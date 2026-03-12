#!/usr/bin/env python3
"""
Create State CLI

Command-line interface for the Create State API. This tool provides terminal
access to Create State's AI code intelligence features including code analysis,
knowledge graph management, session handoffs, and proactive insights.

Usage:
    create-state analyze ./my-project
    create-state init
    create-state status
    create-state query "authentication classes"
    create-state configure
    create-state handoff create --name "end-of-day"
    create-state thinking --priority high

For documentation and more information, visit:
    https://createstate.ai

Copyright (c) 2026 Create State. All rights reserved.

This software is licensed under the MIT License. You may obtain a copy of the
license at: https://opensource.org/licenses/MIT

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from .client import CreateStateClient
from .exceptions import AuthenticationError, CreateStateError

# Use the same base URL as the client (varies by build: prod/beta/dev)
DEFAULT_BASE_URL = CreateStateClient.DEFAULT_BASE_URL


# ANSI color codes (disabled if not a TTY)
def _supports_color() -> bool:
    """Check if the terminal supports colors."""
    if not hasattr(sys.stdout, "isatty"):
        return False
    if not sys.stdout.isatty():
        return False
    if os.environ.get("NO_COLOR"):
        return False
    return True


_USE_COLOR = _supports_color()


def _color(text: str, code: str) -> str:
    """Apply ANSI color code to text."""
    if not _USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def green(text: str) -> str:
    return _color(text, "32")


def cyan(text: str) -> str:
    return _color(text, "36")


def yellow(text: str) -> str:
    return _color(text, "33")


# Global verbose flag (set by main parser)
_VERBOSE = False


def set_verbose(verbose: bool) -> None:
    """Set the global verbose mode."""
    global _VERBOSE
    _VERBOSE = verbose


def is_verbose() -> bool:
    """Check if verbose mode is enabled."""
    return _VERBOSE


def print_response(result: dict) -> None:
    """Print the response content from Create State.

    CS already provides beautifully formatted markdown output,
    so we just print it as-is.
    """
    content = result.get("content", [])
    if content:
        print()
        for item in content:
            if isinstance(item, dict):
                text = item.get("text", "")
                if text:
                    print(text)
            elif isinstance(item, str):
                print(item)


def print_parameters(params: dict) -> None:
    """Print the parameters that were sent to the API (verbose mode).

    Mimics the PARAMETERS section shown in Cursor's MCP UI.
    """
    if not params:
        return

    print()
    print(dim("PARAMETERS"))
    for key, value in params.items():
        if isinstance(value, str) and len(value) > 100:
            # Truncate long values with ellipsis
            display_value = value[:100] + "..."
        else:
            display_value = value
        print(f"  {cyan(key)}: {display_value}")

    print()


def red(text: str) -> str:
    return _color(text, "31")


def purple(text: str) -> str:
    return _color(text, "35")


def bold(text: str) -> str:
    return _color(text, "1")


def dim(text: str) -> str:
    return _color(text, "2")


def get_config_path() -> Path:
    """Get the configuration file path."""
    config_dir = Path.home() / ".createstate"
    return config_dir / "config.json"


def load_config() -> dict:
    """Load configuration from file."""
    config_path = get_config_path()
    if config_path.exists():
        try:
            return json.loads(config_path.read_text())
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_config(config: dict) -> None:
    """Save configuration to file."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2))
    # Secure the file
    os.chmod(config_path, 0o600)


def get_active_model() -> dict:
    """Get the active world model from config."""
    config = load_config()
    return config.get("active_model", {})


def set_active_model(model_id: str, model_name: str) -> None:
    """Set the active world model in config."""
    config = load_config()
    config["active_model"] = {
        "id": model_id,
        "name": model_name,
    }
    save_config(config)


def get_client() -> CreateStateClient:
    """Get an authenticated client."""
    # Try environment variable first
    api_key = os.environ.get("CREATESTATE_API_KEY")

    # Fall back to config file
    if not api_key:
        config = load_config()
        api_key = config.get("api_key")

    if not api_key:
        print(red("[ERROR]") + " No API key configured.")
        print()
        print("Run " + cyan("create-state configure") + " to set up your API key,")
        print("or set the " + cyan("CREATESTATE_API_KEY") + " environment variable.")
        sys.exit(1)

    base_url = os.environ.get("CREATESTATE_API_URL") or load_config().get("api_url")

    return CreateStateClient(api_key=api_key, base_url=base_url)


def cmd_auth(args: argparse.Namespace) -> int:
    """Manage OAuth connections (GitHub, etc.)."""

    auth_command = getattr(args, "auth_command", None)

    if not auth_command:
        print(yellow("[INFO]") + " OAuth management commands:")
        print()
        print(
            f"  {cyan('create-state auth github')}             - Connect GitHub account"
        )
        print(
            f"  {cyan('create-state auth github --status')}    - Check connection status"
        )
        print(f"  {cyan('create-state auth github --disconnect')}- Disconnect GitHub")
        print()
        return 0

    if auth_command == "github":
        return cmd_auth_github(args)

    print(yellow("[ERROR]") + f" Unknown auth command: {auth_command}")
    return 1


