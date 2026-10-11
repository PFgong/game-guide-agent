#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通关喵 · 跨平台编译器

把 core/（平台无关的唯一真源）编译成各 Agent 平台的产物，输出到 dist/<platform>/。

用法:
    python build.py                 # 编译所有平台
    python build.py workbuddy dify  # 只编译指定平台
    python build.py --list          # 列出支持的平台

新增平台时：在 PLATFORM_NOTES 里加说明，并在 build_<platform>() 里实现产物生成。
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORE = ROOT / "core"
DIST = ROOT / "dist"
ASSETS = ROOT / "assets"

PKG = "game-guide-expert"
VERSION = "1.0.0"

# ---------------------------------------------------------------- 角色元数据

ROLES = [
    {
        "id": "game-guide-expert-team-lead",
        "file": "01-lead.md",
        "zh": "通关喵",
        "en": "ClearCat",
        "prof_zh": "全平台攻略团主理人",
        "prof_en": "Lead Editor, All-Platform Game Guides",
        "desc": "Lead editor of an all-platform game walkthrough team. Use when a player asks anything "
                "about clearing, building, farming, triggering or solving content in online games, "
                "single-player games, mobile games or mini-games, and expects a live-web-sourced, "
                "version-accurate, illustrated answer with no reasoning shown.",
        "rules": ["05-output-rules.md"],
    },
    {
        "id": "game-question-parser",
        "file": "02-parser.md",
        "zh": "读题喵",
        "en": "BriefCat",
        "prof_zh": "需求解码员",
        "prof_en": "Question Decoder",
        "desc": "Decodes an ambiguous player question into a structured search brief: resolves the game "
                "name, locks platform / version / server / season, classifies the question type, and "
                "emits Chinese-English-Japanese keyword sets. Use before any retrieval happens.",
        "rules": ["05-output-rules.md", "01-source-map.md"],
    },
    {
        "id": "game-guide-crawler",
        "file": "03-crawler.md",
        "zh": "搜猎喵",
        "en": "SearchCat",
        "prof_zh": "全网检索官",
        "prof_en": "Web Retrieval Officer",
        "desc": "Retrieves live game guides from the open web in Chinese, English and Japanese. Produces "
                "an evidence pack with source list, verbatim excerpts and directly renderable image "
                "URLs. Use whenever a question needs external facts.",
        "rules": ["05-output-rules.md", "01-source-map.md", "02-search-playbook.md"],
    },
    {
        "id": "game-fact-verifier",
        "file": "04-verifier.md",
        "zh": "鉴真喵",
        "en": "VerifyCat",
        "prof_zh": "时效核验官",
        "prof_en": "Fact & Freshness Verifier",
        "desc": "Cross-checks retrieved guide claims across sources, judges version freshness, catches "
                "outdated or AI-fabricated guides, and assigns a confidence level. Use when the user "
                "doubts a claim or asks whether it still works on the current patch.",
        "rules": ["05-output-rules.md", "03-credibility-rules.md"],
    },
    {
        "id": "game-answer-writer",
        "file": "05-writer.md",
        "zh": "执笔喵",
        "en": "WriterCat",
        "prof_zh": "答案撰写官",
        "prof_en": "Answer Writer",
        "desc": "Turns verified evidence into a ready-to-follow illustrated answer: picks the output "
                "template by question type, interleaves screenshots after the steps they illustrate, "
                "and strips all reasoning. Use for every player-facing final answer.",
        "rules": ["05-output-rules.md", "04-answer-templates.md"],
    },
]

# 规则文件（core/rules 下的全部，按序）
RULE_FILES = sorted(p.name for p in (CORE / "rules").glob("*.md"))


# ---------------------------------------------------------------- 基础工具

def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.rstrip() + "\n", encoding="utf-8")


def role_body(role: dict) -> str:
    return read(CORE / "roles" / role["file"])


def rules_block(names: list[str]) -> str:
    parts = []
    for n in names:
        parts.append(f"\n---\n\n{read(CORE / 'rules' / n)}")
    return "".join(parts)


def split_sections(text: str) -> list[tuple[str, str]]:
    """按 '## ' 标题切成 [(标题, 正文)]，标题前的导语用 '' 作为标题。"""
    out, cur_title, cur = [], "", []
    for line in text.splitlines():
        if line.startswith("## "):
            out.append((cur_title, "\n".join(cur).strip()))
            cur_title, cur = line[3:].strip(), []
        else:
            cur.append(line)
    out.append((cur_title, "\n".join(cur).strip()))
    return out


