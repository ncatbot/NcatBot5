"""配置模块：对外暴露可以由环境变量覆盖的默认配置

目标：把那些可能需要定制的常量（如版本正则、默认版权所有者等）放到这里，
以便在未来通过环境变量或更复杂的配置加载方式进行覆盖。
"""
from __future__ import annotations

import os
import re

from cat import constants

# 版本/版权相关正则，可以通过环境变量覆盖
PATTERN_VERSION = os.getenv("FCAT_PATTERN_VERSION", constants.PATTERN_VERSION)
PATTERN_COPYRIGHT = os.getenv("FCAT_PATTERN_COPYRIGHT", constants.PATTERN_COPYRIGHT)
PATTERN_COPYRIGHT_UPDATE = os.getenv(
    "FCAT_PATTERN_COPYRIGHT_UPDATE", constants.PATTERN_COPYRIGHT_UPDATE
)
PATTERN_SEMVER = os.getenv("FCAT_PATTERN_SEMVER", constants.PATTERN_SEMVER)

PRERELEASE_LABEL = os.getenv("FCAT_PRERELEASE_LABEL", "dev")
# 如果没有通过环境变量显式提供 PATTERN_DEV_VERSION，则根据 PRERELEASE_LABEL 动态生成
if os.getenv("FCAT_PATTERN_DEV_VERSION") is None:
    PATTERN_DEV_VERSION = rf"^(\d+)\.(\d+)\.(\d+)-{re.escape(PRERELEASE_LABEL)}\.(\d+)$"
else:
    PATTERN_DEV_VERSION = os.getenv(
        "FCAT_PATTERN_DEV_VERSION", constants.PATTERN_DEV_VERSION
    )

# 其他可配置项
DEFAULT_COPYRIGHT_OWNER = os.getenv(
    "FCAT_COPYRIGHT_OWNER", constants.DEFAULT_COPYRIGHT_OWNER
)

# 若将来需要，也可以在这里暴露更多配置，比如命令 args 等
GIT_DESCRIBE_ARGS = constants.GIT_DESCRIBE_ARGS
PRECOMMIT_ARGS = constants.PRECOMMIT_ARGS
