# SparkWeave CLI Skill

> Teach your AI agent to configure, manage, and use SparkWeave — an intelligent learning platform — entirely through the command line.

## When to Use

Use this skill when the user wants to:
- Set up or configure SparkWeave
- Chat with SparkWeave or run a capability (deep solve, quiz generation, deep research, math animation)
- Create, manage, or search knowledge bases
- Manage SparkBot instances
- View or manage learning memory, sessions, or notebooks
- Start the SparkWeave API server

## Prerequisites

- Python 3.11+
- SparkWeave installed: `pip install -e .` (core) or `pip install -e ".[server]"` (with web)
- Run `python scripts/start_tour.py` for first-time interactive setup (configures LLM, embedding, search providers and writes `.env`)

## Commands

### Chat & Capabilities

```bash
# Interactive REPL
sparkweave chat
sparkweave chat --capability deep_solve --kb my-kb --tool rag --tool web_search

# One-shot capability execution
sparkweave run chat "Explain Fourier transform"
sparkweave run deep_solve "Solve x^2 = 4" --tool rag --kb textbook
sparkweave run deep_question "Linear algebra" --config num_questions=5
sparkweave run deep_research "Attention mechanisms" --kb papers
sparkweave run math_animator "Visualize a Fourier series"

# Options for `run`:
#   --session <id>         Resume existing session
#   --tool/-t <name>       Enable tool (repeatable): rag, web_search, code_execution, reason, brainstorm, paper_search
#   --kb <name>            Knowledge base (repeatable)
#   --notebook-ref <ref>   Notebook reference (repeatable)
#   --history-ref <id>     Referenced session id (repeatable)
#   --language/-l <code>   Response language (default: en)
#   --config <key=value>   Capability config (repeatable)
#   --config-json <json>   Capability config as JSON
#   --format/-f <fmt>      Output format: rich | json
```

### Knowledge Bases

```bash
sparkweave kb list                              # List all knowledge bases
sparkweave kb info <name>                       # Show knowledge base details
sparkweave kb create <name> --doc file.pdf      # Create from documents (--doc repeatable)
sparkweave kb add <name> --doc more.pdf         # Add documents incrementally
sparkweave kb search <name> "query text"        # Search a knowledge base
sparkweave kb set-default <name>                # Set as default KB
sparkweave kb delete <name> [--force]           # Delete a knowledge base
```

### SparkBot

```bash
sparkweave bot list                             # List all SparkBot instances
sparkweave bot create <id> --name "My Tutor"    # Create and start a new bot
sparkweave bot start <id>                       # Start a bot
sparkweave bot stop <id>                        # Stop a bot
```

### Memory

```bash
sparkweave memory show [summary|profile|all]    # View learning memory
sparkweave memory clear [summary|profile|all]   # Clear memory (--force to skip confirm)
```

### Sessions

```bash
sparkweave session list [--limit 20]            # List sessions
sparkweave session show <id>                    # View session messages
sparkweave session open <id>                    # Resume session in REPL
sparkweave session rename <id> --title "..."    # Rename a session
sparkweave session delete <id>                  # Delete a session
```

### Notebooks

```bash
sparkweave notebook list                        # List notebooks
sparkweave notebook create <name>               # Create a notebook
sparkweave notebook show <id>                   # View notebook records
sparkweave notebook add-md <id> <file.md>       # Import markdown as record
sparkweave notebook replace-md <id> <rec> <f>   # Replace a markdown record
sparkweave notebook remove-record <id> <rec>    # Remove a record
```

### System

```bash
sparkweave config show                          # Print current configuration
sparkweave plugin list                          # List registered tools and capabilities
sparkweave plugin info <name>                   # Show tool/capability details
sparkweave provider login <provider>            # OAuth login (openai-codex, github-copilot)
sparkweave serve [--port 8001] [--reload]       # Start API server
```

## REPL Slash Commands

Inside `sparkweave chat`, use these:

| Command | Effect |
|:---|:---|
| `/quit` | Exit REPL |
| `/session` | Show current session id |
| `/new` | Start a new session |
| `/tool on\|off <name>` | Toggle a tool |
| `/cap <name>` | Switch capability |
| `/kb <name>\|none` | Set or clear knowledge base |
| `/history add <id>` / `/history clear` | Manage history references |
| `/notebook add <ref>` / `/notebook clear` | Manage notebook references |
| `/refs` | Show active references |
| `/config show\|set\|clear` | Manage capability config |

## Typical Workflows

**First-time setup:**
```bash
cd SparkWeave
pip install -e ".[server]"
python scripts/start_tour.py    # Interactive guided setup
```

**Daily learning:**
```bash
sparkweave chat --kb textbook --tool rag --tool web_search
```

**Build a knowledge base from documents:**
```bash
sparkweave kb create physics --doc ch1.pdf --doc ch2.pdf
sparkweave run chat "Explain Newton's third law" --kb physics --tool rag
```

**Generate quiz questions:**
```bash
sparkweave run deep_question "Thermodynamics" --kb physics --config num_questions=5
```