def drop_sections(text: str, titles: list[str]) -> str:
    """删除指定标题（支持前缀匹配）的整段。"""
    kept = [f"{t}\n{b}" if t else b for t, b in split_sections(text)
            if not any(t.startswith(x) for x in titles)]
    return "\n\n".join(x for x in kept if x.strip())


# ---------------------------------------------------------------- 平台方言
# core 是平台中性的；各平台产物再注入自己的工具名与机制。

WORKBUDDY_PATCH = [
    (r"回传给编排者", "SendMessage 回传主理人"),
    (r"将回传正文严格写为如下格式：", "用 SendMessage 回传主理人，正文严格如下："),
    (r"## 回传编排者", "## SendMessage 回传"),
    (r"\*\*必须将", "**必须通过 SendMessage 将"),
    (r"必须将完整", "必须通过 SendMessage 将完整"),
    (r"（角色 ID）", "（MD 文件名，不含 .md）"),
]

WORKBUDDY_LEAD_APPEND = """

## 团队协作机制（WorkBuddy 平台实现）

在 WorkBuddy 上，本 SOP 通过正式团队机制落地，严禁简化或跳过：

1. **建立团队**：任务开始时由主理人亲自执行 `TeamCreate`，明确协作边界。
   **团队创建必须且只能由主理人执行，严禁委派任何成员创建团队。**
2. **调度成员**：按 SOP 阶段将成员拉入协作、下发独立任务；成员作为独立协作方输出专业产出，
   不得由主理人代写。
3. **消息中转**：成员产出经 `SendMessage` 回传给主理人，由主理人汇总、转交下一阶段；
   所有跨成员信息流必须经主理人中转，不得互相直连。
4. **成员结论为准**：任何专业产出必须由对应成员输出后再采信，主理人只做编排与汇编。

### 严禁行为
- ❌ 禁止跳过 TeamCreate，直接自己模拟成员发言或并行写出多角色内容
- ❌ 禁止自己代写任何团队成员的专业产出
- ❌ 禁止未完成前序阶段就跳到后续阶段
- ❌ 禁止让成员互相直连通信
- ❌ 禁止 spawn 主理人自己

### 调度参数约定
调度成员时，Agent 工具的 `name` 参数传入成员的**成员 ID**（MD 文件名，不含 .md），
`subagent_type` 传入相同值。禁止使用中文名或自创名称。
"""

CLAUDE_LEAD_APPEND = """

## 团队协作机制（Claude Code 平台实现）

在 Claude Code 上，本 SOP 通过 subagent 机制落地：

1. 主理人通过 **Task tool** 调度成员，或在需要并行时一次性发起多个成员任务。
2. 成员以 subagent 形式独立执行，产出完整结果后回传给主理人。
3. 主理人负责阶段间的信息中转，成员之间不直接通信。
4. 若当前会话未加载 subagent 能力，则退化为单智能体模式：由主理人在内部依次扮演各角色推进。
"""

CLAUDE_PATCH = [
    (r"回传给编排者", "回传给主理人"),
    (r"## 回传编排者", "## 回传给主理人"),
]

SOLO_DROP = ["多智能体编排", "协作通则"]

PLATFORM_NOTES = {
    "workbuddy": "WorkBuddy / CodeBuddy 专家包：plugin.json + agents/*.md + skills 知识库 + 头像",
    "codebuddy": "CodeBuddy 项目级：.codebuddy/agents/*.md + .codebuddy/skills/",
    "claude-code": "Claude Code：.claude/agents/*.md（subagent）+ .claude/skills/ 知识库",
    "cursor": "Cursor：.cursor/rules/*.mdc 规则文件",
    "chatgpt": "ChatGPT 自定义 GPT / Gemini Gem：单文件 system prompt",
    "dify": "Dify：应用提示词 + 五节点工作流 DSL 模板",
    "coze": "Coze（扣子）：单节点提示词 + 多节点拆分说明",
    "generic": "通用：一份纯 Markdown 提示词，任何支持 system prompt 的平台直接粘贴",
}


