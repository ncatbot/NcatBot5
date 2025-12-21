"""cat 工具包常量定义

集中管理所有工具模块中使用的常量、路径和环境变量。
"""

from __future__ import annotations

from pathlib import Path

# ---------- 路径常量 ----------
ROOT = Path(__file__).resolve().parent.parent
LICENSE_PATH = ROOT / "License.txt"
META_PATH = ROOT / "src" / "meta.py"

# ---------- 环境变量 ----------
ENV_SKIP_TESTS = "FCAT_SKIP_TESTS"
ENV_SKIP_PRECOMMIT = "FCAT_SKIP_PRECOMMIT"
ENV_PRE_COMMIT = "PRE_COMMIT"
ENV_DRY_RUN = "HC_DRY_RUN"
ENV_DRY_RUN_VALUES = ("1", "true", "True")

# ---------- 退出码 ----------
EXIT_SUCCESS = 0
EXIT_TEST_FAILED = 1
EXIT_VERSION_SAME = 2
EXIT_GENERAL_ERROR = 3
EXIT_PRECOMMIT_NOT_FOUND = 4
EXIT_VERSION_BUMP_FAILED = 5

# ---------- 正则表达式模式 ----------
PATTERN_VERSION = r"__version__\s*=\s*['\"]([^'\"]+)['\"]"
PATTERN_COPYRIGHT = r"__copyright__\s*=\s*['\"]([^'\"]+)['\"]"
PATTERN_COPYRIGHT_UPDATE = (
    r"(__copyright__\s*=\s*['\"]Copyright\s*\(c\)\s*)(\d{4})(?:-(\d{4}))?(\s*.*?['\"])"
)
PATTERN_SEMVER = r"^(\d+)\.(\d+)\.(\d+)$"
PATTERN_DEV_VERSION = r"^(\d+)\.(\d+)\.(\d+)-dev\.(\d+)$"

# ---------- 字符串常量 ----------
DEFAULT_COPYRIGHT_OWNER = "Fcatbot Contributors"
MIT_LICENSE_TEMPLATE = """{owner} (c) {year}

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

# ---------- 命令行参数 ----------
PYTEST_ARGS = ["-q"]
PRECOMMIT_ARGS = ["run", "--all-files"]
GIT_DESCRIBE_ARGS = ["git", "describe", "--tags", "--abbrev=0"]
