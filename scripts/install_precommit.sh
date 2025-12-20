#!/usr/bin/env bash
set -euo pipefail

# 安装 pre-commit 并启用本项目的本地 hooks
python -m pip install --upgrade pip
python -m pip install pre-commit
# 安装 hooks 并确保本地 hook 链接
pre-commit install --install-hooks

echo "pre-commit 已安装并初始化。要在所有文件上运行一次自动修复，请运行：pre-commit run --all-files"