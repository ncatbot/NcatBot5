#!/usr/bin/env python3
"""生成（并可选择应用）发布说明，同时保留用户自定义区块。

使用方法：
  python scripts/generate_release_notes.py [--apply] [--dry-run]

行为说明：
 - 从环境变量 `TAG_NAME` 或 `GITHUB_REF` 中检测发布标签。
 - 基于上一个标签以来的git提交记录生成程序化更新日志。
 - 更新现有发布时，保留标记之间的用户自定义区块。
 - 使用 GitHub API 和 `GITHUB_TOKEN` 创建或更新发布。

发布正文中保留的标记：
<!-- BEGIN USER CUSTOM DESCRIPTION -->
> 喵喵喵?
<!-- END USER CUSTOM DESCRIPTION -->
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

BEGIN_MARKER = "<!-- BEGIN USER CUSTOM DESCRIPTION -->"
END_MARKER = "<!-- END USER CUSTOM DESCRIPTION -->"

API_BASE = "https://api.github.com"


def run(cmd: list[str]) -> str:
    """运行shell命令并返回输出"""
    return subprocess.check_output(cmd, text=True).strip()


def get_env_tag() -> Optional[str]:
    """从环境变量获取当前标签"""
    tag = os.environ.get("TAG_NAME")
    if tag:
        return tag
    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/tags/"):
        return ref.split("refs/tags/", 1)[1]
    return None


def get_repo() -> str:
    """获取GitHub仓库路径"""
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise SystemExit("错误：未设置 GITHUB_REPOSITORY 环境变量")
    return repo


def get_previous_tag(current_tag: str) -> Optional[str]:
    """获取前一个标签（按创建日期排序）"""
    try:
        tags = run(["git", "tag", "--sort=-creatordate"]).splitlines()
    except subprocess.CalledProcessError:
        return None
    for t in tags:
        if t != current_tag:
            return t
    return None


def get_commit_list(prev: Optional[str], tag: str) -> str:
    """获取两个标签之间的提交列表"""
    try:
        if prev:
            out = run(["git", "log", "--pretty=format:- %s", f"{prev}..{tag}"])
        else:
            # 回退方案：获取标签前的50个提交
            out = run(["git", "log", "--pretty=format:- %s", f"{tag}", "-n", "50"])
        return out if out else "- 无变更"
    except subprocess.CalledProcessError:
        return "- 无变更"


def gh_api_request(method: str, path: str, token: str, data: Optional[dict] = None):
    """发送GitHub API请求"""
    url = API_BASE + path
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    data_bytes = None
    if data is not None:
        data_bytes = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data_bytes, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        body = e.read().decode()
        raise RuntimeError(f"GitHub API错误 {e.code}: {body}")


def extract_user_block(existing_body: Optional[str]) -> str:
    """从现有发布正文中提取用户自定义区块"""
    if not existing_body:
        return "\n*在此处添加您的自定义发布说明*\n"
    m = re.search(
        re.escape(BEGIN_MARKER) + r"(.*?)" + re.escape(END_MARKER), existing_body, re.S
    )
    if m:
        return m.group(1).strip() + "\n"
    return "\n*在此处添加您的自定义发布说明*\n"


def compose_body(changelog: str, user_block: str) -> str:
    """组合完整的发布正文"""
    parts = [
        "## 更新日志",
        "",
        changelog.strip(),
        "",
        BEGIN_MARKER,
        "",
        user_block.strip(),
        "",
        END_MARKER,
    ]
    return "\n".join(parts)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="生成发布说明")
    parser.add_argument("--apply", action="store_true", help="在GitHub上创建或更新发布")
    parser.add_argument("--dry-run", action="store_true", help="仅打印正文并退出")
    args = parser.parse_args()

    tag = get_env_tag()
    if not tag.startswith("v"):
        print("跳过无效版本标签")
        sys.exit(0)
    if not tag:
        print("错误：未检测到标签。请确保在标签推送时运行或设置TAG_NAME环境变量。")
        sys.exit(1)

    repo = get_repo()
    token = os.environ.get("GITHUB_TOKEN")
    if args.apply and not token:
        print("错误：应用更改需要GITHUB_TOKEN环境变量")
        sys.exit(1)

    prev = get_previous_tag(tag)
    commits = get_commit_list(prev, tag)

    programmatic = commits

    existing_release = None
    existing_body = None
    existing_id = None
    if token:
        existing = gh_api_request(
            "GET", f"/repos/{repo}/releases/tags/{urllib.parse.quote(tag)}", token
        )
        if existing:
            existing_release = existing
            existing_body = existing.get("body")
            existing_id = existing.get("id")

    user_block = extract_user_block(existing_body)
    body = compose_body(programmatic, user_block)

    if args.dry_run or not args.apply:
        print(body)
        return

    # 创建或更新发布
    if existing_release:
        print(f"正在更新发布 {tag} (id={existing_id})")
        data = {"body": body, "name": tag}
        gh_api_request("PATCH", f"/repos/{repo}/releases/{existing_id}", token, data)
        print("更新完成")
    else:
        print(f"正在创建发布 {tag}")
        data = {
            "tag_name": tag,
            "name": tag,
            "body": body,
            "draft": False,
            "prerelease": False,
        }
        gh_api_request("POST", f"/repos/{repo}/releases", token, data)
        print("创建完成")


if __name__ == "__main__":
    main()
