# Cat - 勤劳的自动化小猫 🐱

Cat 是一个轻量级 Python 项目自动化工具，帮助您自动处理版本管理、依赖同步、代码检查和构建验证等重复性任务。

## 🚀 快速开始

### 安装

```bash
# 从本地安装
pip install -e /path/to/cat-tool

# 或直接使用（无需安装）
python -m cat.cli --help
```

### 基本用法

```bash
# 查看所有命令
cat --help

# 运行完整检查（测试 + 代码检查 + 构建验证）
cat ci

# 提交代码前的自动修复
cat precommit

# 只运行测试
cat test

# 构建前验证
cat build

# 查看当前版本
cat version
```

## 📋 核心功能

### 1. 智能版本管理 🐾

自动检测版本号，避免重复：

```bash
# 当前版本: 1.2.3
# 最新Git标签: v1.2.3
# ➤ 自动升级为: 1.2.3-dev.0
```

### 2. 依赖自动同步 🔄

保持 `requirements.txt` 和 `pyproject.toml` 一致：

```bash
# 检测到 requirements.txt 有新增依赖
# ➤ 自动同步到 pyproject.toml
```

### 3. 版权年份更新 📅

自动更新版权年份：

```bash
# Copyright (c) 2023 Owner
# ➤ 自动更新为: Copyright (c) 2024 Owner
```

### 4. 一站式检查 ✅

单个命令完成所有检查：

```bash
cat ci
# 等效于:
# 1. 运行测试 (pytest)
# 2. 代码规范检查 (pre-commit)
# 3. 构建前验证 (版本检查、文件更新)
```

## 🔧 详细命令

### `cat ci` - 完整工作流

```bash
cat ci                    # 完整检查（推荐在CI中使用）
cat ci --verbose          # 显示详细过程

# 在CI环境中通常需要设置：
export HC_DRY_RUN=true    # 仅检查，不修改文件
cat ci
```

### `cat precommit` - 本地提交助手

```bash
cat precommit             # 自动修复所有问题
```

**自动执行：**

1. 运行测试，失败则阻止提交
2. 同步依赖到 pyproject.toml
3. 更新版权年份
4. 检查版本，必要时自动升级
5. 将修改的文件添加到Git暂存区

### `cat test` - 测试运行器

```bash
cat test                  # 运行所有测试
cat test tests/unit/      # 运行特定目录
cat test -k "api"         # 运行名称包含"api"的测试
cat test -v               # 显示详细输出
cat test --tb=short       # 简短错误回溯

# 跳过测试
export FCAT_SKIP_TESTS=1
cat test                  # 会直接跳过
```

### `cat build` - 构建验证

```bash
cat build                 # 检查模式（不修改文件）
cat build --no-dry-run    # 应用模式（实际修改文件）
```

**检查内容：**

- ✅ 许可证文件完整性
- ✅ 版权信息正确性
- ✅ 版本号与Git标签不冲突

### `cat version` - 版本信息

```bash
cat version
# 输出示例：
# 版本: 1.2.3-dev.0
# 最新标签: v1.2.2
# 版权: Copyright (c) 2024 Fcatbot Contributors
```

## ⚙️ 配置定制

### 环境变量

```bash
# 跳过某些步骤
export FCAT_SKIP_TESTS=1       # 跳过测试
export FCAT_SKIP_PRECOMMIT=1   # 跳过pre-commit

# 版本标签配置
export FCAT_PRERELEASE_LABEL=alpha  # 使用alpha而不是dev
export FCAT_COPYRIGHT_OWNER="我的公司"

# 正则表达式覆盖（高级）
export FCAT_PATTERN_VERSION='__version__ = "([^"]+)"'
```

### 版本标签说明

```python
# 默认：使用 -dev.N 作为开发版本
1.2.3 → 1.2.3-dev.0 → 1.2.3-dev.1

# 可配置为其他标签
export FCAT_PRERELEASE_LABEL=alpha
1.2.3 → 1.2.3-alpha.0 → 1.2.3-alpha.1

export FCAT_PRERELEASE_LABEL=rc
1.2.3 → 1.2.3-rc.0 → 1.2.3-rc.1
```

## 📁 文件结构要求

工具期望以下文件结构：

