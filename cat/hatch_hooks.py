"""Fcatbot 的 Hatch 构建钩子

提供一个 pre-build 钩子：
- 将 `License.txt` 中的年份更新为当前年份
- 将 `src/meta.py` 中的 `__copyright__` 更新为当前年份
- 检查 `src/meta.py` 中的 `__version__` 是否已相对于最新 git tag 做了变更

该钩子可在没有 git 的环境下容错（只记录警告不会直接失败），并支持通过环境变量 `HC_DRY_RUN=1` 进行干运行（不修改文件）。
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

LOG = logging.getLogger("fcatbot.hatch_hooks")

ROOT = Path(__file__).resolve().parent.parent
LICENSE = ROOT / "License.txt"
META = ROOT / "src" / "meta.py"
YEAR = datetime.now().year
DRY_RUN = os.environ.get("HC_DRY_RUN", "0") in ("1", "true", "True")


def _read_meta_version_and_copyright() -> tuple[str, Optional[str]]:
    text = META.read_text(encoding="utf-8")
    # 简单解析 meta.py 中的版本与版权信息
    ver_match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", text)
    copy_match = re.search(r"__copyright__\s*=\s*['\"]([^'\"]+)['\"]", text)
    version = ver_match.group(1) if ver_match else ""
    copyright_text = copy_match.group(1) if copy_match else None
    return version, copyright_text


def _get_latest_git_tag() -> Optional[str]:
    try:
        out = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=ROOT,
            stderr=subprocess.STDOUT,
        )
        tag = out.decode().strip()
        if tag.startswith("v"):
            tag = tag[1:]
        return tag
    except Exception as exc:  # pragma: no cover - git 环境可能不可用
        LOG.debug("无法获取最新 git tag：%s", exc)
        return None


# -------------------------------------------------
# 1. 从 src/meta.py 里提取 __copyright__ 的作者名
# -------------------------------------------------
def _get_copyright_owner() -> str:
    """返回 src/meta.py 里双引号或单引号包着的版权所有者，失败则回退到项目名。"""
    if not META.exists():
        return "Fcatbot Contributors"  # 兜底
    txt = META.read_text(encoding="utf-8")
    m = re.search(r'__copyright__\s*=\s*["\'].*?(\d{4})\s+([^"\']+)["\']', txt)
    return m.group(2).strip() if m else "Fcatbot Contributors"


# -------------------------------------------------
# 2. 全新生成 License.txt
# -------------------------------------------------
def _write_mit_license(*, dry_run: bool | None = None) -> bool:
    """生成一份全新的 MIT License.txt"""
    if dry_run is None:
        dry_run = DRY_RUN

    owner = _get_copyright_owner()
    content = f"""{owner} (c) {YEAR}

MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
    LOG.info("生成新的 MIT License.txt  （作者=%s，年份=%s）", owner, YEAR)
    if not dry_run:
        LICENSE.write_text(content, encoding="utf-8")
    return True


def _update_meta_copy_and_version_check(dry_run: bool | None = None) -> bool:
    """更新 `src/meta.py` 的版权信息并检查版本（不会自动修改版本）。

    参数 dry_run 用于覆盖模块级 DRY_RUN（当为 None 时使用 DRY_RUN）。
    如果发现版本与最新 tag 相同，会抛出 SystemExit(2)。
    """
    if dry_run is None:
        dry_run = DRY_RUN

    text = META.read_text(encoding="utf-8")
    version, copyright_text = _read_meta_version_and_copyright()

    changed = False

    # 更新 __copyright__ 为当前年份
    def _replace_copyright(m: re.Match) -> str:
        prefix = m.group(1)
        author = m.group(4) if m.group(4) else ""
        return f"{prefix}{YEAR} {author}".strip()

    new_text, n = re.subn(
        r"(__copyright__\s*=\s*['\"]Copyright\s*\(c\)\s*)(\d{4})(?:-(\d{4}))?(\s*.*?['\"])",
        lambda m: m.group(1) + str(YEAR) + m.group(4),
        text,
    )
    if n:
        LOG.info("已更新 %s 中的 __copyright__", META)
        changed = True
        if not dry_run:
            META.write_text(new_text, encoding="utf-8")
            text = new_text

    # version change check relative to git tag
    latest_tag = _get_latest_git_tag()
    if latest_tag:
        if version == latest_tag:
            LOG.error(
                "%s 中的版本 (%s) 与最新 git tag (%s) 相同：请先更新版本号", META, version, latest_tag
            )
            raise SystemExit(2)
        else:
            LOG.info("版本检查通过：meta %s, 最新 tag %s", version, latest_tag)
    else:
        LOG.warning("未找到 git 标签或 git 不可用，已跳过版本差异检查")

    return changed


def pre_build(*_args, **_kwargs) -> None:
    """
    Pre-build 预建钩子
    执行文件更新并引发SystemExit以在失败时中止构建
    """
    logging.basicConfig(level=logging.INFO)
    LOG.info("运行 pre-build 钩子（dry-run=%s）", DRY_RUN)

    try:
        updated_license = _write_mit_license()  # ← 只改这一行
        updated_meta = _update_meta_copy_and_version_check()
    except SystemExit:
        LOG.exception("pre-build 检查失败，终止构建")
        raise
    except Exception:
        LOG.exception("运行 pre-build 钩子时发生意外错误")
        raise SystemExit(3)

    if updated_license or updated_meta:
        LOG.info("已应用 pre-build 修改")
    else:
        LOG.info("无需 pre-build 修改")


if __name__ == "__main__":
    # allow local testing
    try:
        pre_build()
        print("OK")
    except SystemExit as e:
        print("PRE-BUILD FAILED", e)
        raise
