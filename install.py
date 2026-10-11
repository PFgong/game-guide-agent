#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通关喵 · 跨平台安装器

先跑 `python build.py` 生成 dist/，再用本脚本把产物装到目标平台的位置。

用法:
    python install.py --list                 列出支持的平台与安装位置
    python install.py workbuddy              装到 WorkBuddy 专家目录
    python install.py claude-code            装到 ~/.claude/
    python install.py codebuddy              装到当前项目的 .codebuddy/
    python install.py cursor --project D:/x  装到指定项目的 .cursor/rules/
    python install.py chatgpt                打印单文件提示词（需手动粘贴）
    python install.py --print generic        把提示词打到 stdout，便于重定向到文件

说明：本脚本只做复制与覆盖，不删除任何已有文件。
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
HOME = Path.home()

# 平台 -> (dist 子目录, 目标位置描述, 解析函数或 None 表示需手动安装)
PLATFORMS = {
    "workbuddy": "WorkBuddy / CodeBuddy 专家包（多角色 + 头像，唯一支持团队机制）",
    "codebuddy": "CodeBuddy 项目级 agents + skills",
    "claude-code": "Claude Code 全局 agents + skills",
    "cursor": "Cursor 项目规则 .cursor/rules/",
    "chatgpt": "ChatGPT 自定义 GPT / Gemini Gem（手动粘贴）",
    "dify": "Dify 应用提示词（手动粘贴）",
    "coze": "Coze 智能体提示词（手动粘贴）",
    "generic": "通用 Markdown 提示词（手动粘贴）",
}

AUTO = {"workbuddy", "codebuddy", "claude-code", "cursor"}


def copy_tree(src: Path, dst: Path) -> int:
    """覆盖式复制，返回复制的文件数。不删除目标已有文件。"""
    if not src.exists():
        raise SystemExit(f"产物不存在：{src}\n请先运行：python build.py")
    n = 0
    for f in src.rglob("*"):
        if f.is_file():
            target = dst / f.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, target)
            n += 1
    return n


def install_workbuddy(_: argparse.Namespace) -> str:
    dst = HOME / ".workbuddy" / "plugins" / "marketplaces" / "my-experts" / "plugins" / "game-guide-expert"
    n = copy_tree(DIST / "workbuddy" / "game-guide-expert", dst)
    return f"{dst}\n\n复制 {n} 个文件。重启 WorkBuddy 后，在【专家】→【我的专家】里使用「通关喵」。\n" \
           f"若已在市场中注册过，无需再改 marketplace.json。"


def install_claude_code(_: argparse.Namespace) -> str:
    agents = HOME / ".claude" / "agents"
    skills = HOME / ".claude" / "skills" / "game-guide-research"
    n1 = copy_tree(DIST / "claude-code" / ".claude" / "agents", agents)
    n2 = copy_tree(DIST / "claude-code" / ".claude" / "skills" / "game-guide-research", skills)
    return f"{agents}  ({n1} 个角色)\n{skills}  ({n2} 个文件)\n\n" \
           f"重启 Claude Code 后即可通过主理人角色调度。\n" \
           f"若你的环境没有 WebSearch / WebFetch 工具，删掉角色文件 frontmatter 里的 tools 行。"


def install_codebuddy(ns: argparse.Namespace) -> str:
    dst = Path(ns.project).resolve() if ns.project else Path.cwd()
    n = copy_tree(DIST / "codebuddy" / ".codebuddy", dst / ".codebuddy")
    return f"{dst / '.codebuddy'}\n\n复制 {n} 个文件到项目根目录。\n" \
           f"想全局可用改为复制到 {HOME / '.codebuddy'}。"


def install_cursor(ns: argparse.Namespace) -> str:
    dst = Path(ns.project).resolve() if ns.project else Path.cwd()
    n = copy_tree(DIST / "cursor" / ".cursor", dst / ".cursor")
    return f"{dst / '.cursor' / 'rules'}\n\n复制 {n} 个文件。\n" \
           f"仅主理人规则设为 alwaysApply，其余按需 @ 引用，避免占用每轮上下文。"


INSTALLERS = {
    "workbuddy": install_workbuddy,
    "claude-code": install_claude_code,
    "codebuddy": install_codebuddy,
    "cursor": install_cursor,
}


def main() -> int:
    ap = argparse.ArgumentParser(description="通关喵跨平台安装器")
    ap.add_argument("platform", nargs="?", help="目标平台名")
    ap.add_argument("--list", action="store_true", help="列出所有平台")
    ap.add_argument("--project", help="项目根目录（codebuddy / cursor 用）")
    ap.add_argument("--print", dest="to_stdout", action="store_true",
                    help="把提示词打到 stdout 而不是打开目录")
    ns = ap.parse_args()

    if ns.list or not ns.platform:
        print("支持的平台：\n")
        for k, v in PLATFORMS.items():
            tag = "自动安装" if k in AUTO else "手动粘贴"
            print(f"  {k:<12} [{tag}]  {v}")
        print("\n用法：python install.py <平台>")
        return 0

    p = ns.platform
    if p not in PLATFORMS:
        print(f"未知平台：{p}（可用：{', '.join(PLATFORMS)}）")
        return 1

    if p in INSTALLERS:
        print(f"\n[安装] {p}")
        print(INSTALLERS[p](ns))
        return 0

    # 手动粘贴类：给出提示词文件路径
    f = DIST / p / "system-prompt.md"
    if not f.exists():
        raise SystemExit(f"产物不存在：{f}\n请先运行：python build.py")
    if ns.to_stdout:
        sys.stdout.write(f.read_text(encoding="utf-8"))
        return 0
    print(f"\n[{p}] 该平台需手动粘贴提示词。\n")
    print(f"提示词文件：{f}")
    print(f"体量：{f.stat().st_size / 1024:.0f} KB\n")
    print("复制到剪贴板：")
    print(f"  python install.py {p} --print | clip      # Windows")
    print(f"  python install.py {p} --print | pbcopy    # macOS")
    print("\n粘贴位置见 dist/%s/README.md" % p)
    print("\n注意：必须开启该平台的联网检索能力，否则本专家会退化为凭记忆作答。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
