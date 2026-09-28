---
name: record-demo
description: Use when creating an automated product demo recording, browser walkthrough, or synchronized narration video with Playwright and Qwen3-TTS voice cloning.
---

# Skill: Automated Product Demo Recording

**Read `SKILL.md` at the root of this repository before doing anything.** It holds the
full protocol, the runtime file list, requirements, and troubleshooting notes.

Do not rely on this file for the procedure. It exists only so the skill is discoverable
when Claude Code is started inside this repository. When the skill is installed as a
personal skill at `~/.claude/skills/record-demo`, `SKILL.md` at that root is the entry
point instead, and this file is not present.

## Two things worth knowing up front

- `SKILL.md` refers to bundled files through `${CLAUDE_SKILL_DIR}`. Keep that substitution
  so the same instructions work from a personal install, a project clone, or a plugin.
- The reference voice at `assets/reference_voice.wav` is required and is personal data.
  If it is missing, ask the user to record a 5–12 second sample before continuing. Do not
  substitute a system voice.
