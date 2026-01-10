# Conventional Commits 规范

Conventional Commits 是一套轻量级、结构化且具有一致性的 Git 提交信息格式规范。它旨在使提交历史对人类和机器都更易阅读与处理，同时便于自动生成变更日志（CHANGELOG）和基于语义化版本（SemVer）的版本号管理。

## 为什么使用 Conventional Commits？

- **清晰可读的提交历史**：通过分类和结构化描述，快速了解每次提交的意图。
- **自动化变更日志**：工具可自动解析提交信息，生成格式统一的发布说明。
- **自动化版本管理**：根据提交类型（如 `feat`、`fix`、BREAKING CHANGE）自动确定下一版本号（遵循 SemVer）。
- **促进协作与审查**：标准化格式降低了团队沟通成本，便于代码审查和问题追溯。

---

## 提交信息结构

### 基本格式

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### 1. 类型（type）

**必须**，用于说明提交的性质。常见类型如下：

| 类型       | 说明                                                                 | 对应 SemVer |
|------------|----------------------------------------------------------------------|-------------|
| `feat`     | 新增功能或特性                                                       | MINOR       |
| `fix`      | 修复 Bug                                                            | PATCH       |
| `docs`     | 仅文档变更（如 README、API 文档）                                    | -           |
| `style`    | 代码格式变动（空格、分号、格式化等），不改变逻辑                     | -           |
| `refactor` | 重构代码，既不新增功能也不修复 Bug                                   | -           |
| `perf`     | 性能优化                                                             | PATCH       |
| `test`     | 增加或修改测试（单元测试、集成测试等）                               | -           |
| `build`    | 构建系统或外部依赖变动（如 webpack、npm、gulp）                      | -           |
| `ci`       | CI 配置或脚本变动（如 GitHub Actions、Jenkins）                      | -           |
| `chore`    | 其他不修改业务代码的杂项（如更新依赖、调整目录结构）                 | -           |
| `revert`   | 撤销某次提交                                                         | -           |

### 2. 可选范围（scope）

用括号标注，说明提交影响的具体模块、功能或文件，例如：

- `feat(auth): ...`
- `fix(api): ...`
- `docs(readme): ...`

### 3. 描述（description）

简短说明，使用祈使句、现在时，首字母小写，结尾不要加句号，长度建议不超过 50 个字符。
例如：`add user login validation`，而非 `added user login validation`。

### 4. 可选正文（body）

用于详细说明提交的动机、变更内容或与之前行为的对比。正文与描述之间用一个空行分隔，每行不超过 72 个字符。

### 5. 可选脚注（footer）

用于放置额外信息，例如：

- 关联的 Issue 或 Pull Request：`Closes #123`、`Fixes #456`
- 不兼容变更说明（BREAKING CHANGE）
- 影响范围或注意事项

---

## 不兼容变更（BREAKING CHANGE）

当提交中包含不向后兼容的变更时，必须在提交信息中明确标识。有两种标识方式：

### 方式一：在类型后添加 `!`

```
feat!: remove deprecated API endpoints
```

### 方式二：在脚注中显式声明

```
feat: update authentication method

BREAKING CHANGE: The `login()` method now requires a second argument.
```

---

## 完整示例

### 示例 1：包含不兼容变更的新功能

```
feat(api)!: migrate to GraphQL API

BREAKING CHANGE: REST endpoints are removed, use GraphQL queries instead.
Closes #789
```

### 示例 2：修复问题并关联 Issue

```
fix(ui): correct button alignment on mobile

- Adjust padding for small screens
- Fix hover state color

Fixes #123
```

### 示例 3：仅文档更新

```
docs: update installation guide for Windows
```

### 示例 4：重构与性能优化

```
refactor(db): simplify query builder logic

perf: reduce database round trips by caching schema
```

---

## 工具与自动化

采用 Conventional Commits 后，可配合以下工具提升效率：

- **[commitizen](https://github.com/commitizen/cz-cli)**：交互式生成符合规范的提交信息。
- **[commitlint](https://github.com/conventional-changelog/commitlint)**：校验提交信息格式。
- **[semantic-release](https://github.com/semantic-release/semantic-release)**：全自动版本管理与发布。
- **[standard-version](https://github.com/conventional-changelog/standard-version)**：自动生成 CHANGELOG 并升级版本号。
- **Git Hooks**：通过 `husky` 或 `pre-commit` 在提交前自动检查格式。

---

## 工作流建议

1. **分支策略**：推荐使用功能分支（feature branches）或基于主干的开发（trunk-based development）。
2. **提交频率**：小而频的提交，每个提交对应一个明确的变更。
3. **代码审查**：在合并前确保提交信息清晰、类型正确。
4. **发布流程**：利用自动化工具根据提交历史生成版本号和 CHANGELOG。

---

## 总结

Conventional Commits 通过一套简单清晰的约定，使提交历史成为项目可读、可维护的文档。它不仅提升了团队协作效率，还为自动化流程（如版本管理、发布说明生成）提供了可靠的基础。建议在项目中尽早引入并搭配相关工具，以充分发挥其价值。

> 参考： [Conventional Commits 官方规范](https://www.conventionalcommits.org/)
