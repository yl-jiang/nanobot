# Git 历史清理敏感信息指南

当敏感信息（如 API key）被提交到 Git 历史后，即使后续删除，历史记录中仍可恢复。本文档记录如何彻底清理。

## 场景

```
... ← 18ec651 ← 9ad720c ← 5c85c06 (HEAD)
        ↑          ↑          ↑
      (干净)   (有API key)  (删除API key)
```

目标：彻底删除 `9ad720c` 中的敏感信息。

## 操作步骤

### 1. Soft Reset 到干净的提交

```bash
git reset --soft 18ec651
```

**效果**：HEAD 移动到 `18ec651`，但**工作目录和暂存区保持当前最新状态**（不丢失任何代码）。

```
18ec651 (HEAD)     9ad720c → 5c85c06
    ↑                  ↑
 分支指针         变成孤儿提交（无引用）
 
工作目录: 仍是最新代码
```

### 2. 创建新的干净提交

```bash
git commit -m "feat: 新的提交信息"
```

**效果**：在 `18ec651` 之后创建新提交，包含当前所有代码。

```
18ec651 ← 新提交 (HEAD)
              ↑
        包含最新代码（已清理）
```

### 3. 清理 Reflog 和垃圾回收

```bash
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

**作用**：
- `reflog expire`：清除对旧提交的引用记录（否则可通过 `git checkout HEAD@{n}` 恢复）
- `gc --prune=now`：立即删除无引用的对象

### 4. 强制推送

```bash
git push --force origin main
```

**⚠️ 注意**：这会覆盖远程历史，其他协作者需要 `git pull --rebase`。

## 验证

```bash
git log --all -p -- '文件路径' | grep -c "敏感信息"
# 输出 0 表示已彻底清理
```

## 关键概念

| 命令 | 作用 |
|------|------|
| `git reset --soft` | 只移动 HEAD，不改变文件 |
| `git reflog` | Git 的"后悔药"，记录所有 HEAD 移动 |
| `git gc --prune` | 删除无引用的对象 |

## 后续建议

1. **立即废弃泄露的密钥**
2. **使用环境变量**存储敏感信息
3. **添加 `.gitignore`** 防止再次误提交
