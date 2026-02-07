---
name: optimize-flow
description: 经验沉淀与避坑记录。当用户说"记住这个坑"、"记录经验"、"别再踩坑"等触发词时，将问题解决经验持久化到 experience/ 目录，供后续 AI 参考避雷。
---

# Experience Log Skill

将问题解决经验沉淀为可复用的知识库，避免 AI 重复踩坑。

## 触发词

- "记住这个坑"
- "记录经验" / "记录这个经验"
- "别再踩坑" / "避免踩坑"
- "沉淀一下" / "总结经验"
- "remember this" / "log this experience"

## 工作流程

### 1. 初始化目录

检查并创建 `experience/` 目录（项目根目录下）：

```bash
mkdir -p experience
```

### 2. 提取经验要素

从当前会话上下文中提取：

| 要素 | 说明 |
|------|------|
| **问题现象** | 遇到的错误/异常/非预期行为 |
| **根因分析** | 问题的本质原因 |
| **解决方案** | 具体的修复步骤 |
| **避坑要点** | 如何提前规避此问题 |
| **相关文件** | 涉及的代码/配置文件 |
| **标签** | 分类标签（如 `git`, `python`, `config` 等） |

### 3. 生成经验文档

文件命名：`experience/YYYY-MM-DD_<slug>.md`

模板：

```markdown
# <简短标题>

**日期:** YYYY-MM-DD
**标签:** `tag1`, `tag2`

## 问题现象

<描述遇到的问题>

## 根因分析

<分析问题的根本原因>

## 解决方案

<具体解决步骤>

## 避坑要点

- <要点1>
- <要点2>

## 相关文件

- `path/to/file`
```

### 4. 用户确认

使用 `ask_user` 展示生成的经验文档：

```
已提取以下经验，确认保存？

---
[经验文档预览]
---

- 确认保存
- 修改内容
- 取消
```

### 5. 写入文件

用户确认后，使用 `create` 工具写入 `experience/` 目录。

### 6. 更新索引（可选）

如果 `experience/README.md` 存在，追加新条目到索引列表。

## 查阅经验

当开始新任务时，AI 应主动检查 `experience/` 目录：

```bash
ls experience/ 2>/dev/null && head -20 experience/*.md
```

根据任务相关性，参考已有经验避免重复踩坑。

## 约束

- **必须** 获得用户确认后才写入文件
- **必须** 包含问题现象和解决方案（最小完整记录）
- **建议** 添加标签便于后续检索
- **禁止** 记录包含敏感信息的内容（密钥、密码等）

## 示例

**用户:** 终于解决了，记住这个坑

**助手:**

已提取以下经验，确认保存？

---
```markdown
# Git submodule 更新后分支丢失

**日期:** 2026-01-28
**标签:** `git`, `submodule`

## 问题现象

执行 `git submodule update` 后，子模块处于 detached HEAD 状态，本地修改丢失。

## 根因分析

`git submodule update` 默认 checkout 到父仓库记录的 commit，而非跟踪分支。

## 解决方案

使用 `--remote --merge` 参数：
```bash
git submodule update --remote --merge
```

## 避坑要点

- 更新子模块前先确认当前分支
- 使用 `git submodule foreach git status` 检查状态
- 考虑配置 `submodule.<name>.branch`

## 相关文件

- `.gitmodules`
```
---

确认保存到 `experience/2026-01-28_git-submodule-detached-head.md`？
