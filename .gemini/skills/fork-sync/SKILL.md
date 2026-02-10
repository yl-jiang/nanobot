---
name: fork-sync
description: Compares the current project with an upstream repository, then proposes and executes a file-by-file merge of beneficial changes.
disable-model-invocation: true
argument-hint: [path-to-upstream-repo]
allowed-tools: run_shell_command(diff *, ls *, cd *, cat *, echo *), read_file, write_file, replace
---

# Instructions for Fork Synchronization

This skill automates the process of comparing a forked repository (the current project) with its upstream source and selectively merging beneficial changes. It guides the user through a file-by-file analysis, proposing merge actions for each difference and executing them upon user approval.

### Phase 1: Setup and Discovery

1.  **Identify Repositories:**
    *   The user's forked repository is the current working directory.
    *   The path to the upstream (official) repository is provided as an argument. Use `$ARGUMENTS[0]` to get this path.
    *   If `$ARGUMENTS[0]` is empty, stop and inform the user that the upstream repository path is required.

2.  **Initial Comparison:**
    *   Use `diff -rq` to perform an initial comparison between the two repository paths.
    *   Exclude common directories that are expected to differ, such as `.git`, `.venv`, `.vscode`, `__pycache__`, and any agent-specific planning files (`findings.md`, etc.).
    *   Example command: `diff -rq --exclude=".git" --exclude=".venv" --exclude="__pycache__" . "$ARGUMENTS[0]" > diff_output.txt`
    *   Read the output file.

3.  **Categorize Differences:**
    *   Process the `diff` output and create three lists:
        1.  **User-Only Files:** Files/directories existing only in the user's fork.
        2.  **Upstream-Only Files:** Files/directories existing only in the upstream repository.
        3.  **Modified Files:** Files that exist in both but have different content.
    *   Present a summary of these categories to the user.

### Phase 2: Iterative Merge Loop

Begin iterating through the "Modified Files" and "Upstream-Only Files" lists. For each file, follow this sub-process:

1.  **Announce File:** Inform the user which file you are now analyzing (e.g., "Next, we will analyze `path/to/file.py`.").

2.  **Analyze Differences:**
    *   **For Modified Files:** Read both versions of the file (user's and upstream's).
    *   **For Upstream-Only Files:** Read the upstream version of the file.
    *   Perform a careful comparison to understand the nature of the changes (bug fix, new feature, security patch, user customization, etc.).

3.  **Formulate Merge Recommendation:**
    *   Based on your analysis, decide on the best course of action and clearly explain your reasoning to the user. Common scenarios:
        *   **Keep User's Version:** If the user's file has significant custom features not present in the upstream version.
        *   **Merge from Upstream:** If the upstream file contains clear improvements (e.g., a security fix, new dependencies).
        *   **Partial Merge:** If both files contain valuable, non-conflicting changes.
        *   **Create New File:** For "Upstream-Only Files," recommend creating the new file in the user's repository.

4.  **Request User Confirmation:**
    *   Clearly state your proposed action and ask for the user's approval.

5.  **Execute Action:**
    *   If the user agrees, use the appropriate tool (`replace`, `write_file`) to perform the merge.
    *   If the user disagrees or says to skip, do nothing and move to the next file.

### Phase 3: Finalization

1.  **Completion Message:** Once all files have been processed, inform the user that the synchronization process is complete.
2.  **Suggest Next Steps:** If any dependency files (like `pyproject.toml`) were modified, remind the user to run the appropriate command to install/update their dependencies.