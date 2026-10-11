#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键推送到 GitHub。

前置条件（需在浏览器完成一次）：
  1. 建空仓库 https://github.com/new  名字 game-guide-agent，不要勾任何初始化文件
  2. 登记 SSH 公钥 https://github.com/settings/keys （公钥可用 `cat ~/.ssh/id_rsa.pub` 查看）

然后运行：
    python push.py

脚本会依次检查：仓库是否存在 → SSH 是否通 → 推送 main → 打 tag → 推 tag。
任一步不满足就停下来说明原因，不会盲目重试。
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

OWNER = "PFgong"
REPO = "game-guide-agent"
TAG = "v1.0.0"
ROOT = Path(__file__).resolve().parent


def run(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return 1, f"超时（{timeout}s）"


def repo_exists() -> bool | None:
    """True 存在 / False 不存在 / None 无法判断（比如断网）"""
    url = f"https://api.github.com/repos/{OWNER}/{REPO}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        return None
    except Exception:
        return None


def ssh_ok() -> tuple[bool, str]:
    code, out = run(["ssh", "-T", "-o", "BatchMode=yes", "git@github.com"], timeout=30)
    ok = ("successfully authenticated" in out) or ("Hi " in out)
    return ok, out


def main() -> int:
    print(f"目标：{OWNER}/{REPO}   标签：{TAG}\n")

    print("[1/5] 检查远端仓库是否存在 ...")
    exists = repo_exists()
    if exists is False:
        print(f"  ✗ 仓库 {OWNER}/{REPO} 不存在。")
        print(f"    请先在 https://github.com/new 创建它（不要勾选 README / .gitignore / License）。")
        return 1
    if exists is None:
        print("  ? 无法确认（网络问题或仓库为私有），继续尝试。")
    else:
        print("  ✓ 仓库存在")

    print("[2/5] 检查 SSH 认证 ...")
    ok, out = ssh_ok()
    if not ok:
        print("  ✗ SSH 未通过认证：")
        print(f"    {out.splitlines()[0] if out else '无输出'}")
        print("\n    请把本机公钥添加到 https://github.com/settings/keys ：")
        print("      cat ~/.ssh/id_rsa.pub")
        return 1
    print(f"  ✓ {out.splitlines()[0]}")

    print("[3/5] 推送 main 分支 ...")
    code, out = run(["git", "push", "-u", "origin", "main"], timeout=300)
    if code != 0:
        print("  ✗ 推送失败：")
        print(out)
        return 1
    print("  ✓ 已推送")

    print(f"[4/5] 打标签 {TAG} ...")
    code, out = run(["git", "tag", TAG])
    if code != 0 and "already exists" not in out:
        print(f"  ! {out}")
    else:
        print("  ✓ 标签就绪")

    print("[5/5] 推送标签（触发 Release 工作流）...")
    code, out = run(["git", "push", "origin", TAG], timeout=120)
    if code != 0:
        print("  ✗ 标签推送失败：")
        print(out)
        return 1
    print("  ✓ 已推送")

    print(f"\n完成。仓库：https://github.com/{OWNER}/{REPO}")
    print(f"Release 附件：https://github.com/{OWNER}/{REPO}/releases/tag/{TAG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
