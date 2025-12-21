"""处理模块：业务逻辑处理"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Optional, Tuple

from cat import config, constants, io

LOG = logging.getLogger("fcatbot.processing")


def is_dry_run() -> bool:
    """检查是否为干运行模式"""
    return os.environ.get(constants.ENV_DRY_RUN, "0") in constants.ENV_DRY_RUN_VALUES


def should_skip_tests() -> bool:
    """检查是否应该跳过测试"""
    return os.environ.get(constants.ENV_SKIP_TESTS) == "1"


def should_skip_precommit() -> bool:
    """检查是否应该跳过pre-commit"""
    return (
        os.environ.get(constants.ENV_PRE_COMMIT) == "1"
        or os.environ.get(constants.ENV_SKIP_PRECOMMIT) == "1"
    )


def generate_mit_license(owner: Optional[str] = None) -> str:
    """生成MIT许可证内容"""
    if owner is None:
        owner = io.get_copyright_owner()

    year = datetime.now().year
    return constants.MIT_LICENSE_TEMPLATE.format(owner=owner, year=year)


def update_license_file(dry_run: Optional[bool] = None) -> bool:
    """更新License.txt文件"""
    if dry_run is None:
        dry_run = is_dry_run()

    owner = io.get_copyright_owner()
    content = generate_mit_license(owner)

    year = datetime.now().year
    LOG.info("生成新的MIT License.txt（作者=%s，年份=%s）", owner, year)

    if not dry_run:
        io.write_file(constants.LICENSE_PATH, content)

    return True


def update_meta_copyright(dry_run: Optional[bool] = None) -> Tuple[bool, str]:
    """更新meta.py中的版权信息"""
    if dry_run is None:
        dry_run = is_dry_run()

    text = io.read_file(constants.META_PATH)
    year = str(datetime.now().year)

    def replace_copyright(match: re.Match) -> str:
        return f"{match.group(1)}{year}{match.group(4)}".strip()

    new_text, n = re.subn(
        config.PATTERN_COPYRIGHT_UPDATE,
        replace_copyright,
        text,
    )

    if n > 0:
        LOG.info("已更新 %s 中的 __copyright__", constants.META_PATH)
        if not dry_run:
            io.write_file(constants.META_PATH, new_text)
        return True, new_text

    return False, text


def check_version() -> Tuple[bool, Optional[str]]:
    """检查版本是否已更新"""
    version, _ = io.read_meta_file()
    latest_tag = io.get_latest_git_tag()

    if latest_tag:
        if version == latest_tag:
            LOG.error(
                "%s 中的版本 (%s) 与最新git标签 (%s) 相同",
                constants.META_PATH,
                version,
                latest_tag,
            )
            return False, f"版本 {version} 与标签 {latest_tag} 相同"
        else:
            LOG.info("版本检查通过：meta %s, 最新标签 %s", version, latest_tag)
            return True, None
    else:
        LOG.warning("未找到git标签或git不可用，已跳过版本差异检查")
        return True, None  # 当git不可用时视为通过


def bump_dev_version() -> Tuple[bool, Optional[str]]:
    """增加开发版本号"""
    version, _ = io.read_meta_file()
    text = io.read_file(constants.META_PATH)

    # 尝试匹配开发版本格式
    dev_match = re.match(config.PATTERN_DEV_VERSION, version)
    if dev_match:
        major, minor, patch, dev = dev_match.groups()
        new_version = (
            f"{major}.{minor}.{patch}-{config.PRERELEASE_LABEL}.{int(dev) + 1}"
        )
    else:
        # 尝试匹配标准版本格式
        semver_match = re.match(config.PATTERN_SEMVER, version)
        if semver_match:
            major, minor, patch = semver_match.groups()
            new_version = f"{major}.{minor}.{patch}-{config.PRERELEASE_LABEL}.0"
        else:
            return False, f"无法解析版本号: {version}"

    # 更新文件
    new_text = re.sub(config.PATTERN_VERSION, f'__version__ = "{new_version}"', text)

    io.write_file(constants.META_PATH, new_text)
    LOG.info("版本已更新: %s -> %s", version, new_version)
    return True, new_version


def sync_requirements_to_pyproject(auto_fix: bool = True) -> Tuple[bool, list[str]]:
    """同步requirements.txt到pyproject.toml"""
    # 读取requirements.txt
    requirements = []
    try:
        with open("requirements.txt", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    requirements.append(line)
    except FileNotFoundError:
        return True, []  # 如果没有requirements.txt，视为通过

    # 读取pyproject.toml
    try:
        with open("pyproject.toml", "r", encoding="utf-8") as f:
            pyproject_content = f.read()
    except FileNotFoundError:
        LOG.error("pyproject.toml 未找到")
        return False, requirements if not auto_fix else []

    # 查找dependencies部分
    start = pyproject_content.find("dependencies = [")
    if start == -1:
        LOG.error("pyproject.toml 中未找到 dependencies 块")
        return False, requirements if not auto_fix else []

    start_br = pyproject_content.find("[", start)
    end_br = pyproject_content.find("]", start_br)

    # 提取现有依赖
    existing_deps = []
    deps_block = pyproject_content[start_br + 1 : end_br]
    for line in deps_block.splitlines():
        line = line.strip().rstrip(",")
        if line:
            existing_deps.append(line.strip(" '\""))

    # 查找缺失的依赖
    missing = [r for r in requirements if r not in existing_deps]

    if not missing:
        return True, []

    if not auto_fix:
        return False, missing

    # 自动修复：添加缺失的依赖
    lines = deps_block.splitlines()
    for dep in missing:
        lines.append(f'    "{dep}",')

    new_deps_block = "\n".join(lines)
    new_content = (
        pyproject_content[: start_br + 1]
        + "\n"
        + new_deps_block
        + "\n"
        + pyproject_content[end_br:]
    )

    with open("pyproject.toml", "w", encoding="utf-8") as f:
        f.write(new_content)

    LOG.info("已将缺失的依赖添加到pyproject.toml: %s", missing)
    return True, missing