def cmd_auth_github(args: argparse.Namespace) -> int:
    """Connect or manage GitHub OAuth connection via Device Flow.

    Uses GitHub's Device Flow for CLI-friendly authentication:
    1. Requests a device code from Create State server
    2. User visits github.com/login/device and enters the code
    3. CLI polls until authorization completes
    4. Token is stored server-side (encrypted, never returned to CLI)

    Args:
        args: Command arguments (--status, --disconnect)

    Returns:
        0 on success, 1 on failure
    """
    import time
    import urllib.error
    import urllib.request

    config = load_config()
    api_key = os.environ.get("CREATESTATE_API_KEY") or config.get("api_key")
    base_url = os.environ.get("CREATESTATE_API_URL") or config.get(
        "api_url", DEFAULT_BASE_URL
    )
    # Normalize: strip trailing slash and /mcp suffix (config may have /mcp for MCP client)
    base_url = base_url.rstrip("/")
    if base_url.endswith("/mcp"):
        base_url = base_url[:-4]

    if not api_key:
        print(yellow("[ERROR]") + " No API key configured.")
        print()
        print(
            "Run " + cyan("create-state configure") + " to set up your API key first."
        )
        return 1

    # Check status via SDK endpoint
    if args.status:
        print(dim("# Checking GitHub connection status..."))
        try:
            req = urllib.request.Request(
                f"{base_url}/sdk/github/status",
                headers={"Authorization": f"Bearer {api_key}"},
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

            if data.get("connected"):
                print(
                    green("[OK]")
                    + f" GitHub connected as: {cyan(data.get('username', 'unknown'))}"
                )
                print(dim(f"     Scopes: {', '.join(data.get('scopes', []))}"))
                if data.get("is_expired"):
                    print(yellow("[WARNING]") + " Token has expired. Reconnect with:")
                    print(dim("            create-state auth github"))
            else:
                print(dim("# GitHub not connected"))
                print()
                print("Connect your GitHub account to access private repositories:")
                print(f"  {cyan('create-state auth github')}")

            return 0

        except urllib.error.HTTPError as e:
            if e.code == 401:
                print(yellow("[ERROR]") + " Authentication failed. Run:")
                print(dim("           create-state configure"))
            else:
                print(yellow("[ERROR]") + f" API error: {e.code}")
            return 1
        except Exception as e:
            print(yellow("[ERROR]") + f" Failed to check status: {e}")
            return 1

    # Disconnect via SDK endpoint
    if args.disconnect:
        print(dim("# Disconnecting GitHub..."))
        try:
            req = urllib.request.Request(
                f"{base_url}/sdk/github/disconnect",
                method="POST",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                data=b"{}",
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

            if data.get("success"):
                print(green("[OK]") + " GitHub account disconnected")
            else:
                print(dim("# No GitHub connection to disconnect"))

            return 0

        except urllib.error.HTTPError as e:
            if e.code == 401:
                print(yellow("[ERROR]") + " Authentication failed. Run:")
                print(dim("           create-state configure"))
            else:
                print(yellow("[ERROR]") + f" API error: {e.code}")
            return 1
        except Exception as e:
            print(yellow("[ERROR]") + f" Failed to disconnect: {e}")
            return 1

    # Default: initiate Device Flow
    print(green("[GitHub OAuth]") + " Connect your GitHub account")
    print()

    try:
        # Step 1: Initiate device flow
        print(dim("# Requesting device code..."))

        req = urllib.request.Request(
            f"{base_url}/auth/cli/device-flow",
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            data=b"{}",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                device_data = json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 401:
                print(yellow("[ERROR]") + " Authentication failed. Run:")
                print(dim("           create-state configure"))
                return 1
            elif e.code == 429:
                print(
                    yellow("[ERROR]")
                    + " Rate limited. Please wait a few minutes and try again."
                )
                return 1
            else:
                error_body = e.read().decode() if e.fp else ""
                print(yellow("[ERROR]") + f" Failed to initiate device flow: {e.code}")
                if error_body:
                    try:
                        error_data = json.loads(error_body)
                        print(
                            dim(
                                f"           {error_data.get('detail', error_body[:100])}"
                            )
                        )
                    except Exception:
                        pass
                return 1

        user_code = device_data.get("user_code")
        verification_uri = device_data.get("verification_uri")
        device_code = device_data.get("device_code")
        expires_in = device_data.get("expires_in", 900)
        interval = device_data.get("interval", 5)

        if not user_code or not device_code:
            print(yellow("[ERROR]") + " Invalid response from server")
            return 1

        # Step 2: Display instructions to user
        print()
        print(f"Visit:  {cyan(verification_uri)}")
        print(f"Enter code:  {bold(user_code)}")
        print()
        print(dim(f"# Code expires in {expires_in // 60} minutes"))
        print()

        # Step 3: Poll for completion
        poll_url = f"{base_url}/auth/cli/device-poll"
        start_time = time.time()
        max_time = expires_in

        sys.stdout.write("Waiting for authorization...")
        sys.stdout.flush()

        while (time.time() - start_time) < max_time:
            time.sleep(interval)

            try:
                poll_req = urllib.request.Request(
                    poll_url,
                    method="POST",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    data=json.dumps({"device_code": device_code}).encode(),
                )

                with urllib.request.urlopen(poll_req, timeout=30) as response:
                    poll_data = json.loads(response.read().decode())

                if poll_data.get("success"):
                    sys.stdout.write(" " + green("[OK]") + "\n")
                    sys.stdout.flush()
                    print()
                    print(
                        green("[OK]")
                        + f" GitHub connected as: {cyan(poll_data.get('username', 'unknown'))}"
                    )
                    return 0

                if poll_data.get("pending"):
                    sys.stdout.write(".")
                    sys.stdout.flush()
                    continue

                if poll_data.get("error"):
                    sys.stdout.write(" " + yellow("[FAILED]") + "\n")
                    sys.stdout.flush()
                    print(yellow("[ERROR]") + f" {poll_data['error']}")
                    return 1

            except urllib.error.HTTPError as e:
                if e.code == 400:
                    error_body = e.read().decode() if e.fp else ""
                    sys.stdout.write(" " + yellow("[FAILED]") + "\n")
                    sys.stdout.flush()
                    try:
                        error_data = json.loads(error_body)
                        print(
                            yellow("[ERROR]")
                            + f" {error_data.get('detail', 'Request failed')}"
                        )
                    except Exception:
                        print(yellow("[ERROR]") + " Device code expired or invalid")
                    return 1
                elif e.code == 403:
                    sys.stdout.write(" " + yellow("[FAILED]") + "\n")
                    sys.stdout.flush()
                    print(yellow("[ERROR]") + " Authorization denied")
                    return 1
                else:
                    continue
            except Exception:
                continue

        sys.stdout.write(" " + yellow("[TIMEOUT]") + "\n")
        sys.stdout.flush()
        print(yellow("[ERROR]") + " Authorization timed out. Please try again.")
        return 1

    except KeyboardInterrupt:
        print("\n" + dim("# Cancelled"))
        return 1
    except Exception as e:
        print(yellow("[ERROR]") + f" Failed to connect GitHub: {e}")
        return 1


def cmd_configure(args: argparse.Namespace) -> int:
    """Configure the CLI with API credentials."""
    print(bold("Create State CLI Configuration"))
    print()

    config = load_config()

    # Get API key
    current_key = config.get("api_key", "")
    masked = current_key[:8] + "..." if current_key else "not set"
    print(f"Current API key: {dim(masked)}")

    api_key = input("Enter your API key (or press Enter to keep current): ").strip()
    if api_key:
        config["api_key"] = api_key

    # Optional: custom API URL
    if args.advanced:
        current_url = config.get("api_url", DEFAULT_BASE_URL)
        print(f"\nCurrent API URL: {dim(current_url)}")
        api_url = input("Enter API URL (or press Enter for default): ").strip()
        if api_url:
            config["api_url"] = api_url

    save_config(config)
    print()
    print(green("[OK]") + " Configuration saved to " + str(get_config_path()))

    # Test the connection
    if config.get("api_key"):
        print()
        print("Testing connection...")
        try:
            client = get_client()
            # Simple test - list world models
            client.list_world_models()
            print(green("[OK]") + " Successfully connected to Create State API")
        except AuthenticationError:
            print(red("[ERROR]") + " Invalid API key")
            return 1
        except Exception as e:
            print(yellow("[WARNING]") + f" Could not verify connection: {e}")

    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    """Analyze code files or directories (transient by default, use --capture to persist)."""
    target = Path(args.path)

    if not target.exists():
        print(red("[ERROR]") + f" Path not found: {args.path}")
        return 1

    client = get_client()

    # Check if user wants to capture (persist to knowledge graph)
    should_capture = getattr(args, "capture", False)

    # If capturing, check for active model
    model_id = ""
    if should_capture:
        active = get_active_model()
        model_id = active.get("id", "")
        if model_id:
            print(dim(f"# Will capture to: {active.get('name', 'Unknown')}"))
        else:
            print(
                yellow("[WARNING]") + " --capture specified but no active world model"
            )
            print(dim("         Use 'create-state init' to create a model first"))
            print(dim("         Continuing with analysis only..."))
            print()
            should_capture = False

    # Determine whether to respect .gitignore
    respect_gitignore = not getattr(args, "include_gitignored", False)

    # Parse extensions if provided
    extensions = None
    if getattr(args, "extensions", None):
        extensions = [
            f".{ext.strip().lstrip('.')}" for ext in args.extensions.split(",")
        ]

    if target.is_file():
        # Analyze single file
        print(dim(f"# Analyzing {target.name}..."))
        try:
            result = client.analyze_file(str(target))

            # Print the response from Create State
            print_response(result)

            # Capture to knowledge graph if --capture flag and active model
            if should_capture and model_id:
                try:
                    code = target.read_text(encoding="utf-8", errors="replace")
                    language = _get_language_for_extension(target.suffix)
                    client.capture_code(
                        code=code,
                        file_path=str(target),
                        language=language,
                        description=f"Analyzed via CLI: {target.name}",
                        change_type="update",
                        model_id=model_id,
                    )
                    print()
                    print(green("[OK]") + " Captured to knowledge graph")
                except Exception as capture_error:
                    print(yellow("[WARNING]") + f" Could not capture: {capture_error}")

            # Verbose mode: also show parameters sent
            if is_verbose():
                print_parameters(
                    {
                        "file_path": str(target),
                        "capture": should_capture,
                    }
                )
        except CreateStateError as e:
            print(red("[ERROR]") + f" {e}")
            return 1
    else:
        # Analyze directory
        print(dim(f"# Analyzing {target}..."))

        # Check for .gitignore and notify user
        gitignore_path = target / ".gitignore"
        if gitignore_path.exists():
            if respect_gitignore:
                print(yellow("[INFO]") + " Found .gitignore - respecting exclusions")
                print(dim("       Use --include-gitignored to analyze all files"))
            else:
                print(
                    yellow("[INFO]")
                    + " Found .gitignore - IGNORING (--include-gitignored)"
                )

        try:
            max_files = args.max_files or 100

            result = client.analyze_directory(
                str(target),
                extensions=extensions,
                max_files=max_files,
                respect_gitignore=respect_gitignore,
            )

            # Print the response from Create State
            print_response(result)

            # Capture files if --capture flag and active model
            if should_capture and model_id:
                files_analyzed = result.get("files_analyzed", 0)
                if files_analyzed > 0:
                    print()
                    print(
                        dim(f"# Capturing {files_analyzed} files to knowledge graph...")
                    )
                    captured_count = _capture_directory_files(
                        client,
                        target,
                        model_id,
                        extensions,
                        max_files,
                        respect_gitignore,
                    )
                    print(
                        green("[OK]")
                        + f" Captured {captured_count} files to knowledge graph"
                    )

            # Verbose mode: also show parameters sent
            if is_verbose():
                print_parameters(
                    {
                        "directory_path": str(target),
                        "extensions": extensions,
                        "max_files": max_files,
                        "respect_gitignore": respect_gitignore,
                        "capture": should_capture,
                    }
                )
        except CreateStateError as e:
            print(red("[ERROR]") + f" {e}")
            return 1

    return 0


def _get_language_for_extension(ext: str) -> str:
    """Map file extension to language name."""
    ext_to_lang = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".rb": "ruby",
        ".php": "php",
        ".md": "markdown",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".r": "r",
        ".sql": "sql",
        ".sh": "shell",
        ".bash": "shell",
        ".zsh": "shell",
    }
    return ext_to_lang.get(ext.lower(), "text")


def _capture_directory_files(
    client,
    target: Path,
    model_id: str,
    extensions: list,
    max_files: int,
    respect_gitignore: bool,
) -> int:
    """Capture files from a directory to the knowledge graph. Returns count captured."""
    captured_count = 0
    capture_extensions = extensions or [".py", ".js", ".ts", ".jsx", ".tsx"]
    skip_dirs = {
        "node_modules",
        ".git",
        "__pycache__",
        "venv",
        ".venv",
        "dist",
        "build",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".pytest_cache",
    }

    for ext in capture_extensions:
        if captured_count >= max_files:
            break
        for file_path in target.rglob(f"*{ext}"):
            if captured_count >= max_files:
                break
            # Skip common non-source directories
            if any(part in skip_dirs for part in file_path.parts):
                continue
            try:
                code = file_path.read_text(encoding="utf-8", errors="replace")
                language = _get_language_for_extension(ext)
                client.capture_code(
                    code=code,
                    file_path=str(file_path),
                    language=language,
                    description=f"Batch capture: {file_path.name}",
                    change_type="update",
                    model_id=model_id,
                )
                captured_count += 1
            except Exception:
                continue

    return captured_count


def cmd_init_from_github(args: argparse.Namespace) -> int:
    """Initialize a world model from a GitHub repository.

    This command uses server-side import to:
    1. Validate the GitHub URL
    2. Check GitHub connection (prompt to connect if needed)
    3. Start server-side import via bootstrap API
    4. Poll for completion with progress updates
    5. Set the new model as active

    Benefits of server-side import:
    - Works with private repositories via OAuth
    - No local git installation required
    - Handles large repositories
    - Automatic synthesis after import

    Args:
        args: Command arguments including from_github URL, name, branch

    Returns:
        0 on success, 1 on failure
    """
    import re as regex
    import time
    import urllib.error
    import urllib.request

    github_url = args.from_github.strip()

    # Validate GitHub URL format
    github_pattern = regex.compile(
        r"^https://github\.com/([a-zA-Z0-9](?:[a-zA-Z0-9._-]*[a-zA-Z0-9])?)/([a-zA-Z0-9](?:[a-zA-Z0-9._-]*[a-zA-Z0-9])?)(?:\.git)?/?$"
    )
    match = github_pattern.match(github_url)
    if not match:
        print(yellow("[ERROR]") + " Invalid GitHub URL format.")
        print(dim("         Expected: https://github.com/owner/repo"))
        return 1

    owner = match.group(1)
    repo_name = match.group(2)

    # Get config and API key
    config = load_config()
    api_key = os.environ.get("CREATESTATE_API_KEY") or config.get("api_key")
    base_url = os.environ.get("CREATESTATE_API_URL") or config.get(
        "api_url", DEFAULT_BASE_URL
    )
    # Normalize: strip trailing slash and /mcp suffix (config may have /mcp for MCP client)
    base_url = base_url.rstrip("/")
    if base_url.endswith("/mcp"):
        base_url = base_url[:-4]

    if not api_key:
        print(yellow("[ERROR]") + " No API key configured.")
        print()
        print(
            "Run " + cyan("create-state configure") + " to set up your API key first."
        )
        return 1

    # Get project name
    if args.name:
        project_name = args.name
    else:
        default_name = repo_name
        try:
            user_input = input(f"Project name [{default_name}]: ").strip()
            project_name = user_input if user_input else default_name
        except (EOFError, KeyboardInterrupt):
            print("\n" + dim("# Cancelled"))
            return 1

    print()
    print(green("[GitHub Import]") + f" {owner}/{repo_name}")
    print()

    try:
        # Check GitHub connection status first
        print(dim("# Checking GitHub connection..."))
        try:
            status_req = urllib.request.Request(
                f"{base_url}/sdk/github/status",
                headers={"Authorization": f"Bearer {api_key}"},
            )

            with urllib.request.urlopen(status_req, timeout=10) as response:
                status_data = json.loads(response.read().decode())

            if status_data.get("connected"):
                print(
                    green("[OK]")
                    + f" GitHub connected as: {cyan(status_data.get('username', 'unknown'))}"
                )
            else:
                print(dim("# GitHub not connected"))
                print()
                print(
                    "To import private repositories, connect your GitHub account first:"
                )
                print(f"  {cyan('create-state auth github')}")
                print()
                print("Proceeding with public repository import...")

        except urllib.error.HTTPError as e:
            # Don't fail on GitHub status check - it's informational only
            # The actual import request will fail if there's a real auth problem
            if e.code == 401:
                print(dim("# GitHub status check unavailable, proceeding..."))
            else:
                print(dim(f"# Could not check GitHub status ({e.code}), proceeding..."))
        except Exception:
            print(dim("# Could not check GitHub status, proceeding..."))

        # Start server-side import via SDK endpoint (API key auth)
        print()
        print(dim("# Starting import..."))

        import_payload = {
            "repo_url": github_url,
            "project_name": project_name,
        }

        if args.branch:
            import_payload["branch"] = args.branch

        import_url = f"{base_url}/sdk/github/import"
        debug_mode = getattr(args, "debug", False) or os.environ.get(
            "CREATESTATE_DEBUG"
        )
        if debug_mode:
            print(dim(f"# DEBUG: base_url = {base_url}"))
            print(dim(f"# DEBUG: import_url = {import_url}"))
            print(dim(f"# DEBUG: DEFAULT_BASE_URL = {DEFAULT_BASE_URL}"))

        bootstrap_req = urllib.request.Request(
            import_url,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(import_payload).encode(),
        )

        try:
            with urllib.request.urlopen(bootstrap_req, timeout=30) as response:
                bootstrap_data = json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""

            if e.code == 401:
                print(yellow("[ERROR]") + " Authentication failed. Run:")
                print(dim("           create-state configure"))
                return 1
            elif e.code == 403:
                print(
                    yellow("[ERROR]") + " Access denied. The repository may be private."
                )
                print()
                print("Connect your GitHub account to import private repositories:")
                print(f"  {cyan('create-state auth github')}")
                return 1
            elif e.code == 400:
                try:
                    error_data = json.loads(error_body)
                    detail = error_data.get("detail", "")
                    if "already has an active" in detail.lower():
                        print(yellow("[ERROR]") + " An import is already in progress.")
                        print(
                            dim(
                                "         Wait for it to complete or check status with:"
                            )
                        )
                        print(dim("         create-state models"))
                        return 1
                    print(yellow("[ERROR]") + f" {detail}")
                except Exception:
                    print(yellow("[ERROR]") + f" Bad request: {error_body[:200]}")
                return 1
            elif e.code == 429:
                print(
                    yellow("[ERROR]")
                    + " Rate limit exceeded. Please wait and try again."
                )
                return 1
            else:
                print(yellow("[ERROR]") + f" Server error: {e.code}")
                return 1

        job_id = bootstrap_data.get("job_id")
        if not job_id:
            print(yellow("[ERROR]") + " No job ID returned from server")
            return 1

        print(green("[OK]") + " Import started")
        print(dim(f"     Job ID: {job_id}"))
        print()

        # Poll for completion
        sys.stdout.write("Importing repository")
        sys.stdout.flush()

        last_status = ""
        last_progress = 0
        max_wait = 600  # 10 minutes max
        start_time = time.time()

        while (time.time() - start_time) < max_wait:
            time.sleep(3)

            try:
                progress_req = urllib.request.Request(
                    f"{base_url}/sdk/github/import-progress/{job_id}",
                    headers={"Authorization": f"Bearer {api_key}"},
                )

                with urllib.request.urlopen(progress_req, timeout=10) as response:
                    progress_data = json.loads(response.read().decode())

                status = progress_data.get("status", "")
                progress = progress_data.get("progress", 0)

                if status == "completed":
                    sys.stdout.write(" " + green("[OK]") + "\n")
                    sys.stdout.flush()

                    model_id = progress_data.get("model_id")
                    files_captured = progress_data.get(
                        "entities_created", 0
                    ) or progress_data.get("files_captured", 0)

                    if model_id:
                        set_active_model(model_id, project_name)

                    print()
                    print(green("[SUCCESS]") + " GitHub import complete!")
                    print()
                    print(f"Project: {cyan(project_name)}")
                    if model_id:
                        print(f"Model ID: {dim(model_id)}")
                    print(f"Entities created: {files_captured}")
                    print()
                    print("Next steps:")
                    print(
                        f"  {cyan('create-state status')}        - View model details"
                    )
                    query_cmd = 'create-state query "..."'
                    print(f"  {cyan(query_cmd)}  - Search your codebase")

                    return 0

                elif status == "failed":
                    sys.stdout.write(" " + yellow("[FAILED]") + "\n")
                    sys.stdout.flush()

                    error = progress_data.get("error", "Unknown error")
                    print(yellow("[ERROR]") + f" Import failed: {error}")

                    if "private" in error.lower() or "authentication" in error.lower():
                        print()
                        print(
                            "This may be a private repository. Connect GitHub to import it:"
                        )
                        print(f"  {cyan('create-state auth github')}")

                    return 1

                else:
                    # Still in progress
                    if progress > last_progress:
                        dots = (progress - last_progress) // 10
                        sys.stdout.write("." * max(1, dots))
                        sys.stdout.flush()
                        last_progress = progress
                    elif status != last_status:
                        sys.stdout.write(".")
                        sys.stdout.flush()

                    last_status = status

            except urllib.error.HTTPError as e:
                if e.code == 404:
                    sys.stdout.write(" " + yellow("[FAILED]") + "\n")
                    sys.stdout.flush()
                    print(yellow("[ERROR]") + " Import job not found")
                    return 1
                # Continue polling on other errors
                continue
            except Exception:
                # Continue polling on network errors
                continue

        sys.stdout.write(" " + yellow("[TIMEOUT]") + "\n")
        sys.stdout.flush()
        print(
            yellow("[ERROR]")
            + " Import timed out. The repository may still be processing."
        )
        print(dim("         Check status with: create-state models"))
        return 1

    except KeyboardInterrupt:
        print("\n" + dim("# Cancelled"))
        return 1
    except Exception as e:
        print(yellow("[ERROR]") + f" Import failed: {str(e)}")
        if is_verbose():
            import traceback

            traceback.print_exc()
        return 1


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a world model for the current project."""

    # Handle --from-github flag
    from_github = getattr(args, "from_github", None)
    if from_github and isinstance(from_github, str):
        return cmd_init_from_github(args)

    project_path = Path(args.path or ".").resolve()

    # Get project name - prompt if not provided
    if args.name:
        project_name = args.name
    else:
        default_name = project_path.name
        print(dim(f"# Project directory: {project_path}"))
        try:
            user_input = input(f"Project name [{default_name}]: ").strip()
            project_name = user_input if user_input else default_name
        except (EOFError, KeyboardInterrupt):
            print("\n" + dim("# Cancelled"))
            return 1

    client = get_client()

    # Check for existing model with same name
    try:
        models_result = client.list_world_models()
        existing_models = _parse_models_from_response(models_result)
        matching_model = None
        for model in existing_models:
            if model.get("name", "").lower() == project_name.lower():
                matching_model = model
                break

        if matching_model:
            print(
                yellow("[WARNING]")
                + f" A world model named '{project_name}' already exists."
            )
            print(dim(f"           ID: {matching_model['id']}"))
            print()
            try:
                choice = input("Use existing model? [Y/n]: ").strip().lower()
                if choice in ("", "y", "yes"):
                    # Use the existing model
                    set_active_model(matching_model["id"], project_name)
                    print()
                    print(green("[OK]") + f" Now using existing model: {project_name}")
                    print(dim(f"     Model ID: {matching_model['id']}"))
                    print()
                    print(
                        "Run " + cyan("create-state status") + " to see model details."
                    )
                    return 0
                # User chose to create new - continue below
                print(dim("# Creating new model with same name..."))
            except (EOFError, KeyboardInterrupt):
                print("\n" + dim("# Cancelled"))
                return 1
    except Exception as e:
        # If we can't check for duplicates, continue with creation
        if is_verbose():
            print(dim(f"# Could not check for duplicates: {e}"))

    print(dim(f"# Initializing world model for {project_name}..."))

    # Detect primary language
    language = args.language
    if not language:
        # Auto-detect from files
        ext_count = {}
        for ext in [".py", ".js", ".ts", ".go", ".rs", ".java"]:
            count = len(list(project_path.rglob(f"*{ext}")))
            if count > 0:
                ext_count[ext] = count

        if ext_count:
            primary_ext = max(ext_count, key=ext_count.get)
            lang_map = {
                ".py": "python",
                ".js": "javascript",
                ".ts": "typescript",
                ".go": "go",
                ".rs": "rust",
                ".java": "java",
            }
            language = lang_map.get(primary_ext, "python")
            print(dim(f"# Detected primary language: {language}"))
        else:
            language = "python"

    try:
        description = args.description or ""

        result = client.create_world_model(
            project_name=project_name,
            language=language,
            description=description,
        )

        # Extract model_id from result and save as active model
        model_id = None
        if isinstance(result, dict):
            # Try common response structures
            model_id = result.get("model_id") or result.get("id")
            if not model_id and "content" in result:
                # MCP response format - parse from content
                content = result.get("content", [])
                if content and isinstance(content[0], dict):
                    text = content[0].get("text", "")
                    # Look for full UUID pattern first (36 chars with dashes)
                    uuid_match = re.search(
                        r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}",
                        text,
                        re.IGNORECASE,
                    )
                    if uuid_match:
                        model_id = uuid_match.group(0)
                    else:
                        # Fall back to parsing "Model ID:" line
                        for line in text.split("\n"):
                            if "Model ID:" in line:
                                model_id = (
                                    line.split("Model ID:")[-1].strip().strip("*`")
                                )
                                break

        if model_id:
            set_active_model(model_id, project_name)
            print(dim(f"# Set as active model (ID: {model_id[:8]}...)"))

        # Print the response from Create State
        print_response(result)

        # Verbose mode: also show parameters sent
        if is_verbose():
            print_parameters(
                {
                    "project_name": project_name,
                    "language": language,
                    "description": description,
                }
            )

    except CreateStateError as e:
        print(red("[ERROR]") + f" {e}")
        return 1

    return 0


def _parse_models_from_response(result: dict) -> list:
    """Parse model list from MCP response, extracting full IDs and names."""
    models = []
    if not isinstance(result, dict) or "content" not in result:
        return models

    content = result.get("content", [])
    if not content or not isinstance(content[0], dict):
        return models

    text = content[0].get("text", "")
    lines = text.split("\n")

    # Parse model entries - new format has name on one line, ID on next:
    # "  • Model Name"
    # "    ID: full-uuid-here"
    current_name = None
    for line in lines:
        # Look for model name line (bullet point)
        name_match = re.match(r"\s*[•\-\*]\s*(.+?)(?:\s*\[ARCHIVED\])?\s*$", line)
        if name_match:
            current_name = name_match.group(1).strip()
            continue

        # Look for ID line following a name
        id_match = re.match(r"\s*ID:\s*([a-f0-9\-]{36})", line, re.IGNORECASE)
        if id_match and current_name:
            models.append({"name": current_name, "id": id_match.group(1)})
            current_name = None
            continue

    # Fallback: Look for any full UUIDs in text
    if not models:
        uuid_pattern = re.compile(
            r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}",
            re.IGNORECASE,
        )
        for match in uuid_pattern.finditer(text):
            uuid = match.group(0)
            # Look for a name before this UUID
            before_text = text[max(0, match.start() - 100) : match.start()]
            name_match = re.search(r"[•\-\*]\s*(.+?)(?:\n|$)", before_text)
            name = name_match.group(1).strip() if name_match else "Unknown"
            models.append({"name": name, "id": uuid})

    return models


def cmd_models(args: argparse.Namespace) -> int:
    """List user's world models."""
    print(dim("# Loading world models..."))

    client = get_client()

    try:
        result = client.list_world_models()

        # Show active model indicator
        active = get_active_model()
        active_id = active.get("id", "")

        # Show active model indicator if set
        if active_id:
            print(dim(f"# Active model: {active.get('name', 'Unknown')} ({active_id})"))
            print()

        # Print the server response (formatted output)
        print_response(result)

        # Also show a tip about using full IDs
        print()
        print(dim("Tip: Use 'create-state use <name>' or 'create-state use <id>'"))
        print(dim("     to switch models. Names and partial IDs work too."))

    except CreateStateError as e:
        print(red("[ERROR]") + f" {e}")
        return 1

    return 0


def cmd_use(args: argparse.Namespace) -> int:
    """Set the active world model."""
    model_ref = args.model

    if not model_ref:
        # Show current active model with full ID
        active = get_active_model()
        if active:
            print(f"Active model: {cyan(active.get('name', 'Unknown'))}")
            print(f"Model ID:     {active.get('id', 'Unknown')}")
        else:
            print("No active model set.")
            print()
            print(f"Use {cyan('create-state models')} to list available models,")
            cmd_hint = cyan("create-state use <name-or-id>")
            print(f"then {cmd_hint} to select one.")
        return 0

    print(dim(f"# Looking for model: {model_ref}..."))

    client = get_client()

    try:
        # Get list of models to search
        result = client.list_world_models()
        models = _parse_models_from_response(result)

        model_ref_lower = model_ref.lower()

        # Collect all matches by category
        exact_name_matches = []
        id_matches = []
        partial_name_matches = []

        for model in models:
            m_name = model.get("name", "").lower()
            m_id = model.get("id", "").lower()

            # Exact name match (case-insensitive)
            if m_name == model_ref_lower:
                exact_name_matches.append(model)

            # ID match (starts with or contains)
            elif m_id.startswith(model_ref_lower) or model_ref_lower in m_id:
                id_matches.append(model)

            # Partial name match (contains)
            elif model_ref_lower in m_name:
                partial_name_matches.append(model)

        # Determine which matches to use (priority: exact name > ID > partial name)
        matches = exact_name_matches or id_matches or partial_name_matches

        # Handle results
        if len(matches) == 1:
            # Single match - use it
            model = matches[0]
            set_active_model(model["id"], model["name"])
            print(green("[OK]") + f" Active model set to: {model['name']}")
            print(f"     Model ID: {model['id']}")
            return 0

        elif len(matches) > 1:
            # Multiple matches - show disambiguation menu
            print(yellow("[WARNING]") + f" Multiple models match '{model_ref}':")
            print()
            for i, model in enumerate(matches, 1):
                print(f"  {i}. {model['name']}")
                print(dim(f"     ID: {model['id']}"))
            print()

            try:
                choice = input(
                    f"Select model [1-{len(matches)}] or 'c' to cancel: "
                ).strip()
                if choice.lower() == "c":
                    print(dim("# Cancelled"))
                    return 1

                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(matches):
                        model = matches[idx]
                        set_active_model(model["id"], model["name"])
                        print()
                        print(green("[OK]") + f" Active model set to: {model['name']}")
                        print(f"     Model ID: {model['id']}")
                        return 0
                    else:
                        print(red("[ERROR]") + f" Invalid selection: {choice}")
                        return 1
                except ValueError:
                    print(red("[ERROR]") + f" Invalid selection: {choice}")
                    return 1

            except (EOFError, KeyboardInterrupt):
                print("\n" + dim("# Cancelled"))
                return 1

        else:
            # No matches found
            # If model_ref looks like a full UUID, use it directly
            if len(model_ref) > 30 and "-" in model_ref:
                set_active_model(model_ref, "Unknown")
                print(green("[OK]") + f" Active model set to ID: {model_ref}")
                print(
                    yellow("[WARNING]")
                    + " Model not found in your list - verify the ID is correct."
                )
                return 0

            print(red("[ERROR]") + f" Could not find model: {model_ref}")
            print()
            print(f"Use {cyan('create-state models')} to list available models.")
            print("You can use the model name or ID (partial or full).")
            return 1

    except CreateStateError as e:
        print(red("[ERROR]") + f" {e}")
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Show project status and insights."""
    # Check for active model - required for status command
    active = get_active_model()
    model_id = getattr(args, "model", None) or active.get("id", "")

    if not model_id:
        # No active model - show helpful CLI-specific message
        print(red("[ERROR]") + " No active world model.")
        print()
        print("To get started:")
        cmd1 = cyan("create-state init --name 'My Project'")
        cmd2 = cyan("create-state models")
        cmd3 = cyan("create-state use <model-id>")
        print(f"  1. Create a model: {cmd1}")
        print(f"  2. Or list models:  {cmd2}")
        print(f"  3. Then select one: {cmd3}")
        return 1

    model_name = active.get("name", model_id[:8])
    print(dim(f"# Loading world model {model_name}..."))

    client = get_client()

    try:
        # If model_id is short (not a full UUID), try to expand it
        if len(model_id) < 36:
            models_result = client.list_world_models()
            models = _parse_models_from_response(models_result)
            for model in models:
                if model["id"].startswith(model_id) or model_id in model["id"]:
                    full_id = model["id"]
                    full_name = model["name"]
                    # Update config with full ID
                    set_active_model(full_id, full_name)
                    model_id = full_id
                    model_name = full_name
                    print(dim(f"# Expanded to full ID: {model_id}"))
                    break

        # Get world model context using model_id
        result = client.get_world_model(
            model_id=model_id,
            include_insights=True,
        )

        # Check if response indicates model not found
        response_text = ""
        if isinstance(result, dict) and "content" in result:
            content = result.get("content", [])
            if content and isinstance(content[0], dict):
                response_text = content[0].get("text", "")

        # Filter out MCP-specific responses - show CLI guidance instead
        if (
            "No World Model Found" in response_text
            or "not found" in response_text.lower()
        ):
            print(red("[ERROR]") + f" World model not found: {model_id}")
            print()
            print("The stored model ID may be invalid or the model was deleted.")
            print()
            cmd1 = cyan("create-state models")
            cmd2 = cyan("create-state use <name-or-id>")
            print(f"Run {cmd1} to see available models,")
            print(f"then {cmd2} to select a valid one.")
            return 1

        # Print the response from Create State
        print_response(result)

        # Verbose mode: also show parameters sent
        if is_verbose():
            print_parameters(
                {
                    "model_id": model_id,
                    "include_insights": True,
                }
            )

    except CreateStateError as e:
        print(red("[ERROR]") + f" {e}")
        return 1

    return 0


def cmd_query(args: argparse.Namespace) -> int:
    """Query the project knowledge graph."""
    query = " ".join(args.query)

    if not query:
        print(red("[ERROR]") + " Please provide a query")
        return 1

    # Check for active model
    active = get_active_model()
    if not active.get("id"):
        print(red("[ERROR]") + " No active world model.")
        print()
        cmd1 = cyan("create-state init --name 'My Project'")
        cmd2 = cyan("create-state use <model>")
        print(f"First create or select a model: {cmd1}")
        print(f"Or select an existing one: {cmd2}")
        return 1

    model_name = active.get("name", "Unknown")
    print(dim(f"# Querying {model_name}: {query}"))

    client = get_client()

    try:
        include_code = args.code

        result = client.query_world_model(
            query=query,
            model_id=active.get("id", ""),
            include_code=include_code,
        )

        # Print the response from Create State
        print_response(result)

        # Verbose mode: also show parameters sent
        if is_verbose():
            print_parameters(
                {
                    "query": query,
                    "model_id": active.get("id", ""),
                    "include_code": include_code,
                }
            )

    except CreateStateError as e:
        print(red("[ERROR]") + f" {e}")
        return 1

    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    """Ask a question using AI chat with your project context."""
    question = " ".join(args.question)

    if not question:
        print(red("[ERROR]") + " Please provide a question")
        return 1

    # Check for active model
    active = get_active_model()
    if not active.get("id"):
        print(red("[ERROR]") + " No active world model.")
        print()
        cmd1 = cyan("create-state init --name 'My Project'")
        cmd2 = cyan("create-state use <model>")
        print(f"First create or select a model: {cmd1}")
        print(f"Or select an existing one: {cmd2}")
        return 1

    model_name = active.get("name", "Unknown")
    print(dim(f"# Asking {model_name}: {question}"))
    print()

    client = get_client()

    try:
        result = client.ask(
            question=question,
            model_id=active.get("id", ""),
        )

        # Print the response from the AI
        print_response(result)

        # Verbose mode: also show parameters sent
        if is_verbose():
            print_parameters(
                {
                    "question": question,
                    "model_id": active.get("id", ""),
                }
            )

    except CreateStateError as e:
        print(red("[ERROR]") + f" {e}")
        return 1

    return 0


def cmd_insights(args: argparse.Namespace) -> int:
    """Get AI-generated insights for the project."""
    project_path = args.path or "."
    focus_area = args.focus or "all"

    # Check for active model
    active = get_active_model()
    if not active.get("id"):
        print(red("[ERROR]") + " No active world model.")
        print()
        cmd1 = cyan("create-state init --name 'My Project'")
        cmd2 = cyan("create-state use <model>")
        print(f"First create or select a model: {cmd1}")
        print(f"Or select an existing one: {cmd2}")
        return 1

    model_name = active.get("name", "Unknown")
    print(dim(f"# Generating insights for {model_name}..."))

    client = get_client()

    try:
        result = client.get_insights(
            project_path=project_path,
            focus_area=focus_area,
            model_id=active.get("id", ""),
        )

        # Print the response from Create State
        print_response(result)

        # Verbose mode: also show parameters sent
        if is_verbose():
            print_parameters(
                {
                    "project_path": project_path,
                    "focus_area": focus_area,
                    "model_id": active.get("id", ""),
                }
            )

    except CreateStateError as e:
        print(red("[ERROR]") + f" {e}")
        return 1

    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """Search project knowledge."""
    query = " ".join(args.query)

    if not query:
        print(red("[ERROR]") + " Please provide a search query")
        return 1

    # Check for active model
    active = get_active_model()
    if not active.get("id"):
        print(red("[ERROR]") + " No active world model.")
        print()
        cmd1 = cyan("create-state init --name 'My Project'")
        cmd2 = cyan("create-state use <model>")
        print(f"First create or select a model: {cmd1}")
        print(f"Or select an existing one: {cmd2}")
        return 1

    model_name = active.get("name", "Unknown")
    print(dim(f"# Searching {model_name}: {query}"))

    client = get_client()

    try:
        limit = args.limit or 10

        result = client.search_knowledge(
            query=query,
            limit=limit,
            model_id=active.get("id", ""),
        )

        # Print the response from Create State
        print_response(result)

        # Verbose mode: also show parameters sent
        if is_verbose():
            print_parameters(
                {
                    "query": query,
                    "limit": limit,
                    "model_id": active.get("id", ""),
                }
            )

    except CreateStateError as e:
        print(red("[ERROR]") + f" {e}")
        return 1

    return 0


def cmd_handoff_create(args: argparse.Namespace) -> int:
    """Create a session handoff package."""
    # Get active model to include in handoff
    active = get_active_model()
    model_id = active.get("id", "")
    model_name = active.get("name", "")

    if model_id:
        print(dim(f"# Creating session handoff for {model_name}..."))
    else:
        print(dim("# Creating session handoff..."))
        print(dim("# (No active model - handoff may not include world model)"))

    client = get_client()

    try:
        handoff_name = args.name or ""
        include_experimental = not args.no_experimental

        result = client.create_session_handoff(
            handoff_name=handoff_name,
            include_experimental_thoughts=include_experimental,
            model_id=model_id,
        )

        # Print the response from Create State
        print_response(result)

        # Verbose mode: also show parameters sent
        if is_verbose():
            print_parameters(
                {
                    "handoff_name": handoff_name,
                    "include_experimental_thoughts": include_experimental,
                    "model_id": model_id,
                }
            )

    except CreateStateError as e:
        print(red("[ERROR]") + f" {e}")
        return 1

    return 0


def cmd_handoff_restore(args: argparse.Namespace) -> int:
    """Restore from a session handoff."""
    handoff_id = args.handoff_id

    print(dim(f"# Restoring from handoff {handoff_id[:16]}..."))

    client = get_client()

    try:
        result = client.restore_from_handoff(
            handoff_id=handoff_id,
            priority_restoration=True,
        )

        # Try to extract and save the restored model as active
        # The response text contains model info like:
        # "- **Model Name** (ID: `abc12345...`)"
        model_restored = False
        if isinstance(result, dict) and "content" in result:
            for content_item in result.get("content", []):
                if content_item.get("type") == "text":
                    text = content_item.get("text", "")
                    # Look for "Active World Model Restored" or "World Model Auto-Loaded"
                    if "World Model" in text and "(ID:" in text:
                        # Extract model info from response
                        # Pattern: **Model Name** (ID: `abc12345...`)
                        import re

                        # Find model name and ID
                        model_match = re.search(
                            r"\*\*([^*]+)\*\*\s*\(ID:\s*`([a-f0-9-]+)\.\.\.`\)",
                            text,
                        )
                        if model_match:
                            model_name = model_match.group(1).strip()
                            model_id_prefix = model_match.group(2).strip()

                            # Get full model ID by listing models
                            try:
                                models_result = client.list_world_models()
                                models = _parse_models_from_response(models_result)
                                for model in models:
                                    if model["id"].startswith(model_id_prefix):
                                        set_active_model(model["id"], model_name)
                                        print(
                                            dim(f"# Updated active model: {model_name}")
                                        )
                                        model_restored = True
                                        break
                            except Exception:
                                pass
                    break

        if not model_restored:
            print(
                dim(
                    "# [INFO] No active model set. Run 'create-state use <model>' to select one."
                )
            )

        # Print the response from Create State
        print_response(result)

        # Verbose mode: also show parameters sent
        if is_verbose():
            print_parameters(
                {
                    "handoff_id": handoff_id,
                    "priority_restoration": True,
                }
            )

    except CreateStateError as e:
        print(red("[ERROR]") + f" {e}")
        return 1

    return 0


def cmd_handoff_list(args: argparse.Namespace) -> int:
    """List available session handoffs."""
    print(dim("# Listing handoff packages..."))

    client = get_client()

    try:
        max_results = args.limit or 10
        include_expired = args.expired

        result = client.list_handoff_packages(
            max_results=max_results,
            include_expired=include_expired,
        )

        # Print the response from Create State
        print_response(result)

        # Verbose mode: also show parameters sent
        if is_verbose():
            print_parameters(
                {
                    "max_results": max_results,
                    "include_expired": include_expired,
                }
            )

    except CreateStateError as e:
        print(red("[ERROR]") + f" {e}")
        return 1

    return 0


def cmd_thinking(args: argparse.Namespace) -> int:
    """Get autonomous shower thinking insights."""
    project_path = args.path or "."

    # Check for active model
    active = get_active_model()
    if not active.get("id"):
        print(red("[ERROR]") + " No active world model.")
        print()
        cmd1 = cyan("create-state init --name 'My Project'")
        cmd2 = cyan("create-state use <model>")
        print(f"First create or select a model: {cmd1}")
        print(f"Or select an existing one: {cmd2}")
        return 1

    model_name = active.get("name", "Unknown")
    print(dim(f"# Getting AI insights for {model_name}..."))

    client = get_client()

    try:
        max_insights = args.limit or 10
        priority_filter = args.priority

        result = client.get_shower_thinking_insights(
            project_path=project_path,
            max_insights=max_insights,
            priority_filter=priority_filter,
            model_id=active.get("id", ""),
        )

        # Verbose mode: show full response
        # Print the response from Create State
        print_response(result)

        # Verbose mode: also show parameters sent
        if is_verbose():
            print_parameters(
                {
                    "project_path": project_path,
                    "max_insights": max_insights,
                    "priority_filter": priority_filter,
                    "model_id": active.get("id", ""),
                }
            )

    except CreateStateError as e:
        print(red("[ERROR]") + f" {e}")
        return 1

    return 0


def cmd_synthesize(args: argparse.Namespace) -> int:
    """Synthesize project knowledge into AINOTES summary."""
    project_path = args.path or "."

    # Check for active model
    active = get_active_model()
    if not active.get("id"):
        print(red("[ERROR]") + " No active world model.")
        print()
        cmd1 = cyan("create-state init --name 'My Project'")
        cmd2 = cyan("create-state use <model>")
        print(f"First create or select a model: {cmd1}")
        print(f"Or select an existing one: {cmd2}")
        return 1

    model_name = active.get("name", "Unknown")
    print(dim(f"# Synthesizing {model_name}..."))

    client = get_client()

    try:
        result = client.synthesize_context(
            project_path=project_path,
            model_id=active.get("id", ""),
        )

        # Print the response from Create State
        print_response(result)

        # Verbose mode: also show parameters sent
        if is_verbose():
            print_parameters(
                {
                    "project_path": project_path,
                    "model_id": active.get("id", ""),
                }
            )

    except CreateStateError as e:
        print(red("[ERROR]") + f" {e}")
        return 1

    return 0


def cmd_capture_context(args: argparse.Namespace) -> int:
    """Capture conversation context or decisions to the knowledge graph."""
    context = args.context

    if not context:
        print(red("[ERROR]") + " Please provide context to capture")
        print()
        print("Example:")
        print(
            f'  {cyan("create-state capture context")} '
            '"We decided to use Redis for session caching"'
        )
        return 1

    # Check for active model
    active = get_active_model()
    if not active.get("id"):
        print(red("[ERROR]") + " No active world model.")
        print()
        cmd1 = cyan("create-state init --name 'My Project'")
        cmd2 = cyan("create-state use <model>")
        print(f"First create or select a model: {cmd1}")
        print(f"Or select an existing one: {cmd2}")
        return 1

    model_name = active.get("name", "Unknown")
    print(dim(f"# Capturing context to {model_name}..."))

    client = get_client()

    try:
        result = client.capture_context(
            context=context,
            project_path=".",
            model_id=active.get("id", ""),  # Explicit model_id for CLI
        )

        # Print success
        print(green("[OK]") + " Context captured successfully")
        print()
        print(dim("Captured:"))
        # Show first 200 chars of context
        preview = context[:200] + "..." if len(context) > 200 else context
        print(f"  {preview}")

        if is_verbose():
            print()
            print_response(result)

    except CreateStateError as e:
        print(red("[ERROR]") + f" {e}")
        return 1

    return 0


def cmd_capture_code(args: argparse.Namespace) -> int:
    """Capture code to the knowledge graph (file or directory)."""
    target = Path(args.path)

    if not target.exists():
        print(red("[ERROR]") + f" Path not found: {args.path}")
        return 1

    # Check for active model
    active = get_active_model()
    if not active.get("id"):
        print(red("[ERROR]") + " No active world model.")
        print()
        cmd1 = cyan("create-state init --name 'My Project'")
        cmd2 = cyan("create-state use <model>")
        print(f"First create or select a model: {cmd1}")
        print(f"Or select an existing one: {cmd2}")
        return 1

    model_id = active.get("id", "")
    model_name = active.get("name", "Unknown")

    client = get_client()

    # Determine whether to respect .gitignore
    respect_gitignore = not getattr(args, "include_gitignored", False)

    if target.is_file():
        # Single file capture
        print(dim(f"# Capturing {target.name} to {model_name}..."))

        try:
            code = target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(red("[ERROR]") + f" Could not read file: {e}")
            return 1

        language = args.language or _get_language_for_extension(target.suffix)
        description = args.description or f"Captured from {target.name}"
        change_type = args.type or "update"

        try:
            result = client.capture_code(
                code=code,
                file_path=str(target),
                language=language,
                description=description,
                change_type=change_type,
                model_id=model_id,
            )

            print(green("[OK]") + f" Captured: {target.name}")
            print(f"     Language: {language}")
            print(f"     Type: {change_type}")

            if is_verbose():
                print()
                print_response(result)

        except CreateStateError as e:
            print(red("[ERROR]") + f" {e}")
            return 1
    else:
        # Directory capture (recursive)
        print(dim(f"# Capturing directory {target} to {model_name}..."))

        # Parse extensions if provided
        extensions = None
        if getattr(args, "extensions", None):
            extensions = [
                f".{ext.strip().lstrip('.')}" for ext in args.extensions.split(",")
            ]

        max_files = getattr(args, "max_files", 100) or 100

        # Check for .gitignore
        gitignore_path = target / ".gitignore"
        if gitignore_path.exists() and respect_gitignore:
            print(yellow("[INFO]") + " Found .gitignore - respecting exclusions")

        captured_count = _capture_directory_files(
            client, target, model_id, extensions, max_files, respect_gitignore
        )

        print(green("[OK]") + f" Captured {captured_count} files to knowledge graph")

    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """Show version information."""
    from . import __version__

    print(f"create-state version {__version__}")
    return 0


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="create-state",
        description="Create State - Enterprise AI Code Intelligence Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  create-state init --name "My App"       Initialize a new world model
  create-state models                     List your world models
  create-state use "My App"               Switch by name (or partial ID)
  create-state status                     Show active model status

  # GitHub integration (NEW)
  create-state auth github                Connect your GitHub account
  create-state init --from-github <url>   Import from GitHub repository
  create-state init --from-github <url> --branch dev   Import specific branch

  # Capture to knowledge graph (persists data)
  create-state capture context "..."      Capture decisions/discussions
  create-state capture code ./file.py     Capture single file
  create-state capture code ./src         Capture directory (recursive)

  # Analyze code (transient by default)
  create-state analyze ./src              Analyze only (no persistence)
  create-state analyze ./src --capture    Analyze AND persist to graph
  create-state ask "why Redis?"           Ask questions about your project
  create-state thinking                   Get autonomous AI insights
  create-state synthesize                 Create AINOTES-style summary
  create-state handoff create             Save session for continuity
  create-state configure                  Set up your API key

Get your API key at: https://createstate.ai/web/api-keys
        """,
    )

    parser.add_argument(
        "-V",
        "--version",
        action="store_true",
        help="Show version and exit",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show rich, detailed output (like MCP responses in Cursor)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # configure command
    configure_parser = subparsers.add_parser(
        "configure",
        help="Configure API credentials",
    )
    configure_parser.add_argument(
        "--advanced",
        action="store_true",
        help="Show advanced configuration options",
    )
    configure_parser.set_defaults(func=cmd_configure)

    # auth command - OAuth management
    auth_parser = subparsers.add_parser(
        "auth",
        help="Manage OAuth connections (GitHub, etc.)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  create-state auth github             Connect your GitHub account
  create-state auth github --status    Check connection status
  create-state auth github --disconnect   Revoke GitHub access
        """,
    )
    auth_subparsers = auth_parser.add_subparsers(
        dest="auth_command", help="Auth commands"
    )

    # auth github - Connect GitHub account
    auth_github_parser = auth_subparsers.add_parser(
        "github",
        help="Connect or manage GitHub account for private repo access",
    )
    auth_github_parser.add_argument(
        "--disconnect",
        action="store_true",
        help="Disconnect GitHub account",
    )
    auth_github_parser.add_argument(
        "--status",
        action="store_true",
        help="Show current connection status",
    )
    auth_parser.set_defaults(func=cmd_auth)

    # analyze command
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze code (transient - use --capture to persist)",
    )
    analyze_parser.add_argument(
        "path",
        help="Path to file or directory to analyze",
    )
    analyze_parser.add_argument(
        "--capture",
        action="store_true",
        help="Also capture code to knowledge graph (requires active model)",
    )
    analyze_parser.add_argument(
        "--max-files",
        type=int,
        default=100,
        help="Maximum files to analyze (default: 100)",
    )
    analyze_parser.add_argument(
        "--extensions",
        help="Comma-separated file extensions to analyze (default: py,js,ts,jsx,tsx)",
    )
    analyze_parser.add_argument(
        "--include-gitignored",
        action="store_true",
        help="Include files that would be excluded by .gitignore",
    )
    analyze_parser.set_defaults(func=cmd_analyze)

    # init command
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a world model for a project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  create-state init                       Initialize from current directory
  create-state init --name "My App"       Initialize with custom name
  create-state init ./my-project          Initialize from specific path

  # GitHub import (requires: create-state auth github)
  create-state init --from-github https://github.com/user/repo
  create-state init --from-github https://github.com/user/repo --branch develop
        """,
    )
    init_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project path (default: current directory)",
    )
    init_parser.add_argument(
        "--name",
        help="Project name (default: directory name)",
    )
    init_parser.add_argument(
        "--language",
        help="Primary language (auto-detected if not specified)",
    )
    init_parser.add_argument(
        "--description",
        help="Project description",
    )
    init_parser.add_argument(
        "--from-github",
        metavar="URL",
        help="Initialize from a GitHub repository URL (e.g., https://github.com/owner/repo)",
    )
    init_parser.add_argument(
        "--branch",
        help="Branch to clone (default: repository default branch, only used with --from-github)",
    )
    init_parser.add_argument(
        "--debug",
        action="store_true",
        help="Show debug information (URLs, etc.)",
    )
    init_parser.set_defaults(func=cmd_init)

    # models command (list world models)
    models_parser = subparsers.add_parser(
        "models",
        help="List your world models",
    )
    models_parser.set_defaults(func=cmd_models)

    # use command (set active model)
    use_parser = subparsers.add_parser(
        "use",
        help="Set active model by name or ID (partial IDs work)",
    )
    use_parser.add_argument(
        "model",
        nargs="?",
        help="Model name, full ID, or partial ID (shows current if omitted)",
    )
    use_parser.set_defaults(func=cmd_use)

    # status command
    status_parser = subparsers.add_parser(
        "status",
        help="Show active model status and context",
    )
    status_parser.set_defaults(func=cmd_status)

    # capture command (subcommands)
    capture_parser = subparsers.add_parser(
        "capture",
        help="Capture knowledge to the graph (context or code)",
    )
    capture_subparsers = capture_parser.add_subparsers(
        dest="capture_command", help="What to capture"
    )

    # capture context
    capture_context_parser = capture_subparsers.add_parser(
        "context",
        help="Capture conversation context, decisions, or insights",
    )
    capture_context_parser.add_argument(
        "context",
        nargs="?",
        help='The context to capture (e.g., "We chose Redis for caching because...")',
    )
    capture_context_parser.set_defaults(func=cmd_capture_context)

    # capture code
    capture_code_parser = capture_subparsers.add_parser(
        "code",
        help="Capture code to knowledge graph (file or directory)",
    )
    capture_code_parser.add_argument(
        "path",
        help="Path to file or directory to capture",
    )
    capture_code_parser.add_argument(
        "--description",
        "-d",
        help="Description of the code or changes (single file only)",
    )
    capture_code_parser.add_argument(
        "--language",
        "-l",
        help="Programming language (auto-detected from extension)",
    )
    capture_code_parser.add_argument(
        "--type",
        "-t",
        choices=["new", "update", "fix", "refactor"],
        default="update",
        help="Type of change (default: update)",
    )
    capture_code_parser.add_argument(
        "--max-files",
        type=int,
        default=100,
        help="Maximum files to capture for directories (default: 100)",
    )
    capture_code_parser.add_argument(
        "--extensions",
        help="Comma-separated file extensions (default: py,js,ts,jsx,tsx)",
    )
    capture_code_parser.add_argument(
        "--include-gitignored",
        action="store_true",
        help="Include files that would be excluded by .gitignore",
    )
    capture_code_parser.set_defaults(func=cmd_capture_code)

    # query command - graph search
    query_parser = subparsers.add_parser(
        "query",
        help="Search knowledge graph for matching files, decisions, and insights",
        description=(
            "Direct graph search using keyword matching. Returns CodeEntities "
            "(captured files), Decisions, and Insights that match your search terms. "
            "Searches names, file paths, and descriptions. Fast and deterministic - "
            "use this when you know specific terms to look for."
        ),
    )
    query_parser.add_argument(
        "query",
        nargs="+",
        help="Keywords to find in the knowledge graph (searches names, paths, descriptions)",
    )
    query_parser.add_argument(
        "--code",
        action="store_true",
        help="Include code content in results (not just file references)",
    )
    query_parser.set_defaults(func=cmd_query)

    # ask command - AI-powered chat interface
    ask_parser = subparsers.add_parser(
        "ask",
        help="Get AI-generated answers using your project context (LLM chat)",
        description=(
            "AI-powered Q&A that generates conversational responses using your "
            "configured LLM provider (BYOK) or the built-in Qwen model. Your full "
            "project context is provided to the AI. Equivalent to chatting in the "
            "web UI's world model chat panel."
        ),
    )
    ask_parser.add_argument(
        "question",
        nargs="+",
        help="Your question (AI generates a response using your project context)",
    )
    ask_parser.set_defaults(func=cmd_ask)

    # insights command
    insights_parser = subparsers.add_parser(
        "insights",
        help="Get AI-generated project insights",
    )
    insights_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project path (default: current directory)",
    )
    insights_parser.add_argument(
        "--focus",
        choices=["architecture", "quality", "performance", "security", "all"],
        default="all",
        help="Focus area for insights",
    )
    insights_parser.set_defaults(func=cmd_insights)

    # search command - semantic vector search
    search_parser = subparsers.add_parser(
        "search",
        help="Semantic search using vector similarity (finds conceptually similar content)",
        description=(
            "Semantic search using AI vector embeddings. Unlike 'query' which matches "
            "exact keywords, 'search' finds content that is conceptually similar to "
            "your query - even if it uses different terminology. Use this when you're "
            "not sure of exact terms or want to explore related concepts."
        ),
    )
    search_parser.add_argument(
        "query",
        nargs="+",
        help="Natural language query (finds semantically similar content)",
    )
    search_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum results to return (default: 10)",
    )
    search_parser.set_defaults(func=cmd_search)

    # handoff command (subcommands)
    handoff_parser = subparsers.add_parser(
        "handoff",
        help="Session handoff for AI continuity",
        description="Manage session handoffs for AI continuity across sessions.",
        epilog="""
Examples:
  create-state handoff              List your handoff packages (default)
  create-state handoff list         List your handoff packages
  create-state handoff create       Create a new handoff package
  create-state handoff restore ID   Restore from a handoff package
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Default arguments for 'handoff' without subcommand (acts as 'list')
    handoff_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum results (default: 10)",
    )
    handoff_parser.add_argument(
        "--expired",
        action="store_true",
        help="Include expired packages",
    )
    handoff_parser.set_defaults(func=cmd_handoff_list)  # Default to list
    handoff_subparsers = handoff_parser.add_subparsers(dest="handoff_command")

    # handoff create
    handoff_create_parser = handoff_subparsers.add_parser(
        "create",
        help="Create a session handoff package",
    )
    handoff_create_parser.add_argument(
        "--name",
        help="Custom name for the handoff",
    )
    handoff_create_parser.add_argument(
        "--no-experimental",
        action="store_true",
        help="Exclude experimental thoughts",
    )
    handoff_create_parser.set_defaults(func=cmd_handoff_create)

    # handoff restore
    handoff_restore_parser = handoff_subparsers.add_parser(
        "restore",
        help="Restore from a session handoff",
    )
    handoff_restore_parser.add_argument(
        "handoff_id",
        help="Handoff package ID to restore",
    )
    handoff_restore_parser.set_defaults(func=cmd_handoff_restore)

    # handoff list
    handoff_list_parser = handoff_subparsers.add_parser(
        "list",
        help="List available handoff packages",
    )
    handoff_list_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum results (default: 10)",
    )
    handoff_list_parser.add_argument(
        "--expired",
        action="store_true",
        help="Include expired packages",
    )
    handoff_list_parser.set_defaults(func=cmd_handoff_list)

    # thinking command (shower thinking insights)
    thinking_parser = subparsers.add_parser(
        "thinking",
        help="Get autonomous AI 'shower thinking' insights",
    )
    thinking_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project path (default: current directory)",
    )
    thinking_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum insights (default: 10)",
    )
    thinking_parser.add_argument(
        "--priority",
        choices=["urgent", "high", "medium", "low", "exploratory"],
        help="Filter by priority level",
    )
    thinking_parser.set_defaults(func=cmd_thinking)

    # synthesize command
    synthesize_parser = subparsers.add_parser(
        "synthesize",
        help="Synthesize project knowledge into AINOTES summary",
    )
    synthesize_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project path (default: current directory)",
    )
    synthesize_parser.set_defaults(func=cmd_synthesize)

    # version command
    version_parser = subparsers.add_parser(
        "version",
        help="Show version information",
    )
    version_parser.set_defaults(func=cmd_version)

    args = parser.parse_args()

    # Handle --version flag
    if args.version:
        return cmd_version(args)

    # Set verbose mode globally
    if getattr(args, "verbose", False):
        set_verbose(True)

    # Show help if no command
    if not args.command:
        parser.print_help()
        return 0

    # Execute command
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print()
        return 130
    except Exception as e:
        print(red("[ERROR]") + f" Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