# ---------------------------------------------------------------- 各平台构建

def build_workbuddy(out: Path):
    """WorkBuddy 专家包（当前唯一支持 Team 型多角色 + 头像的产物）。"""
    pkg = out / PKG
    pkg.mkdir(parents=True, exist_ok=True)

    # plugin.json —— 用 dict 构造再序列化，避免手工拼字符串出错
    import json
    lead = ROLES[0]
    plugin = {
        "name": PKG,
        "version": VERSION,
        "description": "A game walkthrough expert team that searches the live web for guides across "
                       "online, single-player, mobile and mini-games, cross-verifies version "
                       "freshness, and returns direct, illustrated and actionable answers with no "
                       "reasoning exposed.",
        "author": {"name": "pengfei.gong"},
        "agents": [f'./agents/{r["id"]}.md' for r in ROLES],
        "skills": ["./skills/game-guide-research"],
        "expertType": "team",
        "agentName": lead["id"],
        "teamInfo": {
            "leadAgent": lead["id"],
            "memberAgents": [r["id"] for r in ROLES[1:]],
        },
        "displayName": {"en": lead["en"], "zh": lead["zh"]},
        # 校验规则要求顶层 profession 与 displayName 完全一致
        "profession": {"en": lead["en"], "zh": lead["zh"]},
        "displayDescription": {
            "en": "Searches the live web for guides across online, single-player, mobile and "
                  "mini-games, cross-checks version freshness, and hands you a ready-to-follow "
                  "illustrated answer.",
            "zh": "全网实时检索网游、单机、手游、小游戏攻略，交叉核验版本时效，直接给可照做的通关答案。",
        },
        "avatar": "avatars/team.png",
        "categoryId": "03-GameSpatial",
        "defaultInitPrompt": {
            "zh": "《黑神话：悟空》第二章的隐藏BOSS怎么触发？给我完整路线和打法",
            "en": "How do I trigger the hidden boss in Chapter 2 of Black Myth: Wukong? "
                  "Give me the full route and strategy",
        },
        "plugin": PKG,
        "tags": [
            {"en": "Live Guide Search", "zh": "全网攻略检索"},
            {"en": "Version Freshness Check", "zh": "版本时效核验"},
            {"en": "Illustrated Walkthrough", "zh": "图文通关方案"},
        ],
        "quickPrompts": [
            {
                "zh": "《黑神话：悟空》第二章的隐藏BOSS怎么触发？给我完整路线和打法",
                "en": "How do I trigger the hidden boss in Chapter 2 of Black Myth: Wukong? "
                      "Give me the full route and strategy",
            },
            {
                "zh": "《原神》当前版本这个角色该怎么配队、刷哪套圣遗物？给我具体方案",
                "en": "What's the best team comp and artifact set for this Genshin character "
                      "in the current version? Give me a concrete build",
            },
            {
                "zh": "微信小游戏《羊了个羊》第二关一直过不去，有没有稳定通关思路？",
                "en": "I keep failing level 2 of the WeChat mini-game Sheep a Sheep — "
                      "is there a reliable way to clear it?",
            },
        ],
        "members": [
            {
                "id": r["id"],
                "displayName": {"en": r["en"], "zh": r["zh"]},
                "profession": {"en": r["prof_en"], "zh": r["prof_zh"]},
                "avatar": f'avatars/{r["id"]}.png',
                "role": "lead" if i == 0 else "member",
            }
            for i, r in enumerate(ROLES)
        ],
    }
    write(pkg / ".codebuddy-plugin" / "plugin.json",
          json.dumps(plugin, ensure_ascii=False, indent=2))

    # agents
    for r in ROLES:
        body = role_body(r)
        if r["file"] == "01-lead.md":
            body = body + WORKBUDDY_LEAD_APPEND
        for pat, rep in WORKBUDDY_PATCH:
            body = re.sub(pat, rep, body)
        fm = (
            "---\n"
            f'name: {r["id"]}\n'
            f'description: "{r["desc"]}"\n'
            "displayName:\n"
            f'  en: "{r["en"]}"\n'
            f'  zh: "{r["zh"]}"\n'
            "profession:\n"
            f'  en: "{r["prof_en"]}"\n'
            f'  zh: "{r["prof_zh"]}"\n'
            "maxTurns: 200\n"
            "skills: [game-guide-research]\n"
            "---\n\n"
        )
        write(pkg / "agents" / f'{r["id"]}.md', fm + body)

    # skills 知识库（rules 全量）
    skill_dir = pkg / "skills" / "game-guide-research"
    write(skill_dir / "SKILL.md", read(CORE / "rules" / "00-research-index.md"))
    for name in RULE_FILES:
        if name != "00-research-index.md":
            write(skill_dir / "references" / name, read(CORE / "rules" / name))

    # 头像
    if (ASSETS / "avatars").exists():
        av = pkg / "avatars"
        av.mkdir(parents=True, exist_ok=True)
        for png in (ASSETS / "avatars").glob("*.png"):
            shutil.copy(png, av / png.name)

    write(pkg / "settings.json", '{}\n')
    write(out / "README.md", INSTALL_NOTES["workbuddy"])


