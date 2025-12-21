"""Fcatbot 的 Hatch 构建钩子"""

from __future__ import annotations

import logging

from cat import constants, processing

LOG = logging.getLogger("fcatbot.hatch_hooks")

# 可由测试 monkeypatch 的路径（默认指向 constants 中的路径）
ROOT = constants.ROOT
LICENSE = constants.LICENSE_PATH
META = constants.META_PATH

# 测试时可以 monkeypatch `_get_latest_git_tag` 来模拟 git 标签
_get_latest_git_tag = None


def pre_build(*_args, **_kwargs) -> None:
    """
    Pre-build 预构建钩子
    执行文件更新并在失败时中止构建
    """
    logging.basicConfig(level=logging.INFO)
    dry_run = processing.is_dry_run()
    LOG.info("运行 pre-build 钩子（dry-run=%s）", dry_run)

    try:
        # 1. 生成/更新许可证
        updated_license = processing.update_license_file(dry_run)

        # 2. 更新版权并检查版本
        updated_copyright, _ = processing.update_meta_copyright(dry_run)
        version_ok, error_msg = processing.check_version()

        if not version_ok:
            LOG.error("版本检查失败: %s", error_msg)
            raise SystemExit(constants.EXIT_VERSION_SAME)

    except SystemExit:
        LOG.exception("pre-build 检查失败，终止构建")
        raise
    except Exception:
        LOG.exception("运行 pre-build 钩子时发生意外错误")
        raise SystemExit(constants.EXIT_GENERAL_ERROR)

    if updated_license or updated_copyright:
        LOG.info("已应用 pre-build 修改")
    else:
        LOG.info("无需 pre-build 修改")
