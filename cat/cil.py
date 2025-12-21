"""Fcatbot 命令行工具 - 统一入口"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from cat import constants, hatch_hooks, io, processing


def setup_logging(verbose: bool = False) -> None:
    """配置日志级别"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(name)s - %(levelname)s - %(message)s",
    )


def run_tests(pytest_args: Optional[list[str]] = None) -> int:
    """运行测试套件"""
    if processing.should_skip_tests():
        print("跳过测试（FCAT_SKIP_TESTS=1）")
        return constants.EXIT_SUCCESS

    args = constants.PYTEST_ARGS.copy()
    if pytest_args:
        args.extend(pytest_args)

    _, returncode = io.execute_command([sys.executable, "-m", "pytest"] + args)
    return returncode


def run_precommit_check() -> int:
    """运行本地 pre-commit 检查（内部实现）"""
    print("运行本地 pre-commit 检查...")

    # 1) 运行测试
    rv = run_tests()
    if rv != constants.EXIT_SUCCESS:
        print("❌ 测试失败，阻止提交", file=sys.stderr)
        return rv

    # 2) 检查并自动同步 requirements 到 pyproject
    ok, missing = processing.sync_requirements_to_pyproject(auto_fix=True)
    if not ok:
        print("❌ requirements 与 pyproject 不一致，阻止提交", file=sys.stderr)
        print("以下 requirements 未同步到 pyproject.toml:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return constants.EXIT_GENERAL_ERROR

    # 3) 运行构建前的检查/修复
    try:
        # 更新许可证文件
        processing.update_license_file(dry_run=False)

        # 更新版权信息
        processing.update_meta_copyright(dry_run=False)

        # 检查版本
        version_ok, error_msg = processing.check_version()
        if not version_ok:
            print(f"检测到版本问题: {error_msg}")
            print("尝试自动增加开发版本号...")

            bumped, new_version = processing.bump_dev_version()
            if bumped:
                print(f"✅ 已自动更新版本为: {new_version}")

                # 重新检查版本
                version_ok, _ = processing.check_version()
                if version_ok:
                    # 将变更添加到 Git
                    io.execute_command(["git", "add", str(hatch_hooks.META)])
                    io.execute_command(["git", "add", str(hatch_hooks.LICENSE)])
                    print("✅ 已自动提交文件更改")
                else:
                    print("❌ 版本更新后检查失败", file=sys.stderr)
                    return constants.EXIT_VERSION_BUMP_FAILED
            else:
                print(f"❌ 无法自动更新版本: {new_version}", file=sys.stderr)
                return constants.EXIT_VERSION_BUMP_FAILED

    except Exception as e:
        print(f"❌ 运行 pre-build 钩子时发生异常: {e}", file=sys.stderr)
        return constants.EXIT_GENERAL_ERROR

    print("✅ pre-commit 检查通过")
    return constants.EXIT_SUCCESS


def run_external_precommit() -> int:
    """运行外部 pre-commit 工具"""
    if processing.is_dry_run():
        print("跳过 pre-commit 调用（dry-run 模式）")
        return constants.EXIT_SUCCESS

    if processing.should_skip_precommit():
        print("跳过 pre-commit 调用（FCAT_SKIP_PRECOMMIT 已设置）")
        return constants.EXIT_SUCCESS

    try:
        _, returncode = io.execute_command(["pre-commit"] + constants.PRECOMMIT_ARGS)
        return returncode
    except FileNotFoundError:
        print("❌ pre-commit 未安装，请在环境中安装 pre-commit", file=sys.stderr)
        return constants.EXIT_PRECOMMIT_NOT_FOUND


def run_build_check(dry_run: bool = True) -> int:
    """运行构建前检查"""
    import os

    # 保存原始环境变量
    old_dry = os.environ.get(constants.ENV_DRY_RUN)

    try:
        # 设置 dry-run 模式
        if dry_run:
            os.environ[constants.ENV_DRY_RUN] = "1"
        else:
            os.environ.pop(constants.ENV_DRY_RUN, None)

        print(f"运行构建前检查 (dry-run={'✅' if dry_run else '❌'})...")

        # 调用 hatch 钩子
        hatch_hooks.pre_build()

        print("✅ 构建前检查通过")
        return constants.EXIT_SUCCESS

    except SystemExit as e:
        exit_code = (
            getattr(e, "code", constants.EXIT_GENERAL_ERROR)
            or constants.EXIT_GENERAL_ERROR
        )
        print(f"❌ pre-build 钩子失败: {e}", file=sys.stderr)
        return exit_code
    except Exception as e:
        print(f"❌ 运行构建前检查时发生异常: {e}", file=sys.stderr)
        return constants.EXIT_GENERAL_ERROR
    finally:
        # 恢复环境变量
        if old_dry is None:
            os.environ.pop(constants.ENV_DRY_RUN, None)
        else:
            os.environ[constants.ENV_DRY_RUN] = old_dry


def run_ci_pipeline() -> int:
    """完整的 CI 流水线"""
    print("🚀 开始 CI 流水线...")

    # 1) 运行测试
    print("\n=== 步骤 1: 运行测试 ===")
    rv = run_tests()
    if rv != constants.EXIT_SUCCESS:
        return rv

    # 2) 运行外部 pre-commit
    print("\n=== 步骤 2: 运行 pre-commit 检查 ===")
    rv = run_external_precommit()
    if rv != constants.EXIT_SUCCESS:
        return rv

    # 3) 运行构建前检查 (dry-run 模式)
    print("\n=== 步骤 3: 运行构建前检查 ===")
    rv = run_build_check(dry_run=True)
    if rv != constants.EXIT_SUCCESS:
        return rv

    print("\n✅ CI 流水线全部检查通过！")
    return constants.EXIT_SUCCESS


def show_version() -> None:
    """显示版本信息"""
    try:
        version, copyright_text = io.read_meta_file()
        latest_tag = io.get_latest_git_tag()

        print(f"版本: {version}")
        if latest_tag:
            print(f"最新 Git 标签: {latest_tag}")
        if copyright_text:
            print(f"版权: {copyright_text}")

    except Exception as e:
        print(f"无法读取版本信息: {e}", file=sys.stderr)


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m cat.cil ci               # 运行完整的 CI 流水线
  python -m cat.cil precommit        # 运行本地 pre-commit 检查
  python -m cat.cil test             # 仅运行测试
  python -m cat.cil test -v          # 运行详细测试
  python -m cat.cil build            # 运行构建前检查
  python -m cat.cil build --no-dry-run  # 实际修改文件的构建检查
  python -m cat.cil version          # 显示版本信息
        """,
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="启用详细输出")

    subparsers = parser.add_subparsers(dest="command", title="可用命令", metavar="COMMAND")

    # CI 命令
    subparsers.add_parser("ci", help="运行完整的 CI 流水线（测试 + pre-commit + 构建检查）")

    # 本地 pre-commit 命令
    subparsers.add_parser("precommit", help="运行本地 pre-commit 检查（自动修复问题）")

    # 测试命令
    test_parser = subparsers.add_parser("test", help="运行测试套件")
    test_parser.add_argument("pytest_args", nargs="*", help="传递给 pytest 的额外参数")

    # 构建检查命令
    build_parser = subparsers.add_parser("build", help="运行构建前检查")
    build_parser.add_argument(
        "--no-dry-run", action="store_true", help="实际修改文件（默认是 dry-run 模式）"
    )

    # 版本命令
    subparsers.add_parser("version", help="显示版本信息")

    return parser


def main() -> int:
    """主函数"""
    parser = create_parser()
    args = parser.parse_args()

    # 设置日志
    setup_logging(args.verbose)

    # 如果没有指定命令，显示帮助信息
    if not args.command:
        parser.print_help()
        return constants.EXIT_SUCCESS

    try:
        if args.command == "ci":
            run_precommit_check()
            return run_ci_pipeline()

        elif args.command == "precommit":
            return run_precommit_check()

        elif args.command == "test":
            return run_tests(args.pytest_args if hasattr(args, "pytest_args") else None)

        elif args.command == "build":
            dry_run = not args.no_dry_run
            return run_build_check(dry_run)

        elif args.command == "version":
            show_version()
            return constants.EXIT_SUCCESS

    except KeyboardInterrupt:
        print("\n✋ 操作被用户中断")
        return 130  # SIGINT 的标准退出码
    except Exception as e:
        print(f"❌ 执行命令时发生错误: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return constants.EXIT_GENERAL_ERROR

    return constants.EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
