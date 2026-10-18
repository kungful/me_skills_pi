---
name: internalcot
description: 开启 InternalCoT 可见思维链模式：在每次实质工具调用和回答前，必须先写 internalcot CLI 笔记，整个会话持续生效。仅当用户明确说"$internalcot / internalcot on / 开 internalcot"时才用；用户只是说"仔细想 / 深入推理 / 展示思路"不算触发。用户明确关闭前保持激活。Activate a persistent visible-reasoning mode that requires detailed internalcot CLI notes before substantive tools and answers, throughout the conversation.
---

# InternalCoT

Install the CLI and this skill together with:

```bash
npx internalcot@latest setup
```

This file is a stable discovery skill. The installed CLI owns the version-matched workflow instructions.

## Load the current workflow

When this skill is invoked:

1. Prefer the persistent CLI and run this standalone command before substantive work:

   ```bash
   internalcot skill
   ```

2. If that command is unavailable or does not support `skill`, load the same workflow without installing anything globally:

   ```bash
   npx --yes internalcot@latest skill --npx
   ```

3. Treat the returned Markdown as mandatory instructions for the selected CLI version. Follow every required note call for the current conversation, including any substantive task in the invocation message; do not replace the workflow with ordinary commentary or a shorter summary.
4. If both commands fail, do not improvise an older workflow or claim the mode is active. Give the exact recovery command `npx internalcot@latest setup`.
