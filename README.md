# 通关喵 · 跨平台游戏攻略专家

一个覆盖网络游戏 / 单机主机 / 手机游戏 / 小游戏的实时攻略专家，可编译到 **8 类 Agent 平台** + **任意 MCP 客户端**。

玩家问什么，它就去全网把攻略捞出来、验过版本时效、写成一份照着做就能过的图文答案——**不展示思考过程**。

---

## 设计原则：一份真源，多处编译

这个仓库不为任何单一平台而写。

```
core/          平台无关的唯一真源（角色定义 + 检索规则 + 输出铁律）
  ↓ build.py
dist/          8 个平台的原生产物
  ↓ install.py
本机各平台
```

**要改专家的行为？只改 `core/`，然后重新 `python build.py`。** 不要直接改 `dist/` 里的文件——下次编译会被覆盖。

平台专有机制（如 WorkBuddy 的 `TeamCreate` / `SendMessage`、Claude Code 的 `Task tool`）只存在于编译产物里，core 里一律使用中性表述「编排者」「回传」。

---

## 快速开始

```bash
python build.py            # 编译所有平台 → dist/
python install.py --list   # 看支持哪些平台
python install.py workbuddy
```

`build.py` 和 `install.py` 只用 Python 标准库，无依赖。

---

## 支持的平台

| 平台 | 安装方式 | 形态 | 说明 |
|---|---|---|---|
| `workbuddy` | 自动 | 专家包（plugin.json + 5 agents + 知识库 + 头像） | 唯一支持真团队机制与头像的产物 |
| `codebuddy` | 自动 | `.codebuddy/agents/` + `skills/` | 项目级多角色 |
| `claude-code` | 自动 | `.claude/agents/` + `skills/` | subagent 调度 |
| `cursor` | 自动 | `.cursor/rules/*.mdc` | 仅主理人 alwaysApply |
| `chatgpt` | 手动粘贴 | 单文件 system prompt | 也适用于 Gemini Gem |
| `dify` | 手动粘贴 | 提示词 + 五节点工作流模板 | 工作流 YAML 为结构示意 |
| `coze` | 手动粘贴 | 单节点提示词 + 5 份节点拆分 | 扣子智能体 / 工作流 |
| `generic` | 手动粘贴 | 纯 Markdown | 任何支持 system prompt 的平台 |
| **MCP 客户端** | 配置命令 | `mcp_server.py` | Claude Desktop / Cursor / Windsurf / Cline / Cherry Studio 等 |

### MCP：跨平台的通用挂载方式

任何支持 MCP 的客户端都能直接加载本专家，无需复制文件：

```json
{
  "mcpServers": {
    "game-guide-expert": {
      "command": "python",
      "args": ["<绝对路径>/mcp_server.py"]
    }
  }
}
```

服务器零依赖，暴露 `core/` 下全部提示词为 resources，并额外提供 6 个 prompt（5 个角色 + 1 份单文件完整提示词）。

---

## 目录结构

```
core/
  roles/      01-lead  02-parser  03-crawler  04-verifier  05-writer
  rules/      00 检索索引 · 01 源地图 · 02 检索打法 · 03 可信度 · 04 答案模板 · 05 输出铁律
  solo/       单智能体模式的头尾段
build.py      core → dist 编译器
install.py    把产物装到各平台
mcp_server.py MCP 提示词服务器（零依赖）
assets/       头像（仅 WorkBuddy 产物使用）
dist/         编译产物（不入版本库）
```

---

## 五个角色

| 角色 | 职业 | 职责 |
|---|---|---|
| 通关喵 | 主理人 | 分流、阶段推进、成稿终审 |
| 读题喵 | 需求解码员 | 游戏名消歧、锁定平台/版本、产出检索 Brief |
| 搜猎喵 | 全网检索官 | 中英日三语检索、抓图片直链 |
| 鉴真喵 | 时效核验官 | 版本时效判定、多源仲裁、置信度分级 |
| 执笔喵 | 答案撰写官 | 按 8 类模板成稿、图文混排 |

**单智能体平台怎么办**：Core 的 lead 定义了 A/B/C 三类宿主自适应规则——支持子智能体的走调度，只支持单智能体的由模型在内部依次切换角色，支持工作流的拆成节点。行为一致，只是过程可见性不同。

---

## 硬要求

**宿主平台必须提供联网检索能力。** 输出铁律第 7 条明确禁止凭记忆回答数值与版本类问题——训练数据里的攻略大概率已过期。断网环境下它会退化为"猜"，这违背设计前提。

---

## 新增一个平台

1. 在 `build.py` 的 `PLATFORM_NOTES` 里加一行说明。
2. 实现 `build_<platform>(out)`：读 `core/`，写 `dist/<platform>/`。
   - 多文件平台：复用 `_multi_file()`，传入 frontmatter 生成函数与平台补丁表。
   - 单文件平台：复用 `build_solo()`，它会拼好 head + 五角色 + 全部规则 + tail。
3. 在 `BUILDERS` 字典里注册。
4. 若要自动安装，在 `install.py` 的 `INSTALLERS` 里加对应函数。

---

## License

MIT