def _multi_file(out: Path, agent_dir: Path, fm_fn, patch=None, lead_append="", skill_dir=None):
    for r in ROLES:
        body = role_body(r)
        if r["file"] == "01-lead.md" and lead_append:
            body = body + lead_append
        for pat, rep in (patch or []):
            body = re.sub(pat, rep, body)
        write(agent_dir / f'{r["id"]}.md', fm_fn(r) + body)
    if skill_dir:
        write(skill_dir / "SKILL.md", read(CORE / "rules" / "00-research-index.md"))
        for name in RULE_FILES:
            if name != "00-research-index.md":
                write(skill_dir / "references" / name, read(CORE / "rules" / name))


def build_codebuddy(out: Path):
    _multi_file(
        out,
        out / ".codebuddy" / "agents",
        lambda r: f'---\nname: {r["id"]}\ndescription: "{r["desc"]}"\n---\n\n',
        patch=CLAUDE_PATCH,
        lead_append=CLAUDE_LEAD_APPEND,
        skill_dir=out / ".codebuddy" / "skills" / "game-guide-research",
    )
    write(out / "README.md", INSTALL_NOTES["codebuddy"])


def build_claude_code(out: Path):
    _multi_file(
        out,
        out / ".claude" / "agents",
        lambda r: f'---\nname: {r["id"]}\ndescription: "{r["desc"]}"\ntools: WebSearch, WebFetch\n---\n\n',
        patch=CLAUDE_PATCH,
        lead_append=CLAUDE_LEAD_APPEND,
        skill_dir=out / ".claude" / "skills" / "game-guide-research",
    )
    write(out / "README.md", INSTALL_NOTES["claude-code"])


def build_cursor(out: Path):
    base = out / ".cursor" / "rules"
    for r in ROLES:
        body = role_body(r)
        always = "true" if r["file"] == "01-lead.md" else "false"
        fm = (
            "---\n"
            f'description: "{r["desc"]}"\n'
            "globs: \n"
            f"alwaysApply: {always}\n"
            "---\n\n"
        )
        write(base / f'{r["id"]}.mdc', fm + body)
    # 知识库作为一条可按需调用的规则
    kb = "\n\n".join(read(CORE / "rules" / n) for n in RULE_FILES)
    write(base / "game-guide-research.mdc",
          "---\ndescription: \"Game guide retrieval handbook: source map, search playbook, "
          "credibility rules and answer templates.\"\nglobs: \nalwaysApply: false\n---\n\n" + kb)
    write(out / "README.md", INSTALL_NOTES["cursor"])


def build_solo(out: Path):
    """单文件提示词：head + 五角色 + 全部规则 + tail。"""
    lead = drop_sections(read(CORE / "roles" / "01-lead.md"), SOLO_DROP)
    parts = [read(CORE / "solo" / "head.md"), lead]
    for r in ROLES[1:]:
        parts.append(f"\n---\n\n# 内部角色：{r['zh']}（{r['en']}）\n\n"
                     + drop_sections(role_body(r), SOLO_DROP))
    parts.append("\n\n---\n\n# 附录：攻略检索手册（内部执行时遵守）\n")
    for n in RULE_FILES:
        parts.append(f"\n\n{read(CORE / 'rules' / n)}")
    parts.append("\n\n" + read(CORE / "solo" / "tail.md"))
    write(out / "system-prompt.md", "".join(parts))


