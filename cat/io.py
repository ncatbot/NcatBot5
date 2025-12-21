"""IO操作模块：文件读写、子进程执行等基础操作"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional, Sequence, Tuple

from cat import config, constants

LOG = logging.getLogger("fcatbot.io")


def read_file(path: Path, encoding: str = "utf-8") -> str:
    """读取文件内容"""
    return path.read_text(encoding=encoding)


def write_file(path: Path, content: str, encoding: str = "utf-8") -> None:
    """写入文件内容"""
    path.write_text(content, encoding=encoding)


def execute_command(
    cmd: Sequence[str], cwd: Optional[Path] = None, capture: bool = False
) -> Tuple[Optional[str], int]:
    """执行命令并返回输出和退出码"""
    try:
        if capture:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
            )
            return result.stdout.strip(), result.returncode
        else:
            returncode = subprocess.call(cmd, cwd=cwd)
            return None, returncode
    except FileNotFoundError as e:
        LOG.error("命令未找到: %s", cmd[0])
        raise e
    except Exception as e:
        LOG.error("执行命令失败: %s", e)
        raise e


def read_meta_file() -> Tuple[str, Optional[str]]:
    """读取meta.py文件并提取版本和版权信息"""
    import re

    text = read_file(constants.META_PATH)

    ver_match = re.search(config.PATTERN_VERSION, text)
    copy_match = re.search(config.PATTERN_COPYRIGHT, text)

    version = ver_match.group(1) if ver_match else ""
    copyright_text = copy_match.group(1) if copy_match else None

    return version, copyright_text


def get_latest_git_tag() -> Optional[str]:
    """获取最新的git标签

    优先尝试调用 `cat.hatch_hooks._get_latest_git_tag`（方便测试时 monkeypatch），
    若不存在则回退到通过 git 命令获取。
    """
    try:
        # 如果 hatch_hooks 提供了覆盖方法（tests 会 monkeypatch），优先使用它
        import importlib

        try:
            hh = importlib.import_module("cat.hatch_hooks")
            if hasattr(hh, "_get_latest_git_tag") and callable(
                getattr(hh, "_get_latest_git_tag")
            ):
                return hh._get_latest_git_tag()
        except Exception:
            pass

        output, returncode = execute_command(
            constants.GIT_DESCRIBE_ARGS,
            cwd=constants.ROOT,
            capture=True,
        )

        if returncode == 0 and output:
            tag = output.strip()
            return tag[1:] if tag.startswith("v") else tag
        return None
    except Exception:
        LOG.debug("无法获取最新git标签")
        return None


def get_copyright_owner() -> str:
    """从meta.py中提取版权所有者"""
    if not constants.META_PATH.exists():
        return config.DEFAULT_COPYRIGHT_OWNER

    text = read_file(constants.META_PATH)
    import re

    m = re.search(r'__copyright__\s*=\s*["\'].*?(\d{4})\s+([^"\']+)["\']', text)
    return m.group(2).strip() if m else constants.DEFAULT_COPYRIGHT_OWNER
