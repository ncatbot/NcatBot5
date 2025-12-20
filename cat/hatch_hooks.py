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
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

LOG = logging.getLogger("fcatbot.hatch_hooks")

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
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
        out = subprocess.check_output(["git", "describe", "--tags", "--abbrev=0"], cwd=ROOT, stderr=subprocess.STDOUT)
        tag = out.decode().strip()
        if tag.startswith("v"):
            tag = tag[1:]
        return tag
    except Exception as exc:  # pragma: no cover - git 环境可能不可用
        LOG.debug("无法获取最新 git tag：%s", exc)
        return None


def _update_license_year() -> bool:
    if not LICENSE.exists():
        LOG.warning("未找到 %s，跳过 License 年份更新", LICENSE)
        return False

    txt = LICENSE.read_text(encoding="utf-8")
    # 替换类似版权行中的结束年份，例如 (c) 2020 或 2019-2024
    def repl(m: re.Match) -> str:
        prefix = m.group(1)
        start = m.group(2)
        end = m.group(3)
        if end:
            new = f"{prefix}{start}-{YEAR}"
        else:
            new = f"{prefix}{YEAR}"
        return new

    new_txt, n = re.subn(r"(Copyright(?:\s*\(c\))?\s+)(\d{4})(?:-(\d{4}))?", repl, txt, flags=re.I)
    if n:
        LOG.info("更新 %s (%d 次替换)", LICENSE, n)
        if not DRY_RUN:
            LICENSE.write_text(new_txt, encoding="utf-8")
        return True
    LOG.debug("在 %s 中未找到版权模式，跳过", LICENSE)
    return False


def _update_meta_copy_and_version_check() -> bool:
    text = META.read_text(encoding="utf-8")
    version, copyright_text = _read_meta_version_and_copyright()

    changed = False

    # 更新 __copyright__ 行为当前年份
    def _replace_copyright(m: re.Match) -> str:
        prefix = m.group(1)
        author = m.group(4) if m.group(4) else ""
        return f"{prefix}{YEAR} {author}".strip()

    new_text, n = re.subn(r"(__copyright__\s*=\s*['\"]Copyright\s*\(c\)\s*)(\d{4})(?:-(\d{4}))?(\s*.*?['\"])", lambda m: m.group(1) + str(YEAR) + m.group(4), text)
    if n:
        LOG.info("已更新 %s 中的 __copyright__", META)
        changed = True
        if not DRY_RUN:
            META.write_text(new_text, encoding="utf-8")
            text = new_text

    # version change check relative to git tag
    latest_tag = _get_latest_git_tag()
    if latest_tag:
        if version == latest_tag:
            LOG.error("%s 中的版本 (%s) 与最新 git tag (%s) 相同：请先更新版本号", META, version, latest_tag)
            raise SystemExit(2)
        else:
            LOG.info("版本检查通过：meta %s, 最新 tag %s", version, latest_tag)
    else:
        LOG.warning("未找到 git 标签或 git 不可用，已跳过版本差异检查")

    return changed


def pre_build(*_args, **_kwargs) -> None:
    """Pre-build hook called by Hatch.

    It performs file updates and raises SystemExit to abort build on failures.
    """
    logging.basicConfig(level=logging.INFO)
    LOG.info("运行 pre-build 钩子（dry-run=%s）", DRY_RUN)

    try:
        updated_license = _update_license_year()
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
