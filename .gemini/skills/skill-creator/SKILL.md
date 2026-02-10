---
name: skill-creator
description: Guide for creating effective skills. Use when a user wants to create a new skill or update an existing one.
---

# Skill Creator

This skill guides the creation of effective, well-structured skills, following official best practices.

## Core Principles

1.  **Be Concise**: The AI is already smart. Only add knowledge it doesn't have.
2.  **Use Progressive Disclosure**: Keep `SKILL.md` as a high-level guide. Move detailed documentation, schemas, or examples into `references/` files and link to them.
3.  **Define a Clear Interface**: Use the YAML frontmatter to define a skill's name, description, and behavior. This is critical for the AI to know when and how to use the skill.

## Skill Creation Workflow

Follow these steps to create a new skill.

### Step 1: Understand the Goal

- Clarify the skill's purpose with the user.
- Ask for concrete examples of how the skill will be used.
- Example Questions: "What should this skill accomplish?", "Can you give an example of a command or request that would use this skill?".

### Step 2: Plan the Skill's Resources

- Based on the examples, determine what resources the skill will need.
- **Scripts (`scripts/`)**: For reusable, deterministic logic (e.g., a Python script to parse a file).
- **References (`references/`)**: For detailed documentation the AI should read (e.g., API specs, style guides).
- **Assets (`assets/`)**: For files used in the skill's output (e.g., project templates, images).

### Step 3: Initialize the Skill Directory

- Use the `init_skill.py` script from this `skill-creator` skill's own `scripts/` directory to create the basic file structure.
- Command: `python .gemini/skills/skill-creator/scripts/init_skill.py <skill-name> --path .gemini/skills`
- This creates the skill directory, a template `SKILL.md`, and the `scripts/`, `references/`, and `assets/` subdirectories.

### Step 4: Implement the Skill

1.  **Implement Resources**: Create the scripts, reference files, and assets identified in Step 2. Test any scripts to ensure they work correctly.

2.  **Write SKILL.md**: This is the most important part.
    *   **YAML Frontmatter**: This is the skill's "control panel".
        *   `name`: The `/slash-command` for the skill.
        *   `description`: **Crucial for auto-triggering.** Clearly explain what the skill does and when to use it.
        *   **Important Fields**: Consider using `disable-model-invocation: true` for manual-only skills, `allowed-tools` for smoother execution, and `context: fork` for isolated tasks.
        *   **For a complete guide to all frontmatter fields, argument variables, and advanced patterns, read this skill's reference document: [references/workflows.md](references/workflows.md)**.
    *   **Body (Markdown)**: Write clear, step-by-step instructions for the AI to follow when the skill is invoked. Reference the resources you created.

### Step 5: Package and Test

- When the skill is complete, package it using the `package_skill.py` script.
- Command: `python .gemini/skills/skill-creator/scripts/package_skill.py .gemini/skills/<skill-name>`
- Test the skill by invoking it directly (`/skill-name`) or by giving a prompt that matches its description.

### Step 6: Iterate

- Based on usage, refine the skill's instructions, resources, or frontmatter to improve its performance and reliability.