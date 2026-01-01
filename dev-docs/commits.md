# Conventional Commits

Conventional Commits 的规范是一套轻量级、结构化的 Git 提交信息格式，旨在让提交历史对人类和机器都更易读，并便于自动生成变更日志和版本号。其基本格式如下：

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### 1. 类型（type）

必须，用于说明提交的性质，常见类型包括：

- `feat`：新增功能（对应 SemVer 的 MINOR）
- `fix`：修复 Bug（对应 SemVer 的 PATCH）
- `docs`：仅文档变更
- `style`：代码格式变动（如空格、分号），不改变逻辑
- `refactor`：重构代码，不新增功能也不修复 Bug
- `perf`：性能优化
- `test`：增加或修改测试
- `build`：构建系统或依赖变动
- `ci`：CI 配置变动
- `chore`：其他不修改业务代码的杂项
- `revert`：撤销某次提交

### 2. 可选范围（scope）

用括号标注影响的模块或文件，如 `feat(auth): ...` 。

### 3. 描述（description）

简短祈使句，首字母小写，不超过 50 字符，如 `add OAuth2 login flow` 。

### 4. 可选正文（body）

用于补充“为什么”与“做了什么”，多行时空行分隔 。

### 5. 可选脚注（footer）

可引用 Issue 或标注 BREAKING CHANGE。两种写法：

- 在类型后加 `!` 表示不兼容变更：
  `feat!: drop support for Node 6`
- 或在脚注显式声明：

  ```
  BREAKING CHANGE: 删除了 xxx API
  ```

示例：

```
feat(api): add rate-limit middleware

BREAKING CHANGE: 请求头字段由 X-Rate-Limit 改为 RateLimit
Closes #42
```

遵守该规范后，配合工具可自动生成 CHANGELOG、语义化版本号及发布说明 。