def build_chatgpt(out: Path):
    build_solo(out)
    write(out / "README.md", INSTALL_NOTES["chatgpt"])


def build_generic(out: Path):
    build_solo(out)
    write(out / "README.md", INSTALL_NOTES["generic"])


def build_dify(out: Path):
    build_solo(out)
    write(out / "workflow.yml", DIFY_WORKFLOW)
    write(out / "README.md", INSTALL_NOTES["dify"])


def build_coze(out: Path):
    build_solo(out)
    for r in ROLES:
        body = drop_sections(role_body(r), SOLO_DROP)
        write(out / "nodes" / f'{r["id"]}.md',
              f'# {r["zh"]}（{r["en"]}）节点提示词\n\n{body}\n\n{rules_block(r["rules"])}')
    write(out / "README.md", INSTALL_NOTES["coze"])


BUILDERS = {
    "workbuddy": build_workbuddy,
    "codebuddy": build_codebuddy,
    "claude-code": build_claude_code,
    "cursor": build_cursor,
    "chatgpt": build_chatgpt,
    "dify": build_dify,
    "coze": build_coze,
    "generic": build_generic,
}


# ---------------------------------------------------------------- 安装说明

INSTALL_NOTES = {
    "workbuddy": """# WorkBuddy / CodeBuddy 安装

1. 把整个 `game-guide-expert/` 目录复制到：
   - Windows：`C:\\Users\\<用户名>\\.workbuddy\\plugins\\marketplaces\\my-experts\\plugins\\`
   - macOS / Linux：`~/.workbuddy/plugins/marketplaces/my-experts/plugins/`
2. 若同目录已存在同名包，直接覆盖即可。
3. 重启 WorkBuddy，左侧栏【专家】→【我的专家】里会出现「通关喵」。

本产物是唯一带头像的多角色专家包，其余平台产物均为纯文本。
""",
    "codebuddy": """# CodeBuddy 项目级安装

把 `.codebuddy/` 整个目录复制到你的项目根目录：

```
<项目>/
└── .codebuddy/
    ├── agents/    # 5 个角色，主理人 game-guide-expert-team-lead
    └── skills/game-guide-research/
```

复制后重启会话即可。若希望全局可用，把 `agents/` 内容放到
`~/.codebuddy/agents/` 下。
""",
    "claude-code": """# Claude Code 安装

放到用户级（所有项目可用）：

```bash
cp -r .claude/agents/*   ~/.claude/agents/
cp -r .claude/skills/*   ~/.claude/skills/
```

或放到项目级：把 `.claude/` 复制到项目根目录。

角色以 subagent 形式被主理人通过 Task tool 调度。`tools` 字段声明了 WebSearch / WebFetch，
若你的环境未启用联网工具，请删掉 frontmatter 里的 `tools` 行并改用其他检索方式。
""",
    "cursor": """# Cursor 安装

把 `.cursor/rules/` 整个目录复制到项目根目录：

```
<项目>/.cursor/rules/
├── game-guide-expert-team-lead.mdc   # alwaysApply: true
├── game-question-parser.mdc
├── game-guide-crawler.mdc
├── game-fact-verifier.mdc
├── game-answer-writer.mdc
└── game-guide-research.mdc           # 检索手册
```

只有主理人设为 alwaysApply，其余按需触发，避免每轮都占用上下文。
也可以在 Cursor 对话里直接 @ 某个规则文件手动调用。
""",
    "chatgpt": """# ChatGPT 自定义 GPT / Gemini Gem 安装

1. 新建 GPT（ChatGPT）或 Gem（Gemini）。
2. 把 `system-prompt.md` 的**全文**粘贴进 Instructions 框。
3. **必须开启联网能力**：ChatGPT 打开 "Web Browsing"；Gemini 依赖内置搜索。
   不开联网本专家会失效——它禁止凭记忆回答数值与版本问题。
4. 建议上传 `avatars/team.png`（如已提供）作为头像。

单文件模式没有真正的子智能体，提示词已把五角色压成"内部依次切换"的流程，
对外仍然只输出答案本身。
""",
    "dify": """# Dify 安装

两种用法，二选一：

**A. 单节点（推荐先跑通）**
新建「Agent」或「Chatflow」应用，把 `system-prompt.md` 全文贴进系统提示词，
开启联网工具（联网搜索 / 网页抓取插件）。

**B. 五节点工作流**
`workflow.yml` 是**示意模板**，描述 Phase 0~5 的节点拆分与三份中间产物
（Brief / 证据包 / 核验结论）的传递关系。Dify 的 DSL 版本差异较大，
建议按其结构在画布上手工搭建，而不是直接导入 YAML。

关键约束：节点间必须传递完整原文，不能只传摘要；最后一个节点只输出答案正文。
""",
    "coze": """# Coze（扣子）安装

**单节点**：新建智能体，把 `system-prompt.md` 全文贴进「人设与回复逻辑」，
在「插件」里加上联网搜索与网页解析能力。

**多节点**：`nodes/` 下已按角色拆好 5 份提示词，可在工作流里建成 5 个 LLM 节点，
按 主理人 → 读题喵 → 搜猎喵 → 鉴真喵 → 执笔喵 → 主理人终审 的顺序连线，
节点输出变量依次传 Brief、证据包、核验结论。

最后一节点务必只输出答案正文，且关闭"输出中间过程"。
""",
    "generic": """# 通用提示词

`system-prompt.md` 是一份纯 Markdown，不依赖任何平台的专有字段。
任何支持 system prompt / 人设设定 / 自定义指令的平台都可以直接粘贴使用，
例如 Claude Projects、Kimi、豆包、文心、通义、元宝、LangChain、OpenAI Assistants 等。

**唯一硬要求**：宿主必须提供联网检索能力。本专家被禁止凭记忆回答数值与版本类问题，
断网环境下会退化为"猜"，这违背它的设计前提。
""",
}

