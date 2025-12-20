"""CI wrapper：供 GitHub Actions 调用的简洁入口

此模块提供一个最小入口 `main()`，在 CI 中调用时会：
- 运行测试（通过 pytest）
- 运行 pre-build 钩子（以 dry-run 模式）

目的是让 workflow 的步骤尽可能简洁：只需调用 `python -m cat.ci` 即可完成主要验证。
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Sequence

from cat import hatch_hooks


def _run_pytest(argv: Sequence[str] | None = None) -> int:
    # 在测试时可以通过设置环境变量 FCAT_SKIP_TESTS=1 来跳过 pytest（避免在 pytest 进程中嵌套调用 pytest）
    if os.environ.get("FCAT_SKIP_TESTS") == "1":
        return 0

    args = ["-q"]
    if argv:
        args.extend(argv)
    # 使用独立进程运行 pytest 更简洁并避免在同一进程中重复导入问题
    return subprocess.call([sys.executable, "-m", "pytest"] + args)


def main() -> int:
    """主入口：在 CI 中运行测试并执行 pre-build（dry-run）。

    返回 0 表示通过，非 0 表示失败（CI 会失败）。
    """
    # 1) 运行测试
    rv = _run_pytest()
    if rv != 0:
        print("测试未通过，终止 CI", file=sys.stderr)
        return rv

    # 2) 尝试运行 pre-commit（CI 上对所有文件运行自动修复），但避免在 pre-commit 本身的执行环境中重复调用
    #    当 PRE_COMMIT=1（pre-commit hook 的运行环境）或 FCAT_SKIP_PRECOMMIT=1 时跳过
    if (
        os.environ.get("PRE_COMMIT") == "1"
        or os.environ.get("FCAT_SKIP_PRECOMMIT") == "1"
    ):
        print("跳过 pre-commit 调用（在 pre-commit 环境或被显式禁用）")
    else:
        try:
            rv = subprocess.call(["pre-commit", "run", "--all-files"])
            if rv != 0:
                print("pre-commit 修复/检查未全部通过，请查看输出", file=sys.stderr)
                return rv
        except FileNotFoundError:
            print("pre-commit 未安装，请在 CI 中安装 pre-commit。", file=sys.stderr)
            return 3

    # 3) 运行构建前检查（dry-run）以确保一致性
    try:
        os.environ.setdefault("HC_DRY_RUN", "1")
        hatch_hooks.pre_build()
    except SystemExit as e:
        print("pre-build 钩子失败：", e, file=sys.stderr)
        return getattr(e, "code", 1) or 1
    except Exception as e:
        print("运行 pre-build 钩子时出错：", e, file=sys.stderr)
        return 3

    print("CI wrapper: All checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
