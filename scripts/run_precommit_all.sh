#!/usr/bin/env bash
set -euo pipefail

# 对仓库中所有文件运行 pre-commit（会尝试自动修复支持 auto-fix 的 hook）
pre-commit run --all-files --show-diff-on-failure
