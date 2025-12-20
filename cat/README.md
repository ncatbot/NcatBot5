# CI / pre-commit 工具（简洁包装）

`cat` 目录下提供用于 CI 与本地提交的简洁包装脚本，目标是把 GitHub Actions / pre-commit 中的步骤保持最小化、可复用。

包含脚本

- `hatch_hooks.py`：pre-build 钩子实现（License 年份、版权更新、版本变更检查）。
- `ci.py`：CI wrapper（入口 `python -m cat.ci`）——运行测试并以 dry-run 方式运行 pre-build 钩子，便于在 workflow 中只用一条命令完成主要验证。
- `precommit.py`：本地 pre-commit 脚本（入口 `python -m cat.precommit`）——运行测试、requirements/pyproject 同步检查、并以 dry-run 方式运行 pre-build 钩子，用于阻止不符合要求的提交。

快速使用

- 在 GitHub Actions 中：已配置 workflow 调用 `python -m cat.ci`（详见 `.github/workflows/pre_build.yml`）。
- 在本地：安装 `pre-commit`，然后运行 `pre-commit install` 即可在每次提交前自动调用 `python -m cat.precommit`。
自动修复（格式化/修复）

- 已在 `.pre-commit-config.yaml` 中增加自动修复工具：`black`、`isort`、`ruff` 等会在提交时自动修复格式问题。
- 本地手动修复（对仓库所有文件）可运行：

  ```bash
  scripts/run_precommit_all.sh
  ```

- 安装并启用 pre-commit（一次性）：

  ```bash
  scripts/install_precommit.sh
  ```

环境变量

- `HC_DRY_RUN=1`：使 pre-build 钩子以干运行模式，不会修改文件。
- `FCAT_SKIP_TESTS=1`：在单元测试中使用，跳过执行 pytest（用于避免在测试中嵌套运行 pytest）。

注：这些脚本旨在作为最小包装器用于 CI 与本地自动化，减少 workflow/钩子中的详细描述并一致化行为。
