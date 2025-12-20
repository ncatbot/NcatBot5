"""本地 pre-commit 检查脚本（供 pre-commit 或手动调用）

功能：
- 运行快速测试（pytest）
- 检查 requirements 与 pyproject 是否同步
- 运行 pre-build 钩子（dry-run），确保版本等检查通过

该脚本在本地提交前运行，遇到错误将以非 0 退出，阻止提交。
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Sequence

from cat import hatch_hooks


def _sync_requirements_to_pyproject(auto_fix: bool = True) -> bool:
    """确保 requirements.txt 的依赖至少出现在 pyproject.toml 的 dependencies 中。

    当 auto_fix 为 True 时，会自动把缺失的依赖写入 pyproject.toml 并返回 True（表示有变更）；
    否则只返回是否一致（False 表示发现缺失）。
    """
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
    start = data.find("dependencies = [")
    if start == -1:
        # 未找到 dependencies 块，无法自动修复
        print("pyproject.toml 中未找到 dependencies 块，无法同步", file=sys.stderr)
        return False

    start_br = data.find("[", start)
    end_br = data.find("]", start_br)
    deps_block = data[start_br + 1 : end_br]

    py_deps = []
    for item in deps_block.splitlines():
        item = item.strip().rstrip(",")
        if not item:
            continue
        item = item.strip(" '\"\n")
        py_deps.append(item)

    missing = [r for r in reqs if r not in py_deps]
    if not missing:
        return True

    if not auto_fix:
        print("以下 requirements 未同步到 pyproject.toml 的 dependencies：", file=sys.stderr)
        for m in missing:
            print("  - ", m, file=sys.stderr)
        return False

    # 自动修复：把缺失的依赖按行追加到 dependencies 列表中
    new_deps_lines = []
    for line in deps_block.splitlines():
        new_deps_lines.append(line)
    # append missing items with proper quoting
    for m in missing:
        new_deps_lines.append(f'    "{m}",')

    new_deps_block = "\n".join(new_deps_lines)
    new_data = data[: start_br + 1] + "\n" + new_deps_block + "\n" + data[end_br:]

    with open("pyproject.toml", "w", encoding="utf-8") as fh:
        fh.write(new_data)

    print("已将缺失的依赖添加到 pyproject.toml 的 dependencies：", missing)

    # 尝试 git add pyproject.toml（若在 git 仓库中）
    try:
        subprocess.call(["git", "add", "pyproject.toml"])
    except Exception:
        pass

    return True


def _run_pytest(argv: Sequence[str] | None = None) -> int:
    # 本地测试时，如需跳过 pytest（例如单元测试中调用该脚本），可设置环境变量 FCAT_SKIP_TESTS=1
    if os.environ.get("FCAT_SKIP_TESTS") == "1":
        return 0

    args = ["-q"]
    if argv:
        args.extend(argv)
    return subprocess.call([sys.executable, "-m", "pytest"] + args)


def _bump_dev_version_in_meta() -> bool:
    """尝试在 `src/meta.py` 中将版本按 `{major}.{minor}.{patch}-dev.{n}` 的格式自增。

    返回 True 表示已修改文件（并尝试 git add），False 表示无法修改（例如解析失败）。
    """
    meta_path = hatch_hooks.META
    text = meta_path.read_text(encoding="utf-8")
    m = __import__("re").search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", text)
    if not m:
        return False
    ver = m.group(1)
    # 匹配 dev 格式
    dev_match = __import__("re").match(r"^(\d+)\.(\d+)\.(\d+)-dev\.(\d+)$", ver)
    if dev_match:
        major, minor, patch, dev = dev_match.groups()
        new_ver = f"{major}.{minor}.{patch}-dev.{int(dev)+1}"
    else:
        # 若不是 dev 格式但为 x.y.z，则附加 -dev.0
        semver_match = __import__("re").match(r"^(\d+)\.(\d+)\.(\d+)$", ver)
        if semver_match:
            major, minor, patch = semver_match.groups()
            new_ver = f"{major}.{minor}.{patch}-dev.0"
        else:
            # 无法解析
            return False

    new_text = text.replace(m.group(0), f'__version__ = "{new_ver}"')
    meta_path.write_text(new_text, encoding="utf-8")
    # 尝试 git add
    try:
        subprocess.call(["git", "add", str(meta_path)])
    except Exception:
        pass
    return True


def main() -> int:
    # 1) 运行测试
    rv = _run_pytest()
    if rv != 0:
        print("测试失败，阻止提交", file=sys.stderr)
        return rv

    # 2) 检查并自动同步 requirements 到 pyproject（本地自动修复）
    ok = _sync_requirements_to_pyproject(auto_fix=True)
    if not ok:
        print("requirements 与 pyproject 不一致，阻止提交", file=sys.stderr)
        return 2

    # 3) 运行构建前的检查/修复（将构建钩子移到提前检查并允许本地自动修复）
    try:
        # 以非 dry-run 模式运行，允许修改文件并在必要时进行 git add
        hatch_hooks._write_mit_license(dry_run=False)
        try:
            hatch_hooks._update_meta_copy_and_version_check(dry_run=False)
        except SystemExit as e:
            # 这里捕获版本相同导致的退出（code 2），并尝试自动 bump dev 号
            if getattr(e, "code", None) == 2:
                print("检测到版本与最新 tag 相同，尝试自动增加 dev 版本号...")
                if _bump_dev_version_in_meta():
                    print("已自动更新版本并提交变更（若在 git 仓库中）")
                    # 再次尝试更新 meta 的版权等信息
                    hatch_hooks._update_meta_copy_and_version_check(dry_run=False)
                else:
                    print("无法自动更新版本，阻止提交", file=sys.stderr)
                    return 4
            else:
                raise
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
