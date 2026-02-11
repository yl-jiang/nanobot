---
name: git-commit
description: 执行 git commit 和 push 操作，遵循 Conventional Commits 规范。提交前必须与用户确认 commit message 内容。
---

# Git Commit & Push Skill

协助用户完成 git 提交和推送，确保提交信息规范且经过用户确认。

## 工作流程

### 1. 检查仓库状态

```bash
git status && git diff --stat
```

- 确认有待提交的更改
- 展示变更文件列表和统计

### 2. 分析变更内容

- 查看 `git diff` 理解具体修改
- 根据变更内容判断提交类型

### 3. 生成 Commit Message

遵循 Conventional Commits 规范：

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

**Type 选项:**
| Type | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 bug |
| `docs` | 文档变更 |
| `style` | 代码格式（不影响逻辑） |
| `refactor` | 重构（非新功能、非修复） |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `chore` | 构建/工具变更 |

**规则:**
- subject 使用祈使句，首字母小写，不加句号
- body 解释"为什么"而非"做了什么"
- 破坏性变更在 footer 添加 `BREAKING CHANGE:`

### 4. 用户确认（必须）

**向用户展示生成的 commit message，使用 `ask_user` 工具确认：**

```
建议的 commit message:

<type>(<scope>): <subject>

<body>

确认此提交信息？
- 确认并提交
- 修改 (请说明修改内容)
- 取消
```

⚠️ **未经用户确认，禁止执行 `git commit`**

### 5. 执行提交

用户确认后：

```bash
git add -A && git commit -m "<confirmed message>"
```

### 6. 推送（可选）

询问用户是否推送：

```bash
git push origin <current-branch>
```

推送失败时：
- 检查远程状态
- 建议 `git pull --rebase` 后重试
- 最多重试 3 次

## 约束

- **必须** 在提交前获得用户对 commit message 的确认
- **必须** 检查是否有未暂存的更改
- **禁止** 提交包含敏感信息的内容
- **禁止** 强制推送 (`--force`) 除非用户明确要求

## 示例交互

**用户:** 帮我提交这些更改

**助手:**
```
当前变更:
- M  src/utils.py (添加日志功能)
- A  tests/test_utils.py (新增测试)

建议的 commit message:

feat(utils): add logging functionality

- Add structured logging to utils module
- Include corresponding unit tests

确认此提交信息？
```

**用户:** 确认

**助手:**
```bash
git add -A && git commit -m "feat(utils): add logging functionality

- Add structured logging to utils module
- Include corresponding unit tests"
```
