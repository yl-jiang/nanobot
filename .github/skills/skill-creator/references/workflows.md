# Skill Design Patterns and Reference

This document provides detailed specifications for `SKILL.md` files, including frontmatter, argument substitution, and advanced patterns.

---

## 1. Frontmatter Reference

All fields are optional, but `description` is highly recommended.

| Field | Required | Description |
| :--- | :--- | :--- |
| `name` | No | Display name for the skill. Becomes the `/slash-command`. If omitted, uses the directory name. Lowercase letters, numbers, and hyphens only. |
| `description` | Recommended | What the skill does and when to use it. The AI uses this to decide when to apply the skill automatically. |
| `argument-hint` | No | Hint shown during autocomplete to indicate expected arguments. Example: `[issue-number]` or `[filename]`. |
| `disable-model-invocation` | No | Set to `true` to prevent the AI from automatically loading this skill. Use for workflows you only want to trigger manually (e.g., `/deploy`). Default: `false`. |
| `user-invocable` | No | Set to `false` to hide from the `/` menu. Use for background knowledge skills users shouldn't invoke directly. Default: `true`. |
| `allowed-tools` | No | A comma-separated list of tools the AI can use without asking for permission when this skill is active. Example: `read_file, glob`. |
| `model` | No | The specific AI model to use when this skill is active. |
| `context` | No | Set to `fork` to run the skill in an isolated subagent context, without access to your main conversation history. |
| `agent` | No | Specifies which subagent type to use when `context: fork` is set (e.g., `Explore`, `Plan`). |
| `hooks` | No | For advanced lifecycle integrations. See official docs for details. |

---

## 2. Argument and Variable Substitution

Skills support string substitution for dynamic values in the skill content.

| Variable | Description |
| :--- | :--- |
| `$ARGUMENTS` | All arguments passed when invoking the skill. |
| `$ARGUMENTS[N]` | Access a specific argument by its 0-based index, e.g., `$ARGUMENTS[0]`. |
| `$N` | Shorthand for `$ARGUMENTS[N]`, e.g., `$0` for the first argument. |
| `${CLAUDE_SESSION_ID}` | The current session ID. Useful for creating session-specific temporary files. |

**Example:**
A skill with `name: fix-issue` and content `Fix GitHub issue $ARGUMENTS...` when invoked as `/fix-issue 123` will result in the prompt "Fix GitHub issue 123...".

---

## 3. Advanced Patterns

### Dynamic Context Injection (`!command`)

Use the `!command` syntax to run a shell command *before* the skill is sent to the AI. The command's output replaces the placeholder. This is for pre-populating the prompt with live data.

**Example:**
```yaml
---
name: pr-summary
description: Summarize changes in a pull request
---

## Pull request context
- PR diff: !`gh pr diff`
- Changed files: !`gh pr diff --name-only`

## Your task
Summarize this pull request...
```
When this skill runs, the `gh` commands are executed first, and their output is injected into the prompt that the AI sees.

### Isolated Execution (`context: fork`)

Add `context: fork` to the frontmatter to run a skill in a completely isolated environment (a "subagent"). This is useful for complex tasks that shouldn't be influenced by the ongoing conversation history. The skill's instructions become the subagent's primary goal.

**Example:**
```yaml
---
name: deep-research
description: Research a topic thoroughly in the codebase
context: fork
agent: Explore
---

Research $ARGUMENTS thoroughly:

1. Find relevant files using `glob` and `search_file_content`.
2. Read and analyze the code.
3. Summarize findings with specific file references.
```
When invoked, this skill starts a new "Explore" agent (which has read-only filesystem tools) and gives it the task of researching the arguments. The result is then returned to the main conversation.
