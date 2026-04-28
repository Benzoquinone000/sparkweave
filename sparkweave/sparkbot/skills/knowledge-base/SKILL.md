---
name: knowledge-base
description: "Manage SparkWeave knowledge bases — list, create, search, add documents, delete."
metadata: {"nanobot":{"emoji":"📚","requires":{"bins":["sparkweave"]}}}
always: false
---

# Knowledge Base Management

Use the `exec` tool to manage SparkWeave knowledge bases via CLI.

## When to Use

- User asks about their **knowledge bases** or **study materials**
- User wants to **create**, **search**, or **manage** a knowledge base
- User needs to **add documents** to an existing KB

## Commands

### List all knowledge bases

```bash
sparkweave kb list --format json
```

> `--format json` outputs machine-readable JSON instead of a Rich table.

### Get info about a knowledge base

```bash
sparkweave kb info <kb_name>
```

### Create a knowledge base

```bash
sparkweave kb create <kb_name> --doc /path/to/file.pdf
sparkweave kb create <kb_name> --docs-dir /path/to/directory/
```

### Add documents to existing KB

```bash
sparkweave kb add <kb_name> --doc /path/to/new_file.pdf
```

### Search a knowledge base

```bash
sparkweave kb search <kb_name> "<query>" --format json
```

### Set a default knowledge base

```bash
sparkweave kb set-default <kb_name>
```

### Delete a knowledge base

```bash
sparkweave kb delete <kb_name> --force
```

## Tips

- Use `kb list` first to see what's available before searching.
- The `rag` tool can also search KBs directly within the conversation — use it for quick lookups.
- KB creation from large PDFs can take a few minutes.
- Always confirm with the user before deleting a knowledge base.