DIFY_WORKFLOW = """# Dify 工作流示意模板
#
# 说明：这是结构示意，不是可直接导入的官方 DSL。
# Dify 各版本 YAML schema 差异较大，请按此结构在画布上手工搭建。
# 核心约定：节点间传完整原文，禁止只传摘要。

version: "1.0"
name: 通关喵攻略团

phases:
  - id: phase0_router          # 主理人：分流（快答 / 标准 / 核验）
    role: game-guide-expert-team-lead
    output: channel

  - id: phase1_parser          # 读题喵 → Brief
    role: game-question-parser
    input: user_query
    output: brief
    skip_when: channel == "quick"

  - id: phase2_crawler         # 搜猎喵 → 证据包
    role: game-guide-crawler
    input: brief
    output: evidence_pack
    retry: 2                   # 有效来源 < 2 条时补检

  - id: phase3_verifier        # 鉴真喵 → 核验结论 + 置信度
    role: game-fact-verifier
    input: [brief, evidence_pack]
    output: verification
    retry_on: confidence == "red"
    skip_when: channel == "quick"

  - id: phase4_writer          # 执笔喵 → 答案
    role: game-answer-writer
    input: [brief, evidence_pack, verification]
    output: answer

  - id: phase5_final           # 主理人终审：只输出答案正文
    role: game-guide-expert-team-lead
    input: answer
    output: final
    rules:
      - 第一句必须是答案本身
      - 不得出现阶段名、角色名、检索过程
      - 图片必须嵌在对应步骤之后
      - 来源列表附在末尾
"""


# ---------------------------------------------------------------- 入口

def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("-")]
    if "--list" in argv:
        for k, v in PLATFORM_NOTES.items():
            print(f"  {k:<12} {v}")
        return 0

    targets = args or list(BUILDERS)
    unknown = [t for t in targets if t not in BUILDERS]
    if unknown:
        print("未知平台:", ", ".join(unknown))
        print("可用平台:", ", ".join(BUILDERS))
        return 1

    # 注意：不做 dist 清理。某些环境（含沙箱 / 回收站不可用）会拦截 unlink 与 rmtree，
    # 而本构建是幂等的——文件集合固定、同名直接覆盖，无需先删。
    # 若确实要清干净，手动删除 dist/ 目录即可。

    print(f"编译 core/ → dist/  (v{VERSION})\n")
    for t in targets:
        out = DIST / t
        out.mkdir(parents=True, exist_ok=True)
        BUILDERS[t](out)
        n = sum(1 for _ in out.rglob("*") if _.is_file())
        print(f"  ✓ {t:<12} {n:>2} 个文件   {PLATFORM_NOTES[t]}")

    print(f"\n完成，输出在 {DIST}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
