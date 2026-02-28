# Create State Python SDK

**Version 0.1.25** | Built 2026-02-27 | [createstate.ai](https://createstate.ai)




**Give your AI coding assistant a persistent memory.**

Create State transforms AI coding assistants from forgetful tools into
persistent companions. Every insight, decision, and code pattern is captured
in a knowledge graph that grows smarter with every interaction.

```
+------------------+     +------------------+     +------------------+
|   Day 1          |     |   Week 1         |     |   Week 2+        |
|   AI knows       | --> |   AI remembers   | --> |   AI understands |
|   nothing        |     |   your decisions |     |   your codebase  |
+------------------+     +------------------+     +------------------+
```

**The Problem:** Every time you start a new chat with your AI assistant, it
forgets everything. Your architecture decisions, the bugs you've fixed, why
you chose that framework - all gone.

**The Solution:** Create State captures knowledge continuously and restores
it instantly. Your AI assistant picks up exactly where you left off, with
full context of your project's history.

## Requirements

- Python 3.9+
- **API key from [createstate.ai/web/api-keys](https://createstate.ai/web/api-keys)**
- Create State account (free trial available)

## Why Create State?

- **Persistent Memory** - Decisions, code patterns, and insights survive
  across sessions
- **Knowledge Graph** - Captures relationships between concepts in your
  codebase
- **Session Handoff** - Save AI "thinking state" and restore it later
- **Autonomous Insights** - Background analysis surfaces improvements you
  didn't ask for
- **Works Everywhere** - Cursor, Claude Desktop, VS Code, or this SDK

## Installation

```bash
pip install createstate
```

Or download directly from [createstate.ai/web/sdk](https://createstate.ai/web/sdk)

## Upgrading

To upgrade to the latest version:

```bash
# If installed via pip
pip install --upgrade createstate

# If installed from archive
cd createstate-X.Y.Z
pip install --upgrade .
```

**Note:** Your configuration (`~/.createstate/config.json`) is preserved
during upgrades - you won't need to run `create-state configure` again.

Verify your version:

```bash
create-state --version
```

## Quick Start

```bash
# Configure your API key (get one at createstate.ai/web/api-keys)
create-state configure

# Initialize a world model for your project (automatically set as active)
create-state init --name "My Project"

# Check status of your active model
create-state status

# Capture your codebase to the knowledge graph
create-state capture code ./src

# Ask questions about your project
create-state ask "why did we choose this architecture?"

# List all your world models
create-state models

# Switch to a different model (by name or ID)
create-state use "World Model from CLI"
# Or by ID (full or partial)
create-state use d8e850c0
```

---

## The Knowledge Lifecycle

Create State follows a simple lifecycle that builds institutional memory
over time:

```
    +==========================================+
    |          THE KNOWLEDGE LIFECYCLE         |
    +==========================================+

    1. CREATE          2. CAPTURE           3. SYNTHESIZE
       World Model        Code & Context       Knowledge

         [New]              [+++]               [=]
          |                  |||                 |
          v                  vvv                 v
    +----------+       +----------+        +----------+
    | Empty    |  -->  | Growing  |  -->   | Rich     |
    | Graph    |       | Graph    |        | Summary  |
    +----------+       +----------+        +----------+
                            |
                            | (repeat)
                            v

    4. HANDOFF          5. RESTORE          6. CONTINUE
       Session             Context             Working

        [>>>]              [<<<]              [...]
          |                  |                  |
          v                  v                  v
    +----------+       +----------+        +----------+
    | Save AI  |  -->  | Load AI  |  -->   | Full     |
    | State    |       | State    |        | Context  |
    +----------+       +----------+        +----------+
```

### Phase 1: Create World Model

Start by creating a world model - your project's knowledge container:

```bash
# CLI
create-state init --name "my-app" --language python
```

```python
# Python
client.create_world_model(
    project_name="my-app",
    language="python",
    description="E-commerce backend with FastAPI"
)
```

This creates an empty knowledge graph ready to capture your project's
evolution.

### Phase 2: Capture Knowledge

**Automatic with IDE Integration:** When using Create State through an MCP
integration, code and context are captured automatically as you work.
That's our value add - you don't have to do anything.

Officially supported integrations:
- **Cursor**
- **Claude**
- **OpenAI**
- **VS Code**
- **GitHub Copilot**
- **Lovable**
- **Google Antigravity**

Other MCP-compatible tools should also work with Create State, even if not
officially tested.

**CLI/SDK for Batch Capture:** Use `capture code` to build your knowledge
graph from existing code:

```bash
# Capture entire codebase (recursive) - builds knowledge graph
create-state capture code ./src

# Or filter by file types
create-state capture code ./ --extensions py,js,ts

# Single file capture
create-state capture code ./src/auth.py --description "Auth module"
```

```
    YOUR CODEBASE                     KNOWLEDGE GRAPH

    ./src/                            +--[Module]----+
    ./lib/                   -->      | 127 files    |
    ./tests/                          | 342 nodes    |
                                      | 891 edges    |
                                      +--------------+
```

**Capture decisions and context:** For architectural decisions not in code:

```bash
# Capture context via CLI
create-state capture context "Chose Redis for caching due to low latency"
```

```python
# Or via Python SDK
client.capture_context(
    "Decided to use JWT for authentication because it's stateless "
    "and scales horizontally."
)
```

**Analyze without capturing (privacy-safe exploration):**

```bash
# Analyze only - nothing stored, just returns insights
create-state analyze ./src

# Analyze AND capture in one command
create-state analyze ./src --capture
```

| Command | Persists to Graph | Returns Analysis |
|---------|-------------------|------------------|
| `capture code <path>` | Yes | No |
| `analyze <path>` | No | Yes |
| `analyze <path> --capture` | Yes | Yes |

### Phase 3: Synthesize Knowledge

**Automatic:** Synthesis runs automatically after every 5 captures,
creating a comprehensive project summary using AI.

**Manual trigger:** Force immediate synthesis at natural breakpoints:

```bash
# Optional - synthesis happens automatically
create-state synthesize
```

This creates a comprehensive project summary:

```
+------------------------------------------------------------------+
|                    SYNTHESIZED PROJECT CONTEXT                    |
+------------------------------------------------------------------+
| Project: my-app                                                   |
| Language: Python 3.11                                             |
| Framework: FastAPI                                                |
|                                                                   |
| ARCHITECTURE:                                                     |
|   - REST API with JWT authentication                              |
|   - PostgreSQL for persistence                                    |
|   - Redis for caching (optional)                                  |
|                                                                   |
| KEY DECISIONS:                                                    |
|   - JWT over sessions for horizontal scaling                      |
|   - Pydantic for validation                                       |
|                                                                   |
| KNOWN ISSUES:                                                     |
|   - Token refresh not implemented yet                             |
|                                                                   |
| PRIORITIES:                                                       |
|   1. Complete auth flow                                           |
|   2. Add rate limiting                                            |
+------------------------------------------------------------------+
```

**When to manually synthesize:**
- Before creating a session handoff (ensures latest context is included)
- After completing a major feature
- Before switching to different work area

### Phase 4: Create Session Handoff

Before ending your session, create a handoff to preserve AI thinking state:

```bash
# CLI
create-state handoff create --name "end-of-day-jan-1"
```

```python
# Python
handoff = client.create_session_handoff(
    handoff_name="end-of-day-jan-1",
    include_experimental_thoughts=True
)
print(f"Handoff ID: {handoff['handoff_id']}")
```

The handoff captures:

```
+------------------------------------------------------------------+
|                     SESSION HANDOFF PACKAGE                       |
+------------------------------------------------------------------+
|  - Active world model reference                                   |
|  - Recent captures and context                                    |
|  - AI thinking state and hypotheses                               |
|  - Pending insights not yet discussed                             |
|  - Work in progress indicators                                    |
+------------------------------------------------------------------+
```

### Phase 5: Restore Session

When starting a new session, restore from the handoff:

```bash
# CLI - list available handoffs
create-state handoff list

# Restore from specific handoff
create-state handoff restore abc123-def456
```

```python
# Python
packages = client.list_handoff_packages()
for pkg in packages.get("handoff_packages", []):
    print(f"{pkg['id']}: {pkg['name']} ({pkg['created_at']})")

# Restore
client.restore_from_handoff(handoff_id="abc123-def456")
```

### Phase 6: Continue Working

After restoration, your AI has full context:

```
    BEFORE RESTORE                    AFTER RESTORE

    +----------------+                +----------------+
    | AI: "I don't   |                | AI: "I see we  |
    | know anything  |     -->        | were working   |
    | about your     |                | on JWT auth    |
    | project"       |                | yesterday..."  |
    +----------------+                +----------------+
```

Query your knowledge graph to find past decisions:

```bash
# CLI - conversational queries
create-state ask "why did we choose JWT for auth?"

# Or structured queries
create-state query "authentication decisions"
create-state search "why did we choose JWT"
```

```python
# Python
result = client.query_world_model("authentication classes")
results = client.search_knowledge("JWT decision rationale")
```

Get AI-generated insights:

```bash
# Get focused insights
create-state insights --focus security

# Get autonomous "shower thinking" insights
create-state thinking --priority high
```

---

## Complete Workflow Example

Here's a typical day using the CLI (note: with Cursor/Claude Desktop
integration, capture is automatic):

```
+==================================================================+
|                    A DAY WITH CREATE STATE                        |
+==================================================================+

MORNING - Start Session
-----------------------
$ create-state handoff list
Available handoffs:
  abc123: end-of-day-dec-31 (2025-12-31T18:00:00Z)

$ create-state handoff restore abc123
[OK] Session restored. Context loaded for: my-app
[OK] Last working on: JWT authentication flow


MIDDAY - Capture Your Codebase
------------------------------
$ create-state ask "what's the auth implementation status?"
[INFO] Based on your captured context...

# Capture entire project to knowledge graph
$ create-state capture code ./
[OK] Captured 127 files to knowledge graph
[INFO] Auto-synthesis triggered (5+ captures)


AFTERNOON - Check Insights
--------------------------
$ create-state insights --focus security
[INFO] 2 security recommendations:
  1. Consider adding rate limiting to /auth/refresh
  2. Token expiry could be configurable via env var

$ create-state thinking
[INFO] Autonomous insights:
  - The auth module has grown complex; consider splitting
  - Test coverage for edge cases is low


END OF DAY - Handoff
--------------------
$ create-state handoff create --name "end-of-day-jan-1"
[OK] Handoff created: def456-ghi789
[OK] AI state preserved for next session
```

**Note:** When using Create State through Cursor or Claude Desktop, capture
happens automatically as your AI assistant works with you. The CLI is for
batch operations or explicit control.

---

## CLI Reference

### Global Options

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Show API parameters sent |
| `-V, --version` | Show version and exit |

**Tip:** Use `-v` when learning the CLI. It shows both the response and the
parameters sent, helping you understand how the API works:

```bash
$ create-state -v synthesize
# Synthesizing project knowledge...

# Project Summary Synthesized

**Project:** my-project
**Summary ID:** d2877693-f0e4-47e7-837b-80bba5741ad5
**Entities Analyzed:** 210
...

PARAMETERS
  project_path: .
```

Without `-v`, only the response is shown (no PARAMETERS section).

### Commands

| Command | Description |
|---------|-------------|
| `configure` | Set up API credentials |
| `init` | Initialize a world model for a project (sets as active) |
| `models` | List your world models |
| `use <name-or-id>` | Set active world model by name or ID |
| `status` | Show active model status and context |
| `capture context "..."` | Capture decisions or discussions |
| `capture code <path>` | Capture code to knowledge graph (file or dir) |
| `analyze <path>` | Analyze code (transient, use --capture to persist) |
| `ask <question>` | Ask questions about your project |
| `query <query>` | Query the knowledge graph |
| `search <query>` | Search captured knowledge semantically |
| `insights` | Get AI-generated project insights |
| `thinking` | Get autonomous background insights |
| `synthesize` | Create comprehensive knowledge summary |
| `handoff create` | Create session handoff package |
| `handoff list` | List available handoff packages |
| `handoff restore <id>` | Restore from session handoff |

### Command Details

**capture** - Capture knowledge to the graph (persists data):

```bash
# Capture decisions or discussions
create-state capture context "We chose PostgreSQL for ACID compliance"

# Capture single file
create-state capture code ./src/auth.py
create-state capture code ./src/billing.py --description "Payment module" --type new

# Capture entire directory (recursive)
create-state capture code ./src
create-state capture code ./ --extensions py,js,ts --max-files 200
```

Options for `capture code`:
- `--description, -d` - Description of the code or changes (single file only)
- `--language, -l` - Programming language (auto-detected from extension)
- `--type, -t` - Type of change: `new`, `update`, `fix`, `refactor` (default: update)
- `--max-files` - Maximum files to capture for directories (default: 100)
- `--extensions` - Comma-separated file extensions (default: py,js,ts,jsx,tsx)
- `--include-gitignored` - Include files that would be excluded by .gitignore

**analyze** - Analyze code quality (transient by default):

```bash
# Analyze only - returns insights, nothing stored
create-state analyze ./src

# Analyze AND capture to knowledge graph
create-state analyze ./src --capture

# Single file analysis
create-state analyze ./src/auth.py
```

Options for `analyze`:
- `--capture` - Also capture code to knowledge graph (requires active model)
- `--max-files` - Maximum files to analyze (default: 100)
- `--extensions` - Comma-separated file extensions
- `--include-gitignored` - Include files that would be excluded by .gitignore

**ask** - Conversational interface for asking questions about your project:

```bash
create-state ask "why did we choose Redis here?"
create-state ask "what patterns do we use for error handling?"
```

**query** - Structured queries against the knowledge graph:

```bash
create-state query "authentication classes"
create-state query --code "payment processing"  # Include code snippets
```

## Python API Reference

### Client Initialization

**Note:** An API key is required. Get one at
[createstate.ai/web/api-keys](https://createstate.ai/web/api-keys)

```python
from createstate import CreateStateClient

# With explicit API key
client = CreateStateClient(api_key="cs_...")

# From environment variable CREATESTATE_API_KEY
client = CreateStateClient()

# Custom endpoint (for enterprise deployments)
client = CreateStateClient(base_url="https://your-instance.example.com")
```

### Code Analysis

```python
# Analyze code string
result = client.analyze_code(code, language="python")

# Analyze with educational insights
result = client.analyze_code_with_intelligence(
    code,
    include_educational_insights=True,
    include_alternatives=True
)

# Analyze local files (reads from filesystem)
result = client.analyze_file("./src/main.py")

# Analyze directory (respects .gitignore by default)
result = client.analyze_directory(
    "./src",
    max_files=100,
    respect_gitignore=True  # Default - skips gitignored files
)
```

### World Model Operations

```python
# Create
model = client.create_world_model("my-app", "python", "Description")

# Get context
context = client.get_world_model()

# Query
result = client.query_world_model("authentication classes")

# List
models = client.list_world_models()
```

### Knowledge Capture

```python
# Capture context (decisions, discussions)
client.capture_context("Decided to use PostgreSQL for ACID compliance")

# Capture code
client.capture_code(
    code="def process_payment(): ...",
    file_path="src/billing.py",
    language="python",
    description="Payment processing function",
    change_type="new"  # new | update | fix | refactor
)

# Synthesize all knowledge
client.synthesize_context()

# Search knowledge
results = client.search_knowledge("payment processing")
```

### Session Handoff

```python
# Create handoff
handoff = client.create_session_handoff(handoff_name="end-of-sprint")

# List handoffs
packages = client.list_handoff_packages()

# Restore
client.restore_from_handoff(handoff_id="abc123")
```

### Insights

```python
# Proactive insights
insights = client.get_insights(focus_area="security")

# Autonomous insights
insights = client.get_shower_thinking_insights(priority_filter="high")
```

## Error Handling

```python
from createstate import (
    CreateStateError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
)

try:
    result = client.analyze_code(code)
except AuthenticationError:
    print("Invalid API key - get one at createstate.ai/web/api-keys")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except ValidationError as e:
    print(f"Invalid input: {e.message}")
except CreateStateError as e:
    print(f"API error: {e}")
```

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `CREATESTATE_API_KEY` | Your API key (required) |
| `CREATESTATE_API_URL` | Custom API URL (optional) |

### Config File

Stored at `~/.createstate/config.json`:

```json
{
  "api_key": "cs_your_api_key",
  "api_url": "https://createstate.ai",
  "active_model": {
    "id": "d8e850c0-e8e4-42e7-ac47-361605bcb938",
    "name": "My Project"
  }
}
```

- Run `create-state configure` to set up API credentials
- The `active_model` is automatically set when you run `create-state init`
- Use `create-state use <name-or-id>` to switch active models (names and partial IDs work)
- Use `create-state models` to list available models

## Security & Privacy

### Data Persistence: Analyze vs Capture

Understanding which commands store data is important for privacy:

| Command | Data Stored? | Use Case |
|---------|--------------|----------|
| `analyze <path>` | No | Safe exploration, quality insights |
| `analyze <path> --capture` | Yes | Explore + persist to graph |
| `capture code <path>` | Yes | Build knowledge graph |
| `capture context "..."` | Yes | Record decisions |

**Privacy-safe exploration:** Use `analyze` without `--capture` to explore
code quality, detect patterns, and get insights without storing anything.

### Respecting .gitignore

Both `analyze` and `capture code` respect your `.gitignore` by default.
Files that Git would ignore are automatically skipped, protecting:

- `.env` files containing secrets and API keys
- Local configuration files with credentials
- Build artifacts and generated code
- Dependency directories (`node_modules`, `venv`, etc.)

```bash
# Default behavior - respects .gitignore
create-state capture code ./
create-state analyze ./

# Override to include gitignored files (use with caution)
create-state capture code ./ --include-gitignored
create-state analyze ./ --include-gitignored
```

In Python:

```python
# Control gitignore behavior
result = client.analyze_directory(
    "./src",
    respect_gitignore=True,  # Default
)
print(f"Files gitignored: {result['files_gitignored']}")
```

### File Type Restrictions

The SDK only analyzes recognized source code files. Binaries, images, and
data files are automatically skipped.

### Credential Protection

Your API key is stored in `~/.createstate/config.json` with restricted
file permissions. API keys are never logged or included in error messages.

### Data Transmission

The `analyze_file()` and `analyze_directory()` functions read files from
your local filesystem and transmit their contents to Create State servers
for analysis. See our
[Privacy Policy](https://createstate.ai/web/privacy#sdk-privacy) for details.

## Links

- **Website:** [https://createstate.ai](https://createstate.ai)
- **Documentation:** [https://createstate.ai/web/documentation](https://createstate.ai/web/documentation)
- **API Keys:** [https://createstate.ai/web/api-keys](https://createstate.ai/web/api-keys)
- **SDK Downloads:** [https://createstate.ai/web/sdk](https://createstate.ai/web/sdk)
- **Privacy Policy:** [https://createstate.ai/web/privacy](https://createstate.ai/web/privacy)
- **Security Policy:** [https://createstate.ai/web/security-policy](https://createstate.ai/web/security-policy)
- **Support:** support@createstate.ai

## License

MIT License - Copyright (c) 2026 Create State. All rights reserved.

See [LICENSE](LICENSE) for details.
