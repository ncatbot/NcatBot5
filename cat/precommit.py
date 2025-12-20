"""本地 pre-commit 检查脚本（供 pre-commit 或手动调用）

功能：
- 运行快速测试（pytest）
- 检查 requirements 与 pyproject 是否同步
- 运行 pre-build 钩子（dry-run），确保版本等检查通过

该脚本在本地提交前运行，遇到错误将以非 0 退出，阻止提交。
"""

from __future__ import annotations

import subprocess
import sys
import os
from typing import Sequence

from cat import hatch_hooks


def _check_requirements_sync() -> bool:
    # 简单实现：确保 requirements.txt 中的每个包至少出现在 pyproject.toml 的 dependencies 中
    reqs = []
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            reqs.append(line)

    with open("pyproject.toml", "r", encoding="utf-8") as fh:
        data = fh.read()

    # 解析 dependencies 块（简单实现，适用于当前格式）
    deps_block = ""
    start = data.find("dependencies = [")
    if start != -1:
        start = data.find("[", start)
        end = data.find("]", start)
        deps_block = data[start+1:end]

    py_deps = []
    for item in deps_block.splitlines():
        item = item.strip().rstrip(",")
        if not item:
            continue
        item = item.strip(" '\"\n")
        py_deps.append(item)

    missing = [r for r in reqs if r not in py_deps]
    if missing:
        print("以下 requirements 未同步到 pyproject.toml 的 dependencies：", file=sys.stderr)
        for m in missing:
            print("  - ", m, file=sys.stderr)
        return False
    return True


def _run_pytest(argv: Sequence[str] | None = None) -> int:
    # 本地测试时，如需跳过 pytest（例如单元测试中调用该脚本），可设置环境变量 FCAT_SKIP_TESTS=1
    if os.environ.get("FCAT_SKIP_TESTS") == "1":
        return 0

    args = ["-q"]
    if argv:
        args.extend(argv)
    return subprocess.call([sys.executable, "-m", "pytest"] + args)


def main() -> int:
    # 1) 运行测试
    rv = _run_pytest()
    if rv != 0:
        print("测试失败，阻止提交", file=sys.stderr)
        return rv

    # 2) 检查 requirements 同步
    ok = _check_requirements_sync()
    if not ok:
        print("requirements 与 pyproject 不一致，阻止提交", file=sys.stderr)
        return 2

    # 3) 运行 pre-build 钩子（dry-run）
    try:
        os.environ.setdefault("HC_DRY_RUN", "1")
        hatch_hooks.pre_build()
    except SystemExit as e:
        print("pre-build 检查失败：", e, file=sys.stderr)
        return getattr(e, "code", 1) or 1
    except Exception as e:
        print("运行 pre-build 钩子时发生未处理异常：", e, file=sys.stderr)
        return 3

    print("pre-commit 检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())