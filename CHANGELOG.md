# Changelog

All notable changes to the Create State Python SDK will be documented in this
file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - 2026-10-14

### Added
- **Node tools** - Read and correct one knowledge node by id
  - `client.read_node(node_id, model_id="", node_type="")` calls `readNode`
  - `client.update_node(model_id, node_id, node_type, updates)` calls `updateNode`
  - `create-state node read <node_id> [--type T] [--model-id M]`
  - `create-state node update <node_id> --type T --updates '{"field": "value"}'`
  - Correcting an Entity's name or type retracts the old entity and returns
    the id of its successor
- **Image search on the CLI** - `create-state search --images <query>` calls
  `searchImages`, with `--mode` (text, semantic, hybrid) and `--category`
- **Batch image capture** - `client.capture_image_batch()` and
  `create-state capture images <paths...>` (up to 50 images)

### Security
- General security hardening. Upgrading is recommended

## [0.5.0] - 2026-06-05

### Added
- **Image Capture** - Save screenshots, diagrams, and visual assets to knowledge graph
  - `create-state capture image <path>` - Capture image file
  - `--title` - Set image title (required)
  - `--description` - Add image description
  - `--category` - Categorize as screenshot, diagram, asset, or other
- Python SDK image methods:
  - `client.capture_image()` - Capture image with base64 data
  - `client.search_images()` - Search images by description or visual similarity
- **Image Intelligence** - Uploaded images are automatically processed with:
  - Vision AI for generating descriptions and tags
  - OCR for extracting visible text from screenshots
  - CLIP embeddings for semantic visual search
- **Hybrid Image Search** - Search images using text, semantic similarity, or both

### Changed
- Images are validated, re-encoded, and stripped of EXIF metadata for security
- Content moderation automatically flags inappropriate uploads

## [0.4.0] - 2026-04-17

### Added
- **Teams** (Teams or Enterprise tier)
  - `create-state team list | create | show | members` - Manage teams
  - `create-state team invite | remove | role` - Manage members and roles
  - `create-state team projects | share | unshare` - Share world models
  - `create-state team activity | pulse | expert | colleague | stats` - Team
    intelligence
  - `create-state team capacity` - Show or set working capacity
- Python SDK team methods for the same operations, including
  `create_team()`, `invite_to_team()`, `update_member_role()`,
  `share_project_with_team()`, and `set_working_capacity()`

## [0.3.10] - 2026-03-11

### Added
- `ask` command for AI-powered Q&A using your project context
- Python SDK `ask()` method for programmatic chat interface

### Fixed
- `query` command now searches GitHub-imported code files correctly
- Improved command descriptions for `ask`, `query`, and `search` to clarify
  their different use cases

### Changed
- `query` returns exact matches from knowledge graph (code files, decisions,
  insights)
- `search` uses semantic vector search for conceptual matching
- `ask` uses AI to generate conversational answers from project context

## [0.3.7] - 2026-03-10

### Fixed
- Authentication middleware now uses unified auth service for SDK endpoints
- GitHub status check is now non-blocking for public repository imports
- Base URL handling in CLI no longer strips required path components

### Added
- `--debug` flag on `init` command for troubleshooting import issues
- Comprehensive test coverage for GitHub import workflows

## [0.3.0] - 2026-03-09

### Added
- **GitHub Integration** - Import repositories directly from GitHub
  - `create-state auth github` - Connect GitHub account via Device Flow
  - `create-state auth github --status` - Check connection status
  - `create-state auth github --disconnect` - Revoke GitHub access
  - `create-state init --from-github <url>` - Import from GitHub repository
  - `create-state init --from-github <url> --branch <branch>` - Import specific
    branch
- Python SDK GitHub methods:
  - `client.github_status()` - Check GitHub connection
  - `client.github_connect()` - Connect GitHub via Device Flow
  - `client.github_disconnect()` - Disconnect GitHub
  - `client.github_import()` - Import repository with progress tracking
  - `client.github_import_status()` - Check import job status
  - `client.github_import_cancel()` - Cancel in-progress import

### Changed
- Improved CLI help text with GitHub integration examples
- Server-side repository import for better performance and security

## [0.2.0] - 2026-03-08

### Added
- Initial GitHub OAuth integration infrastructure
- Device Flow authentication for CLI-friendly GitHub login

### Fixed
- Device flow security improvements
- Lint errors resolved across CLI module

## [0.1.0] - 2026-03-01

### Added
- Initial public release of Create State Python SDK
- CLI commands: `configure`, `init`, `models`, `use`, `status`
- Knowledge capture: `capture code`, `capture context`
- Code analysis: `analyze` with optional `--capture` flag
- Knowledge queries: `query`, `search`
- Session management: `handoff create`, `handoff list`, `handoff restore`
- Insights: `insights`, `thinking`, `synthesize`
- Python client library with full API coverage
- Configuration stored in `~/.createstate/config.json`
- Automatic .gitignore respect for privacy protection

---

For detailed documentation, visit [createstate.ai/web/documentation](https://createstate.ai/web/documentation)
