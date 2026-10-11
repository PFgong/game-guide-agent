#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通关喵 · MCP 提示词服务器（零依赖，仅用 Python 标准库）

它本身不联网、不检索，只做一件事：把 core/ 与 dist/generic/ 里的专家提示词
通过 MCP 协议暴露出去。任何支持 MCP 的客户端（Claude Desktop、Cursor、Windsurf、
Cline、Cherry Studio、Continue 等）都能直接加载这套专家配置，
从而在所有这些平台上使用同一个「通关喵」。

启动:
    python mcp_server.py

客户端配置示例（claude_desktop_config.json / mcp.json）:
{
  "mcpServers": {
    "game-guide-expert": {
      "command": "python",
      "args": ["<绝对路径>/mcp_server.py"]
    }
  }
}

暴露内容:
    resources  core/**/*.md 与 dist/generic/system-prompt.md
    prompts    5 个角色提示词 + 1 份单文件完整提示词(solo)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORE = ROOT / "core"
DIST = ROOT / "dist"

SERVER_INFO = {"name": "game-guide-expert", "version": "1.0.0"}
PROTOCOL_VERSION = "2024-11-05"

ROLE_NAMES = {
    "01-lead": "通关喵（主理人 / 编排者）",
    "02-parser": "读题喵（需求解码员）",
    "03-crawler": "搜猎喵（全网检索官）",
    "04-verifier": "鉴真喵（时效核验官）",
    "05-writer": "执笔喵（答案撰写官）",
}


def uri_for(path: Path) -> str:
    return "game-guide:///" + path.relative_to(ROOT).as_posix()


def path_for(uri: str) -> Path:
    rel = uri.replace("game-guide:///", "").lstrip("/")
    p = (ROOT / rel).resolve()
    if not str(p).startswith(str(ROOT)):
        raise ValueError("路径越界")
    return p


def list_files() -> list[Path]:
    files = sorted(CORE.rglob("*.md"))
    solo = DIST / "generic" / "system-prompt.md"
    if solo.exists():
        files.append(solo)
    return files


def handle(req: dict) -> dict | None:
    """处理一条 JSON-RPC 请求；通知类（无 id）返回 None。"""
    mid = req.get("id")
    method = req.get("method", "")

    def ok(result):
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def err(code, msg):
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": msg}}

    if method == "initialize":
        return ok({
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"resources": {"subscribe": False, "listChanged": False},
                             "prompts": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": "通关喵 · 全平台游戏攻略专家。用 resources/read 读取提示词，"
                            "或用 prompts/get 取指定角色的完整提示词。"
                            "注意：宿主必须提供联网检索能力，本专家禁止凭记忆回答数值与版本问题。",
        })

    if method in ("notifications/initialized", "initialized", "notifications/cancelled"):
        return None

    if method == "ping":
        return ok({})

    if method == "resources/list":
        res = []
        for f in list_files():
            res.append({
                "uri": uri_for(f),
                "name": f.relative_to(ROOT).as_posix(),
                "description": "通关喵专家配置片段",
                "mimeType": "text/markdown",
            })
        return ok({"resources": res})

    if method == "resources/read":
        uri = (req.get("params") or {}).get("uri", "")
        try:
            p = path_for(uri)
        except ValueError:
            return err(-32602, "非法 uri")
        if not p.exists():
            return err(-32602, f"资源不存在: {uri}")
        return ok({"contents": [{"uri": uri, "mimeType": "text/markdown",
                                 "text": p.read_text(encoding="utf-8")}]})

    if method == "prompts/list":
        prompts = []
        for key, label in ROLE_NAMES.items():
            prompts.append({
                "name": f"role-{key}",
                "description": f"{label} 的完整提示词（多角色平台用）",
                "arguments": [],
            })
        prompts.append({
            "name": "solo-full-prompt",
            "description": "单文件完整提示词：五角色合一，适用于任何支持 system prompt 的平台",
            "arguments": [],
        })
        return ok({"prompts": prompts})

    if method == "prompts/get":
        name = (req.get("params") or {}).get("name", "")
        text = None
        desc = ""
        if name.startswith("role-"):
            key = name[5:]
            p = CORE / "roles" / f"{key}.md"
            if not p.exists():
                return err(-32602, f"未知角色: {name}")
            text = p.read_text(encoding="utf-8")
            desc = ROLE_NAMES.get(key, key)
        elif name == "solo-full-prompt":
            p = DIST / "generic" / "system-prompt.md"
            if not p.exists():
                return err(-32602, "solo 提示词未生成，请先运行 python build.py")
            text = p.read_text(encoding="utf-8")
            desc = "通关喵单文件完整提示词"
        else:
            return err(-32602, f"未知 prompt: {name}")
        return ok({
            "description": desc,
            "messages": [{"role": "user", "content": {"type": "text", "text": text}}],
        })

    if method == "tools/list":
        return ok({"tools": []})

    return err(-32601, f"不支持的方法: {method}")


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps(
                {"jsonrpc": "2.0", "id": None,
                 "error": {"code": -32700, "message": "JSON 解析失败"}}) + "\n")
            sys.stdout.flush()
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