```
项目根目录/
├── src/
│   └── meta.py          # 必须：包含 __version__ 和 __copyright__
├── pyproject.toml       # 必须：项目配置
├── requirements.txt     # 可选：Python依赖
├── License.txt          # 可选：许可证文件
└── .pre-commit-config.yaml  # 可选：pre-commit配置
```

### `meta.py` 示例

```python
# src/meta.py
__version__ = "1.0.0"
__copyright__ = "Copyright (c) 2024 您的名字"
```

## 🔄 集成到工作流

### Git Hook 集成

```bash
# .git/hooks/pre-commit
#!/bin/sh
python -m cat.cli precommit
```

### Makefile 集成

```makefile
.PHONY: check
check:
 python -m cat.cli ci

.PHONY: test
test:
 python -m cat.cli test

.PHONY: precommit
precommit:
 python -m cat.cli precommit
```

### CI/CD 示例

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4

      - name: 安装依赖
        run: pip install -e .

      - name: 运行Cat检查
        run: python -m cat.cli ci
        env:
          HC_DRY_RUN: "true"
```

## 🐛 常见问题

### Q: 出现 "pre-commit 未安装" 错误

```bash
# 安装 pre-commit
pip install pre-commit

# 或跳过 pre-commit 检查
export FCAT_SKIP_PRECOMMIT=1
cat ci
```

### Q: 版本检查失败

检查以下几点：

1. 确保 `src/meta.py` 中有 `__version__`
2. 确保项目有 Git 标签：`git tag -a v1.0.0 -m "版本1.0.0"`
3. 版本号遵循语义化版本：主版本.次版本.修订号

### Q: 依赖同步失败

确保：

1. `requirements.txt` 文件存在
2. `pyproject.toml` 中有 `[project]` 和 `dependencies` 部分
3. 文件编码为 UTF-8

### Q: 如何在CI中跳过文件修改？

```bash
# CI环境中设置
export HC_DRY_RUN=true
cat ci  # 只检查，不修改文件
```

## 🎯 使用技巧

### 1. 开发工作流

```bash
# 日常开发循环
cat precommit  # 提交前自动修复
git commit -m "功能完成"

# 需要时手动触发
cat test       # 运行测试
cat build      # 检查构建准备
```

### 2. 版本发布工作流

```bash
# 1. 确保所有检查通过
cat ci

# 2. 移除开发标签
# 编辑 src/meta.py: 1.2.3-dev.5 → 1.2.3

# 3. 创建Git标签
git tag -a v1.2.3 -m "发布版本1.2.3"
git push --tags

# 4. 升级到下一个开发版本
# Cat会自动处理：1.2.3 → 1.2.4-dev.0
```

### 3. 临时跳过检查

```bash
# 快速提交（不推荐长期使用）
export FCAT_SKIP_TESTS=1
export FCAT_SKIP_PRECOMMIT=1
cat precommit
```

## 📊 退出码说明

| 退出码 | 含义 | 说明 |
|--------|------|------|
| 0 | 成功 | 所有检查通过 |
| 1 | 测试失败 | pytest 运行失败 |
| 2 | 版本冲突 | 版本号与Git标签相同 |
| 3 | 通用错误 | 其他未分类错误 |
| 4 | pre-commit 未安装 | 需要安装 pre-commit |
| 5 | 版本升级失败 | 无法解析或升级版本号 |

## 🤝 扩展开发

### 添加新检查

在 `processing.py` 中添加函数：

```python
def check_something(dry_run: bool = True) -> bool:
    """新的检查逻辑"""
    # 实现检查逻辑
    return True  # 返回是否通过
```

### 修改行为

通过环境变量配置：

```bash
# 使用不同的版本模式
export FCAT_PATTERN_VERSION='version = "([^"]+)"'
export FCAT_PRERELEASE_LABEL="beta"

# 自定义版权信息
export FCAT_COPYRIGHT_OWNER="我的团队"
```

## 📞 帮助与支持

```bash
# 查看详细帮助
cat --help
cat ci --help
cat precommit --help

# 查看当前配置
python -c "from cat import config; print('PRERELEASE_LABEL:', config.PRERELEASE_LABEL)"

# 调试模式
export FCAT_DEBUG=1
cat ci --verbose
```

---

**记住这只勤劳的小猫** 🐱 让它帮你处理那些重复的琐事，你可以更专注于创造性的工作！
