---
name: memory
description: Three-file shared memory system (SUMMARY, PROFILE, SOUL).
always: true
---

# Memory

SparkBot shares a three-file memory system with SparkWeave. These files persist across sessions and are automatically loaded into your context.

## Structure

| File | Purpose | Loaded |
|------|---------|--------|
| `SUMMARY.md` | Chronological log of all interactions (both SparkWeave and SparkBot) | Yes |
| `PROFILE.md` | User identity, preferences, and recurring patterns extracted from conversations | Yes |
| `SOUL.md` | SparkBot's persona and personality configuration | Yes |

## When to Update

### PROFILE.md
Write important user facts immediately using `edit_file`:
- User preferences ("prefers Chinese responses")
- Background info ("PhD student in computer science")
- Learning context ("studying for linear algebra exam")

### SUMMARY.md
Append notable events or session summaries. Entries should start with `[YYYY-MM-DD HH:MM]`.

### SOUL.md
Only modify if the user explicitly asks to change SparkBot's personality or behavior.

## Searching Memory

For quick lookups in SUMMARY.md:
```bash
grep -i "keyword" memory/SUMMARY.md
```

Or use `read_file` for small files.

## Auto-consolidation

Old conversations are automatically summarized and appended to SUMMARY.md when the session grows large. Long-term user facts are extracted to PROFILE.md. You don't need to manage this manually.
