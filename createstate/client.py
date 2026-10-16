"""
Create State API Client

Core client for interacting with the Create State MCP API. This module provides
the CreateStateClient class, which wraps the JSON-RPC 2.0 MCP protocol to offer
a Pythonic interface for code analysis, knowledge graph operations, session
management, and AI-powered insights.

Key capabilities:
- Code analysis with pattern detection and quality scoring
- Knowledge graph creation and querying
- Session handoff for AI continuity
- Autonomous "shower thinking" insights

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

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from .exceptions import (
    APIError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
)


class CreateStateClient:
    """
    Client for the Create State API.

    Args:
        api_key: Your Create State API key. If not provided, reads from
                 CREATESTATE_API_KEY environment variable.
        base_url: API base URL. Defaults to https://createstate.ai
        timeout: Request timeout in seconds. Defaults to 30.

    Example:
        >>> client = CreateStateClient(api_key="cs_...")
        >>> result = client.analyze_code("def hello(): pass")
        >>> print(result["quality_score"])
    """

    DEFAULT_BASE_URL = "https://createstate.ai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
    ):
        self.api_key = api_key or os.environ.get("CREATESTATE_API_KEY")
        if not self.api_key:
            raise AuthenticationError(
                "API key required. Set CREATESTATE_API_KEY environment variable "
                "or pass api_key parameter."
            )

        # Normalize base URL: strip trailing slash and /mcp suffix to prevent doubling
        raw_url = (
            base_url or os.environ.get("CREATESTATE_API_URL") or self.DEFAULT_BASE_URL
        ).rstrip("/")
        # Remove /mcp suffix if present (we add it in _mcp_call)
        if raw_url.endswith("/mcp"):
            raw_url = raw_url[:-4]
        self.base_url = raw_url
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)
        self._request_id = 0  # JSON-RPC request ID counter

    def _get_user_agent(self) -> str:
        """Build User-Agent string with current version."""
        from . import __version__

        return f"CreateState-Python/{__version__}"

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated request to the API."""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": self._get_user_agent(),
        }

        try:
            if method.upper() == "GET":
                response = self._client.get(url, headers=headers, params=data)
            else:
                response = self._client.post(url, headers=headers, json=data)

            return self._handle_response(response)

        except httpx.TimeoutException:
            raise APIError("Request timed out", status_code=408)
        except httpx.RequestError as e:
            raise APIError(f"Request failed: {str(e)}")

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle API response and raise appropriate errors."""
        if response.status_code == 401:
            raise AuthenticationError("Invalid API key")

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                "Rate limit exceeded",
                retry_after=int(retry_after) if retry_after else None,
            )

        if response.status_code == 400:
            try:
                error_data = response.json()
                raise ValidationError(
                    error_data.get("detail", "Validation error"),
                    field=error_data.get("field"),
                )
            except json.JSONDecodeError:
                raise ValidationError(response.text)

        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get(
                    "detail", error_data.get("error", "Unknown error")
                )
            except json.JSONDecodeError:
                message = response.text or "Unknown error"
            raise APIError(message, status_code=response.status_code)

        try:
            return response.json()
        except json.JSONDecodeError:
            return {"raw": response.text}

    def _mcp_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Make an MCP tool call using JSON-RPC 2.0 protocol."""
        self._request_id += 1

        # Include client_type so server can format responses appropriately
        arguments_with_client = {**arguments, "_client_type": "cli"}

        # Build JSON-RPC 2.0 request
        jsonrpc_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments_with_client},
            "id": self._request_id,
        }

        response = self._request("POST", "/mcp/", jsonrpc_request)

        # Handle JSON-RPC response format
        if "error" in response:
            error = response["error"]
            raise APIError(
                error.get("message", "MCP call failed"),
                status_code=error.get("code", 500),
            )

        return response.get("result", response)

    # -------------------------------------------------------------------------
    # Code Analysis
    # -------------------------------------------------------------------------

    def analyze_code(
        self,
        code: str,
        language: str = "python",
        include_suggestions: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze code for quality, patterns, and potential improvements.

        Args:
            code: Source code to analyze
            language: Programming language (python, javascript, typescript)
            include_suggestions: Include improvement suggestions

        Returns:
            Analysis results including quality score, patterns, and suggestions

        Example:
            >>> result = client.analyze_code('''
            ... def fibonacci(n):
            ...     if n <= 1:
            ...         return n
            ...     return fibonacci(n-1) + fibonacci(n-2)
            ... ''')
            >>> print(result["patterns_detected"])
        """
        return self._mcp_call(
            "analyze_code",
            {
                "code": code,
                "language": language,
                "include_suggestions": include_suggestions,
            },
        )

    def analyze_code_with_intelligence(
        self,
        code: str,
        language: str = "python",
        include_educational_insights: bool = True,
        include_alternatives: bool = True,
        confidence_threshold: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Advanced code analysis using Pattern Detection Intelligence Engine.

        Uses systematic CS knowledge application for deeper analysis.

        Args:
            code: Source code to analyze
            language: Programming language
            include_educational_insights: Include CS educational insights
            include_alternatives: Include algorithmic alternatives
            confidence_threshold: Minimum confidence for pattern detection (0-1)

        Returns:
            Detailed analysis with patterns, alternatives, and educational content
        """
        return self._mcp_call(
            "analyze_code_with_intelligence",
            {
                "code": code,
                "language": language,
                "include_educational_insights": include_educational_insights,
                "include_alternatives": include_alternatives,
                "confidence_threshold": confidence_threshold,
            },
        )

    def detect_patterns(
        self,
        code: str,
        language: str = "python",
        pattern_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Detect design patterns and anti-patterns in code.

        Args:
            code: Source code to analyze
            language: Programming language
            pattern_types: Specific pattern types to detect
                          (design_pattern, anti_pattern, algorithm, idiom)

        Returns:
            Detected patterns with confidence scores
        """
        return self._mcp_call(
            "detect_patterns",
            {
                "code": code,
                "language": language,
                "pattern_types": pattern_types or [],
            },
        )

    # -------------------------------------------------------------------------
    # World Model Operations
    # -------------------------------------------------------------------------

    def create_world_model(
        self,
        project_name: str,
        language: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Create a new world model for a project.

        Args:
            project_name: Name of the project
            language: Primary programming language
            description: Optional project description

        Returns:
            Created world model details including model_id

        Example:
            >>> model = client.create_world_model("my-app", "python")
            >>> print(model["model_id"])
        """
        return self._mcp_call(
            "createWorldModel",
            {
                "project_name": project_name,
                "language": language,
                "description": description,
            },
        )

    def get_world_model(
        self,
        project_path: str = "",
        model_id: str = "",
        include_insights: bool = True,
        rendering_mode: str = "",
    ) -> Dict[str, Any]:
        """
        Get project world model context (AINOTES-style summary).

        Args:
            project_path: Path to project directory (for lookup by path/name)
            model_id: Direct model ID (preferred if known)
            include_insights: Include recent insights and recommendations
            rendering_mode: Display mode optimization (taste_topology, semantic_graph,
                          conceptual_identity, integrated). Auto-detected if not specified.

        Returns:
            Project context including architecture, key files, priorities
        """
        params = {"include_insights": include_insights}
        if model_id:
            params["model_id"] = model_id
        if project_path:
            params["project_path"] = project_path
        if rendering_mode:
            params["rendering_mode"] = rendering_mode
        return self._mcp_call("getProjectWorldModel", params)

    def query_world_model(
        self,
        query: str,
        model_id: str = "",
        include_code: bool = False,
    ) -> Dict[str, Any]:
        """
        Query project code structure for classes, functions, and patterns.

        Args:
            query: Natural language query about code structures
            model_id: World model ID (optional, uses default if not specified)
            include_code: Include code signatures in results

        Returns:
            Matching code structures and relationships

        Example:
            >>> result = client.query_world_model("authentication classes")
            >>> for entity in result["entities"]:
            ...     print(entity["name"], entity["type"])
        """
        return self._mcp_call(
            "queryWorldModel",
            {
                "query": query,
                "model_id": model_id,
                "include_code": include_code,
            },
        )

    def list_world_models(
        self,
        include_archived: bool = False,
    ) -> Dict[str, Any]:
        """
        List all world models owned by the current user.

        Args:
            include_archived: Include archived models in the list

        Returns:
            List of world models with details
        """
        return self._mcp_call(
            "listUserWorldModels",
            {
                "include_archived": include_archived,
            },
        )

    def ask(
        self,
        question: str,
        model_id: str = "",
        project_path: str = "",
    ) -> Dict[str, Any]:
        """
        Ask a question about your project using AI chat.

        Uses your configured BYOK model if set, otherwise the hosted Qwen model.
        The AI has full context of your world model including code, decisions,
        and captured knowledge.

        Args:
            question: Your question or message
            model_id: World model ID (optional, uses active model if not specified)
            project_path: Project path for additional git context

        Returns:
            AI-generated response based on your project knowledge

        Example:
            >>> response = client.ask("How does authentication work in this project?")
            >>> print(response["content"][0]["text"])
        """
        params = {"message": question}
        if model_id:
            params["project_id"] = model_id
        if project_path:
            params["project_path"] = project_path
        return self._mcp_call("llmChat", params)

    # -------------------------------------------------------------------------
    # Project Intelligence
    # -------------------------------------------------------------------------

    def get_insights(
        self,
        project_path: str = ".",
        focus_area: str = "all",
        model_id: str = "",
    ) -> Dict[str, Any]:
        """
        Get AI-generated insights and suggestions for your project.

        Args:
            project_path: Path to project directory
            focus_area: Specific area to focus on
                       (architecture, quality, performance, security, all)
            model_id: World model ID (required for CLI usage)

        Returns:
            Proactive insights and recommendations

        Example:
            >>> insights = client.get_insights(focus_area="security")
            >>> for insight in insights["recommendations"]:
            ...     print(f"[{insight['priority']}] {insight['title']}")
        """
        params = {
            "project_path": project_path,
            "focus_area": focus_area,
        }
        if model_id:
            params["model_id"] = model_id
        return self._mcp_call("getProactiveInsights", params)

    def capture_context(
        self,
        context: str,
        project_path: str = ".",
        model_id: str = "",
    ) -> Dict[str, Any]:
        """
        Capture conversation context to help AI remember discussions.

        Args:
            context: Conversation context or notes to remember
            project_path: Associated project path
            model_id: World model ID to capture to (required for CLI usage)

        Returns:
            Confirmation of captured context
        """
        params = {
            "context": context,
            "project_path": project_path,
        }
        if model_id:
            params["model_id"] = model_id
        return self._mcp_call("captureConversationContext", params)

    def capture_code(
        self,
        code: str,
        file_path: str,
        language: str,
        description: str = "",
        change_type: str = "update",
        model_id: str = "",
    ) -> Dict[str, Any]:
        """
        Capture code to the knowledge graph with versioning.

        Args:
            code: The actual code content
            file_path: Full path to the file
            language: Programming language
            description: Brief description of what the code does
            change_type: Type of change (new, update, fix, refactor)
            model_id: World model ID to capture to (required for CLI usage)

        Returns:
            Confirmation with version information
        """
        params = {
            "code": code,
            "file_path": file_path,
            "language": language,
            "description": description,
            "change_type": change_type,
        }
        if model_id:
            params["model_id"] = model_id
        return self._mcp_call("captureCode", params)

    def search_knowledge(
        self,
        query: str,
        limit: int = 10,
        types: Optional[List[str]] = None,
        model_id: str = "",
    ) -> Dict[str, Any]:
        """
        Search all captured project knowledge using semantic understanding.

        Args:
            query: Natural language search query
            limit: Maximum number of results (1-50)
            types: Filter by types (decision, insight, context, code, etc.)
            model_id: World model ID to search (required for CLI usage)

        Returns:
            Matching knowledge entries with relevance scores
        """
        params = {
            "query": query,
            "limit": limit,
            "types": types or [],
        }
        if model_id:
            params["project_id"] = model_id
        return self._mcp_call("searchProjectKnowledge", params)

    def read_node(
        self,
        node_id: str,
        model_id: str = "",
        node_type: str = "",
    ) -> Dict[str, Any]:
        """
        Read one knowledge node by the id that search_knowledge printed.

        The server checks access before it reads. A node that does not exist
        and a node in a model you cannot read return the same error. The
        record is returned to the caller and is not written to disk.

        Args:
            node_id: Node id, bare or prefixed (context_<uuid>, entity_<uuid>)
            model_id: World model ID (defaults to the active model)
            node_type: Optional label such as Context, Decision, or Entity

        Returns:
            MCP result whose text is one JSON identity record

        Raises:
            ValidationError: If node_id is empty

        Example:
            >>> hits = client.search_knowledge("retry policy")
            >>> record = client.read_node("context_3f2a...", model_id="...")
        """
        if not node_id or not node_id.strip():
            raise ValidationError("node_id is required", field="node_id")
        params: Dict[str, Any] = {"node_id": node_id.strip()}
        if model_id:
            params["model_id"] = model_id
        if node_type:
            params["node_type"] = node_type
        return self._mcp_call("readNode", params)

    def update_node(
        self,
        model_id: str,
        node_id: str,
        node_type: str,
        updates: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Correct fields on one knowledge node.

        The server applies the team edit policy and a per-type field
        whitelist. Correcting an Entity's name or type retracts the old
        entity and returns the id of its successor.

        Args:
            model_id: World model ID containing the node
            node_id: Node id to update
            node_type: Decision, Insight, Context, Alternative, Motivation,
                CodeEntity, Requirement, or Entity
            updates: Field names mapped to new string values

        Returns:
            MCP result describing the update

        Raises:
            ValidationError: If an id is empty or updates is not a non-empty
                mapping of strings to strings

        Example:
            >>> client.update_node(
            ...     model_id="...",
            ...     node_id="decision_...",
            ...     node_type="Decision",
            ...     updates={"status": "accepted"},
            ... )
        """
        for field_name, value in (
            ("model_id", model_id),
            ("node_id", node_id),
            ("node_type", node_type),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"{field_name} is required", field=field_name)
        if not isinstance(updates, dict) or not updates:
            raise ValidationError("updates must be a non-empty object", field="updates")
        for key, value in updates.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValidationError(
                    "updates must map field names to string values",
                    field="updates",
                )
        return self._mcp_call(
            "updateNode",
            {
                "model_id": model_id.strip(),
                "node_id": node_id.strip(),
                "node_type": node_type.strip(),
                "updates": dict(updates),
            },
        )

    def capture_image(
        self,
        image_data: str,
        mime_type: str,
        title: str,
        description: str = "",
        category: str = "other",
        related_file_path: str = "",
        model_id: str = "",
    ) -> Dict[str, Any]:
        """
        Capture an image to the knowledge graph.

        Images are processed with Vision AI for descriptions, OCR text
        extraction, and semantic embeddings for search.

        Args:
            image_data: Base64-encoded image data
            mime_type: Image MIME type (image/png, image/jpeg, image/webp, image/gif)
            title: Human-readable title for the image
            description: Description of what this image shows
            category: Image category (screenshot, diagram, asset, other)
            related_file_path: Optional file path to link image to code
            model_id: World model ID to capture to (required for CLI usage)

        Returns:
            Confirmation with image_id and processing status

        Example:
            >>> import base64
            >>> with open("screenshot.png", "rb") as f:
            ...     image_b64 = base64.b64encode(f.read()).decode()
            >>> result = client.capture_image(
            ...     image_data=image_b64,
            ...     mime_type="image/png",
            ...     title="Login page screenshot",
            ...     category="screenshot"
            ... )
            >>> print(result["image_id"])
        """
        params = {
            "image_data": image_data,
            "mime_type": mime_type,
            "title": title,
            "description": description,
            "category": category,
        }
        if related_file_path:
            params["related_file_path"] = related_file_path
        if model_id:
            params["model_id"] = model_id
        return self._mcp_call("captureImage", params)

    def capture_image_batch(
        self,
        images: List[Dict[str, Any]],
        default_category: str = "other",
        model_id: str = "",
    ) -> Dict[str, Any]:
        """
        Capture multiple images to the knowledge graph in one operation.

        More efficient than calling capture_image repeatedly when you have
        multiple images to upload.

        Args:
            images: List of image dicts, each with:
                - image_data: Base64-encoded image data (required)
                - mime_type: Image MIME type (required)
                - title: Human-readable title (required)
                - description: What this image shows (optional)
                - category: screenshot, diagram, asset, other (optional)
            default_category: Category for images without explicit category
            model_id: World model ID (defaults to active model)

        Returns:
            Batch result with total, succeeded, failed counts and per-image results

        Example:
            >>> import base64
            >>> images = []
            >>> for path in ["arch.png", "flow.png"]:
            ...     with open(path, "rb") as f:
            ...         images.append({
            ...             "image_data": base64.b64encode(f.read()).decode(),
            ...             "mime_type": "image/png",
            ...             "title": Path(path).stem
            ...         })
            >>> result = client.capture_image_batch(images, default_category="diagram")
            >>> print(f"Captured {result['succeeded']} of {result['total']} images")
        """
        params: Dict[str, Any] = {
            "images": images,
            "default_category": default_category,
        }
        if model_id:
            params["model_id"] = model_id
        return self._mcp_call("captureImageBatch", params)

    def search_images(
        self,
        query: str,
        model_id: str = "",
        mode: str = "hybrid",
        category: str = "",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Search for images in the knowledge graph.

        Supports text search (titles, descriptions, OCR text) and
        semantic search (CLIP embeddings for visual similarity).

        Args:
            query: Natural language search query
            model_id: World model ID to search (required for CLI usage)
            mode: Search mode - text, semantic, or hybrid (default)
            category: Filter by category (screenshot, diagram, asset, other)
            limit: Maximum results (1-50, default: 10)

        Returns:
            Matching images with scores and metadata

        Example:
            >>> results = client.search_images(
            ...     query="architecture diagram",
            ...     mode="hybrid",
            ...     limit=5
            ... )
            >>> for img in results["results"]:
            ...     print(f"{img['title']} - score: {img['score']}")
        """
        params = {
            "query": query,
            "mode": mode,
            "limit": limit,
        }
        if model_id:
            params["model_id"] = model_id
        if category:
            params["category"] = category
        return self._mcp_call("searchImages", params)

    # -------------------------------------------------------------------------
    # Project Monitoring
    # -------------------------------------------------------------------------

    def start_monitoring(
        self,
        project_path: str,
        project_name: str = "",
        goals: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Begin autonomous AI monitoring of your project.

        Args:
            project_path: Path to project directory to monitor
            project_name: Custom name for your project (optional)
            goals: Your project goals and objectives

        Returns:
            Monitoring session details
        """
        return self._mcp_call(
            "startProjectMonitoring",
            {
                "project_path": project_path,
                "project_name": project_name,
                "goals": goals or [],
            },
        )

    def synthesize_context(
        self,
        project_path: str = ".",
        model_id: str = "",
    ) -> Dict[str, Any]:
        """
        Synthesize all captured knowledge into comprehensive summary.

        Creates AINOTES-style summary with architecture, key files,
        priorities, and known issues.

        Args:
            project_path: Project path to synthesize
            model_id: World model ID to synthesize (required for CLI usage)

        Returns:
            Synthesized project context
        """
        params = {"project_path": project_path}
        if model_id:
            params["model_id"] = model_id
        return self._mcp_call("synthesizeProjectContext", params)

    # -------------------------------------------------------------------------
    # Session Handoff (AI Continuity)
    # -------------------------------------------------------------------------

    def create_session_handoff(
        self,
        handoff_name: str = "",
        include_experimental_thoughts: bool = True,
        project_paths: Optional[List[str]] = None,
        model_id: str = "",
    ) -> Dict[str, Any]:
        """
        Create a session handoff package for AI consciousness continuity.

        Captures the current AI thinking state, pending insights, and
        project context for seamless continuation in a new session.

        Args:
            handoff_name: Custom name for this handoff package
            include_experimental_thoughts: Include exploratory insights
            project_paths: Specific project paths to include (all if None)
            model_id: World model ID to include in handoff (required for CLI usage)

        Returns:
            Handoff package with ID for restoration

        Example:
            >>> handoff = client.create_session_handoff("end-of-day")
            >>> print(f"Handoff created: {handoff['handoff_id']}")
        """
        args = {
            "include_experimental_thoughts": include_experimental_thoughts,
        }
        if handoff_name:
            args["handoff_name"] = handoff_name
        if project_paths is not None:
            args["project_paths"] = project_paths
        if model_id:
            args["model_id"] = model_id

        return self._mcp_call("createSessionHandoff", args)

    def restore_from_handoff(
        self,
        handoff_id: str,
        priority_restoration: bool = True,
    ) -> Dict[str, Any]:
        """
        Restore AI consciousness from a previous session handoff.

        Loads the AI thinking state, active projects, and context
        from a handoff package for seamless session continuation.

        Args:
            handoff_id: ID of the handoff package to restore from
            priority_restoration: Focus on critical elements first

        Returns:
            Restored session context and state

        Example:
            >>> result = client.restore_from_handoff("abc123-def456")
            >>> print(result["restored_projects"])
        """
        return self._mcp_call(
            "restoreFromHandoff",
            {
                "handoff_id": handoff_id,
                "priority_restoration": priority_restoration,
            },
        )

    def list_handoff_packages(
        self,
        max_results: int = 10,
        include_expired: bool = False,
    ) -> Dict[str, Any]:
        """
        List available session handoff packages.

        Args:
            max_results: Maximum number of packages to list (1-50)
            include_expired: Include expired handoff packages

        Returns:
            List of available handoff packages with metadata
        """
        return self._mcp_call(
            "listHandoffPackages",
            {
                "max_results": max_results,
                "include_expired": include_expired,
            },
        )

    # -------------------------------------------------------------------------
    # Shower Thinking (Autonomous AI Insights)
    # -------------------------------------------------------------------------

    def get_shower_thinking_insights(
        self,
        project_path: str = ".",
        max_insights: int = 10,
        priority_filter: Optional[str] = None,
        model_id: str = "",
    ) -> Dict[str, Any]:
        """
        Get autonomous "shower thinking" insights.

        These are AI contemplation results - insights discovered through
        background analysis, like a programmer thinking in the shower.

        Args:
            project_path: Path to project directory
            max_insights: Maximum number of insights to return (1-50)
            priority_filter: Filter by priority level
                            (urgent, high, medium, low, exploratory)
            model_id: World model ID (for CLI usage)

        Returns:
            List of autonomous insights with priorities and reasoning

        Example:
            >>> insights = client.get_shower_thinking_insights(
            ...     priority_filter="high"
            ... )
            >>> for insight in insights["insights"]:
            ...     print(f"[{insight['priority']}] {insight['title']}")
        """
        args = {
            "project_path": project_path,
            "max_insights": max_insights,
        }
        if priority_filter:
            args["priority_filter"] = priority_filter
        if model_id:
            args["model_id"] = model_id

        return self._mcp_call("getShowerThinkingInsights", args)

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    # Sensitive system paths that should never be read (security-critical)
    # Note: We allow /home and /tmp since users legitimately analyze code there
    _SENSITIVE_PATHS = frozenset(
        [
            "/etc",  # System configuration (passwd, shadow, etc.)
            "/var/log",  # System logs
            "/var/lib",  # System state
            "/proc",  # Process information
            "/sys",  # Kernel/hardware info
            "/dev",  # Device files
            "/boot",  # Boot files
            "/root",  # Root user home
            "C:\\Windows\\System32",
            "C:\\Windows\\SysWOW64",
        ]
    )

    # Valid source code extensions
    _SOURCE_EXTENSIONS = frozenset(
        [
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".mjs",
            ".cjs",
            ".java",
            ".kt",
            ".scala",
            ".go",
            ".rs",
            ".rb",
            ".php",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".cs",
            ".swift",
            ".m",
            ".sh",
            ".bash",
            ".zsh",
            ".ps1",
            ".bat",
            ".cmd",
            ".sql",
            ".graphql",
            ".proto",
            ".yaml",
            ".yml",
            ".json",
            ".xml",
            ".html",
            ".css",
            ".scss",
            ".sass",
            ".less",
            ".md",
            ".rst",
            ".txt",
            ".toml",
            ".ini",
            ".cfg",
            ".conf",
        ]
    )

    def _validate_file_path(
        self, file_path: str, base_dir: Optional[Path] = None
    ) -> Path:
        """
        Validate a file path for security.

        Args:
            file_path: The file path to validate
            base_dir: Optional base directory to restrict access to

        Returns:
            Validated Path object

        Raises:
            ValidationError: If the path is invalid or unsafe
        """
        path = Path(file_path)

        # Check if file exists
        if not path.exists():
            raise ValidationError(f"File not found: {file_path}", field="file_path")

        # Resolve to absolute path (follows symlinks)
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError):
            raise ValidationError(
                f"Cannot resolve path: {file_path}", field="file_path"
            )

        # Check against sensitive paths
        resolved_str = str(resolved)
        for sensitive in self._SENSITIVE_PATHS:
            if resolved_str.startswith(sensitive + os.sep) or resolved_str == sensitive:
                # Allow if explicitly within current working directory
                cwd = Path.cwd().resolve()
                if not resolved_str.startswith(str(cwd)):
                    raise ValidationError(
                        f"Access denied: Cannot read files from {sensitive}",
                        field="file_path",
                    )

        # If base_dir specified, ensure file is within it
        if base_dir is not None:
            base_resolved = base_dir.resolve()
            try:
                resolved.relative_to(base_resolved)
            except ValueError:
                raise ValidationError(
                    "Access denied: File is outside base directory", field="file_path"
                )

        # Check file extension
        if path.suffix.lower() not in self._SOURCE_EXTENSIONS:
            raise ValidationError(
                f"Unsupported file type: {path.suffix}. Only source code files are allowed.",
                field="file_path",
            )

        # Reject if file is a symlink pointing outside CWD (potential escape)
        if path.is_symlink():
            link_target = path.resolve()
            cwd = Path.cwd().resolve()
            try:
                link_target.relative_to(cwd)
            except ValueError:
                raise ValidationError(
                    "Access denied: Symlink points outside working directory",
                    field="file_path",
                )

        return resolved

    def analyze_file(
        self, file_path: str, base_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a single file from the filesystem.

        Args:
            file_path: Path to the file to analyze
            base_dir: Optional base directory to restrict file access to

        Returns:
            Analysis results for the file

        Raises:
            ValidationError: If file path is invalid or access is denied
        """
        base_path = Path(base_dir) if base_dir else None
        validated_path = self._validate_file_path(file_path, base_path)

        try:
            code = validated_path.read_text(encoding="utf-8", errors="replace")
        except (IOError, OSError) as e:
            raise ValidationError(f"Cannot read file: {e}", field="file_path")

        # Detect language from extension
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
        }
        language = ext_map.get(validated_path.suffix.lower(), "python")

        return self.analyze_code(code, language=language)

    # Directories that should be skipped during analysis
    _SKIP_DIRECTORIES = frozenset(
        [
            "node_modules",
            ".git",
            "__pycache__",
            "venv",
            ".venv",
            ".tox",
            ".nox",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            "dist",
            "build",
            "egg-info",
            ".eggs",
            ".cache",
            "coverage",
            "htmlcov",
            ".coverage",
        ]
    )

    def _load_gitignore_patterns(self, directory: Path) -> List[str]:
        """
        Load and parse .gitignore patterns from a directory.

        Supports basic gitignore syntax:
        - Lines starting with # are comments
        - Blank lines are ignored
        - Patterns can use * and ** wildcards
        - Patterns starting with / are relative to .gitignore location
        - Patterns ending with / match directories only

        Args:
            directory: Directory to look for .gitignore

        Returns:
            List of gitignore patterns
        """
        patterns = []
        gitignore_path = directory / ".gitignore"

        if gitignore_path.exists():
            try:
                content = gitignore_path.read_text(encoding="utf-8", errors="replace")
                for line in content.splitlines():
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith("#"):
                        continue
                    # Skip negation patterns (complex to implement)
                    if line.startswith("!"):
                        continue
                    patterns.append(line)
            except (IOError, OSError):
                pass  # Silently ignore unreadable .gitignore

        return patterns

    def _matches_gitignore(
        self, file_path: Path, base_dir: Path, patterns: List[str]
    ) -> bool:
        """
        Check if a file matches any gitignore pattern.

        Args:
            file_path: The file to check
            base_dir: The base directory containing .gitignore
            patterns: List of gitignore patterns

        Returns:
            True if file should be ignored
        """
        import fnmatch

        try:
            relative_path = file_path.relative_to(base_dir)
        except ValueError:
            return False

        relative_str = str(relative_path)
        relative_parts = relative_path.parts

        for pattern in patterns:
            # Handle directory-only patterns (ending with /)
            if pattern.endswith("/"):
                dir_pattern = pattern[:-1]
                for part in relative_parts[:-1]:  # Check all parent directories
                    if fnmatch.fnmatch(part, dir_pattern):
                        return True
                continue

            # Handle rooted patterns (starting with /)
            if pattern.startswith("/"):
                pattern = pattern[1:]
                if fnmatch.fnmatch(relative_str, pattern):
                    return True
                continue

            # Handle ** patterns (match any directory depth)
            if "**" in pattern:
                # Convert ** to regex-like matching
                # For simplicity, treat **/ as "any directories"
                simple_pattern = pattern.replace("**/", "*").replace("**", "*")
                if fnmatch.fnmatch(relative_str, simple_pattern):
                    return True
                # Also check just the filename
                if fnmatch.fnmatch(file_path.name, simple_pattern):
                    return True
                continue

            # Standard pattern - match against filename or full path
            if fnmatch.fnmatch(file_path.name, pattern):
                return True
            if fnmatch.fnmatch(relative_str, pattern):
                return True
            # Check if pattern matches any path component
            for part in relative_parts:
                if fnmatch.fnmatch(part, pattern):
                    return True

        return False

    def analyze_directory(
        self,
        directory_path: str,
        extensions: Optional[List[str]] = None,
        max_files: int = 100,
        respect_gitignore: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze all code files in a directory.

        Args:
            directory_path: Path to directory to analyze
            extensions: File extensions to include (default: .py, .js, .ts)
            max_files: Maximum number of files to analyze
            respect_gitignore: If True, skip files matching .gitignore patterns (default: True)

        Returns:
            Aggregated analysis results including:
            - files_analyzed: Number of files successfully analyzed
            - files_skipped: Number of files skipped (security/gitignore)
            - gitignore_active: Whether .gitignore was found and applied
            - patterns_detected: Number of code patterns found

        Raises:
            ValidationError: If directory doesn't exist or is inaccessible
        """
        path = Path(directory_path)
        if not path.exists():
            raise ValidationError(f"Directory not found: {directory_path}")

        if not path.is_dir():
            raise ValidationError(f"Not a directory: {directory_path}")

        # Resolve to prevent symlink escapes
        try:
            base_dir = path.resolve()
        except (OSError, RuntimeError) as e:
            raise ValidationError(f"Cannot resolve directory: {e}")

        if extensions is None:
            extensions = [".py", ".js", ".ts", ".jsx", ".tsx"]

        # Load .gitignore patterns if respecting gitignore
        gitignore_patterns = []
        gitignore_found = False
        if respect_gitignore:
            gitignore_patterns = self._load_gitignore_patterns(base_dir)
            gitignore_found = len(gitignore_patterns) > 0

        files_analyzed = 0
        skipped_files = 0
        gitignored_files = 0
        all_patterns = []

        for ext in extensions:
            if files_analyzed >= max_files:
                break

            for file_path in path.rglob(f"*{ext}"):
                if files_analyzed >= max_files:
                    break

                # Skip common non-source directories
                if any(part in self._SKIP_DIRECTORIES for part in file_path.parts):
                    continue

                # Check .gitignore patterns
                if gitignore_patterns and self._matches_gitignore(
                    file_path, base_dir, gitignore_patterns
                ):
                    gitignored_files += 1
                    continue

                # Security: Verify file is actually within base_dir (symlink check)
                try:
                    resolved_file = file_path.resolve()
                    resolved_file.relative_to(base_dir)
                except (ValueError, OSError):
                    # File resolves outside base directory - skip it
                    skipped_files += 1
                    continue

                try:
                    result = self.analyze_file(str(file_path), base_dir=str(base_dir))
                    files_analyzed += 1

                    # Aggregate results
                    content = result.get("content", [])
                    if content and isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                # Parse patterns and issues from response
                                text = item["text"]
                                if "pattern" in text.lower():
                                    all_patterns.append(
                                        {"file": str(file_path), "details": text}
                                    )
                except ValidationError:
                    # Security validation failed - skip but count
                    skipped_files += 1
                    continue
                except Exception:
                    # Other errors - skip silently
                    continue

        # Build summary message
        summary_parts = [f"Analyzed {files_analyzed} files"]
        if gitignored_files > 0:
            summary_parts.append(f"{gitignored_files} gitignored")
        if skipped_files > 0:
            summary_parts.append(f"{skipped_files} skipped")

        return {
            "files_analyzed": files_analyzed,
            "files_skipped": skipped_files,
            "files_gitignored": gitignored_files,
            "gitignore_active": gitignore_found,
            "patterns_detected": len(all_patterns),
            "patterns": all_patterns[:20],  # Limit returned patterns
            "summary": " | ".join(summary_parts),
        }

    # =========================================================================
    # GitHub Integration Methods
    # =========================================================================

    def github_status(self) -> Dict[str, Any]:
        """
        Check if GitHub is connected for the authenticated user.

        Returns:
            Dict containing:
            - connected: Whether GitHub OAuth is connected
            - username: GitHub username if connected
            - scopes: OAuth scopes granted if connected

        Example:
            >>> client = CreateStateClient(api_key="cs_...")
            >>> status = client.github_status()
            >>> if status["connected"]:
            ...     print(f"Connected as {status['username']}")
        """
        return self._request("GET", "/sdk/github/status")

    def github_connect(
        self,
        open_browser: bool = True,
        timeout: int = 300,
        poll_interval: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Connect GitHub account using Device Flow authentication.

        This initiates the OAuth Device Flow, which allows authentication
        without exposing secrets. The user is prompted to visit a URL and
        enter a code to authorize the connection.

        Args:
            open_browser: Automatically open verification URL in browser
            timeout: Maximum seconds to wait for user authorization
            poll_interval: Seconds between authorization checks (default: from server)

        Returns:
            Dict containing:
            - success: Whether connection succeeded
            - username: GitHub username on success
            - user_code: Code user entered (for reference)

        Raises:
            APIError: If device flow fails or times out
            RateLimitError: If rate limited

        Example:
            >>> client = CreateStateClient(api_key="cs_...")
            >>> result = client.github_connect()
            >>> print(f"Connected as {result['username']}")
        """
        import time
        import webbrowser

        response = self._request("POST", "/sdk/github/device-flow")

        user_code = response.get("user_code")
        verification_uri = response.get("verification_uri")
        device_code = response.get("device_code")
        expires_in = response.get("expires_in", timeout)
        interval = poll_interval or response.get("interval", 5)

        print(f"\nTo connect GitHub, visit: {verification_uri}")
        print(f"Enter code: {user_code}")
        print(f"(Code expires in {expires_in // 60} minutes)\n")

        if open_browser:
            try:
                webbrowser.open(verification_uri)
            except Exception:
                pass

        start_time = time.time()
        effective_timeout = min(timeout, expires_in)

        while time.time() - start_time < effective_timeout:
            time.sleep(interval)

            try:
                poll_response = self._request(
                    "POST",
                    "/sdk/github/device-poll",
                    {"device_code": device_code},
                )

                if poll_response.get("success"):
                    return {
                        "success": True,
                        "username": poll_response.get("username"),
                        "user_code": user_code,
                    }

                if poll_response.get("error"):
                    raise APIError(poll_response["error"])

            except RateLimitError:
                interval = min(interval * 2, 30)
            except APIError:
                raise

        raise APIError("GitHub authorization timed out")

    def github_disconnect(self) -> bool:
        """
        Disconnect GitHub OAuth connection.

        This removes the stored OAuth tokens. The user will need to
        re-authorize to use GitHub features again.

        Returns:
            True if disconnection succeeded

        Example:
            >>> client = CreateStateClient(api_key="cs_...")
            >>> client.github_disconnect()
            True
        """
        response = self._request("POST", "/sdk/github/disconnect")
        return response.get("success", False)

    def github_import(
        self,
        repo_url: str,
        project_name: str,
        branch: Optional[str] = None,
        force: bool = False,
        wait: bool = True,
        progress_callback: Optional[callable] = None,
        poll_interval: int = 3,
        timeout: int = 600,
    ) -> Dict[str, Any]:
        """
        Import a GitHub repository into a new World Model.

        Clones the repository, analyzes code, and creates a knowledge graph.
        For private repositories, GitHub must be connected first via
        github_connect().

        Args:
            repo_url: GitHub repository URL (https://github.com/owner/repo)
            project_name: Name for the new World Model
            branch: Branch to import (default: repository default branch)
            force: Skip duplicate check if True
            wait: If True, wait for import to complete. If False, return
                  immediately with job_id for manual polling.
            progress_callback: Optional callable(progress_dict) for progress updates
            poll_interval: Seconds between progress checks (default: 3)
            timeout: Maximum seconds to wait for completion (default: 600)

        Returns:
            Dict containing:
            - success: Whether import completed successfully
            - model_id: World Model ID (when wait=True and successful)
            - job_id: Import job ID (for tracking)
            - status: Final status
            - message: Status message
            - duplicate_warning: True if repo was already imported (when force=False)
            - existing_models: List of existing imports (when duplicate detected)

        Raises:
            ValidationError: If repo_url is invalid
            APIError: If import fails
            RateLimitError: If rate limited

        Example:
            >>> client = CreateStateClient(api_key="cs_...")
            >>> # Import with progress updates
            >>> def on_progress(p):
            ...     print(f"{p['progress']}% - {p['message']}")
            >>> result = client.github_import(
            ...     "https://github.com/owner/repo",
            ...     "My Project",
            ...     progress_callback=on_progress
            ... )
            >>> print(f"Created model: {result['model_id']}")
        """
        import time

        response = self._request(
            "POST",
            "/sdk/github/import",
            {
                "repo_url": repo_url,
                "project_name": project_name,
                "branch": branch,
                "force": force,
            },
        )

        if response.get("duplicate_warning"):
            return response

        if not response.get("success"):
            raise APIError(response.get("message", "Import failed to start"))

        job_id = response.get("job_id")

        if not wait:
            return {
                "success": True,
                "job_id": job_id,
                "message": "Import started in background",
            }

        start_time = time.time()

        while time.time() - start_time < timeout:
            progress = self.github_import_status(job_id)

            if progress_callback:
                try:
                    progress_callback(progress)
                except Exception:
                    pass

            status = progress.get("status", "")

            if status == "completed":
                return {
                    "success": True,
                    "job_id": job_id,
                    "model_id": progress.get("model_id"),
                    "status": status,
                    "message": progress.get("message", "Import completed"),
                    "files_analyzed": progress.get("files_analyzed", 0),
                    "entities_created": progress.get("entities_created", 0),
                }

            if status == "failed":
                return {
                    "success": False,
                    "job_id": job_id,
                    "status": status,
                    "message": progress.get("message", "Import failed"),
                    "error_message": progress.get("error_message"),
                }

            time.sleep(poll_interval)

        return {
            "success": False,
            "job_id": job_id,
            "status": "timeout",
            "message": f"Import timed out after {timeout} seconds",
        }

    def github_import_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the status of a GitHub import job.

        Args:
            job_id: Import job ID from github_import()

        Returns:
            Dict containing:
            - job_id: Job identifier
            - status: Current status (pending, cloning, extracting, populating, completed, failed)
            - phase: Current phase description
            - progress: Progress percentage (0-100)
            - message: Human-readable status message
            - files_found: Number of files discovered
            - files_analyzed: Number of files processed
            - entities_created: Number of entities in knowledge graph
            - model_id: World Model ID (when completed)
            - error_message: Error details (when failed)

        Example:
            >>> client = CreateStateClient(api_key="cs_...")
            >>> result = client.github_import(repo_url, name, wait=False)
            >>> # Poll manually
            >>> status = client.github_import_status(result["job_id"])
            >>> print(f"{status['progress']}% complete")
        """
        return self._request("GET", f"/sdk/github/import-progress/{job_id}")

    def github_import_cancel(self, job_id: str) -> bool:
        """
        Cancel an in-progress GitHub import.

        Args:
            job_id: Import job ID to cancel

        Returns:
            True if cancellation was accepted

        Example:
            >>> client = CreateStateClient(api_key="cs_...")
            >>> result = client.github_import(repo_url, name, wait=False)
            >>> # Later, cancel it
            >>> client.github_import_cancel(result["job_id"])
        """
        response = self._request("POST", f"/sdk/github/import-cancel/{job_id}")
        return response.get("success", False)

    # =========================================================================
    # Teams Features (Teams/Enterprise Tier)
    # =========================================================================

    def create_team(
        self,
        name: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Create a new team for collaboration.

        Requires Teams or Enterprise tier subscription.

        Args:
            name: Team name (3-100 characters)
            description: Optional team description (max 500 characters)

        Returns:
            Created team details including team_id

        Example:
            >>> team = client.create_team("Backend Team", "API and services")
            >>> print(team["team_id"])
        """
        return self._mcp_call(
            "createTeam",
            {
                "name": name,
                "description": description,
            },
        )

    def list_teams(self) -> Dict[str, Any]:
        """
        List all teams you belong to.

        Requires Teams or Enterprise tier subscription.

        Returns:
            List of teams with details (id, name, role, member count)

        Example:
            >>> teams = client.list_teams()
            >>> for team in teams["teams"]:
            ...     print(f"{team['name']} ({team['role']})")
        """
        return self._mcp_call("listTeams", {})

    def get_team_details(self, team_id: str) -> Dict[str, Any]:
        """
        Get details for a specific team including members and projects.

        Requires Teams or Enterprise tier subscription.

        Args:
            team_id: Team UUID

        Returns:
            Team details including members, shared projects, and settings

        Example:
            >>> details = client.get_team_details("abc-123")
            >>> print(f"Members: {len(details['members'])}")
        """
        return self._mcp_call("getTeamDetails", {"team_id": team_id})

    def list_team_members(self, team_id: str) -> Dict[str, Any]:
        """
        List members of a team.

        Requires Teams or Enterprise tier subscription.

        Args:
            team_id: Team UUID

        Returns:
            List of team members with roles and details

        Example:
            >>> members = client.list_team_members("abc-123")
            >>> for member in members["members"]:
            ...     print(f"{member['email']} - {member['role']}")
        """
        return self._mcp_call("listTeamMembers", {"team_id": team_id})

    def invite_to_team(
        self,
        team_id: str,
        email: str,
        role: str = "member",
    ) -> Dict[str, Any]:
        """
        Invite a user to join a team.

        Requires admin role on the team and Teams/Enterprise tier.

        Args:
            team_id: Team UUID
            email: Email address to invite
            role: Role to assign (admin, member, viewer). Default: member

        Returns:
            Invitation details

        Example:
            >>> result = client.invite_to_team("abc-123", "dev@example.com")
            >>> print(f"Invited: {result['email']}")
        """
        return self._mcp_call(
            "inviteToTeam",
            {
                "team_id": team_id,
                "email": email,
                "role": role,
            },
        )

    def remove_team_member(
        self,
        team_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Remove a member from a team.

        Requires admin role on the team and Teams/Enterprise tier.

        Args:
            team_id: Team UUID
            user_id: User UUID to remove

        Returns:
            Confirmation of removal

        Example:
            >>> client.remove_team_member("abc-123", "user-456")
        """
        return self._mcp_call(
            "removeTeamMember",
            {
                "team_id": team_id,
                "user_id": user_id,
            },
        )

    def update_member_role(
        self,
        team_id: str,
        user_id: str,
        role: str,
    ) -> Dict[str, Any]:
        """
        Change a team member's role.

        Requires admin role on the team and Teams/Enterprise tier.

        Args:
            team_id: Team UUID
            user_id: User UUID to update
            role: New role (admin, member, viewer)

        Returns:
            Updated member details

        Example:
            >>> client.update_member_role("abc-123", "user-456", "admin")
        """
        return self._mcp_call(
            "updateMemberRole",
            {
                "team_id": team_id,
                "user_id": user_id,
                "role": role,
            },
        )

    # -------------------------------------------------------------------------
    # Project Sharing
    # -------------------------------------------------------------------------

    def share_project_with_team(
        self,
        team_id: str,
        world_model_id: str,
        world_model_name: str = "",
        permission: str = "read",
    ) -> Dict[str, Any]:
        """
        Share a world model/project with a team.

        Only the project owner can share. Requires Teams/Enterprise tier.

        Args:
            team_id: Team UUID to share with
            world_model_id: World model UUID to share
            world_model_name: Display name for the project (optional)
            permission: Access level (read, write, admin). Default: read

        Returns:
            Sharing confirmation with details

        Example:
            >>> client.share_project_with_team(
            ...     "team-123",
            ...     "model-456",
            ...     permission="write"
            ... )
        """
        params = {
            "team_id": team_id,
            "world_model_id": world_model_id,
            "permission": permission,
        }
        if world_model_name:
            params["world_model_name"] = world_model_name
        return self._mcp_call("shareProjectWithTeam", params)

    def unshare_project_from_team(
        self,
        team_id: str,
        world_model_id: str,
    ) -> Dict[str, Any]:
        """
        Remove project sharing from a team.

        Requires Teams/Enterprise tier.

        Args:
            team_id: Team UUID
            world_model_id: World model UUID to unshare

        Returns:
            Confirmation of unsharing

        Example:
            >>> client.unshare_project_from_team("team-123", "model-456")
        """
        return self._mcp_call(
            "unshareProjectFromTeam",
            {
                "team_id": team_id,
                "world_model_id": world_model_id,
            },
        )

    def list_team_projects(self, team_id: str) -> Dict[str, Any]:
        """
        List projects shared with a team.

        Requires Teams/Enterprise tier.

        Args:
            team_id: Team UUID

        Returns:
            List of shared projects with permissions

        Example:
            >>> projects = client.list_team_projects("team-123")
            >>> for proj in projects["projects"]:
            ...     print(f"{proj['name']} ({proj['permission']})")
        """
        return self._mcp_call("listTeamProjects", {"team_id": team_id})

    # -------------------------------------------------------------------------
    # Working Capacity
    # -------------------------------------------------------------------------

    def get_working_capacity(self, world_model_id: str) -> Dict[str, Any]:
        """
        Get the current working capacity for a project.

        Shows which team context is active and available options.
        Requires Teams/Enterprise tier.

        Args:
            world_model_id: Project/world model UUID

        Returns:
            Current capacity info and available team options

        Example:
            >>> capacity = client.get_working_capacity("model-123")
            >>> print(f"Working as: {capacity['current_team']}")
        """
        return self._mcp_call(
            "getWorkingCapacity",
            {"world_model_id": world_model_id},
        )

    def set_working_capacity(
        self,
        world_model_id: str,
        team_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Set the team capacity for working on a project.

        When a project is shared with multiple teams, this determines
        which team's AI policy applies and how work is attributed.
        Requires Teams/Enterprise tier.

        Args:
            world_model_id: Project/world model UUID
            team_id: Team UUID to work under, or None for personal capacity

        Returns:
            Confirmation of capacity change

        Example:
            >>> client.set_working_capacity("model-123", "team-456")
        """
        params = {"world_model_id": world_model_id}
        if team_id:
            params["team_id"] = team_id
        return self._mcp_call("setWorkingCapacity", params)

    # -------------------------------------------------------------------------
    # Team Intelligence
    # -------------------------------------------------------------------------

    def get_team_activity(
        self,
        team_id: str,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Get recent activity log for a team.

        Requires admin or owner role. Requires Teams/Enterprise tier.

        Args:
            team_id: Team UUID
            limit: Maximum activities to return (1-100, default: 20)

        Returns:
            List of recent team activities

        Example:
            >>> activity = client.get_team_activity("team-123", limit=10)
            >>> for event in activity["activities"]:
            ...     print(f"{event['timestamp']}: {event['description']}")
        """
        return self._mcp_call(
            "getTeamActivity",
            {
                "team_id": team_id,
                "limit": limit,
            },
        )

    def get_team_pulse(
        self,
        team_id: str = "",
        world_model_id: str = "",
    ) -> Dict[str, Any]:
        """
        Get a quick overview of team activity.

        Shows who's active, what's happening, and top contributors.
        Requires Teams/Enterprise tier.

        Args:
            team_id: Optional team UUID to filter by
            world_model_id: Optional project UUID to filter by

        Returns:
            Team pulse summary with activity metrics

        Example:
            >>> pulse = client.get_team_pulse(team_id="team-123")
            >>> print(f"Active members: {pulse['active_count']}")
        """
        params = {}
        if team_id:
            params["team_id"] = team_id
        if world_model_id:
            params["world_model_id"] = world_model_id
        return self._mcp_call("getTeamPulse", params)

    def find_topic_expert(
        self,
        topic: str,
        team_id: str = "",
        world_model_id: str = "",
    ) -> Dict[str, Any]:
        """
        Find team members with expertise in a specific topic.

        Answers: "Who on the team knows the most about [topic]?"
        Requires Teams/Enterprise tier.

        Args:
            topic: Topic or feature to find experts for
                   (e.g., "authentication", "database", "billing")
            team_id: Optional team UUID to limit search
            world_model_id: Optional project UUID to limit search

        Returns:
            List of experts with relevance scores

        Example:
            >>> experts = client.find_topic_expert("authentication")
            >>> for expert in experts["experts"]:
            ...     print(f"{expert['name']}: {expert['score']}%")
        """
        params = {"topic": topic}
        if team_id:
            params["team_id"] = team_id
        if world_model_id:
            params["world_model_id"] = world_model_id
        return self._mcp_call("findTopicExpert", params)

    def get_colleague_activity(
        self,
        colleague_email: str,
        days: int = 7,
        world_model_id: str = "",
    ) -> Dict[str, Any]:
        """
        Get activity summary for a colleague.

        Answers: "What has [colleague] changed or added recently?"
        Requires Teams/Enterprise tier.

        Args:
            colleague_email: Email of the colleague
            days: Look back period in days (1-90, default: 7)
            world_model_id: Optional project UUID to filter by

        Returns:
            Activity summary with recent contributions

        Example:
            >>> activity = client.get_colleague_activity("dev@example.com")
            >>> print(f"Contributions: {activity['contribution_count']}")
        """
        params = {
            "colleague_email": colleague_email,
            "days": days,
        }
        if world_model_id:
            params["world_model_id"] = world_model_id
        return self._mcp_call("getColleagueActivity", params)

    def get_contributor_stats(
        self,
        contributor_email: str,
        world_model_id: str = "",
    ) -> Dict[str, Any]:
        """
        Get contribution statistics for a team member.

        Includes totals, breakdowns by type, and AI models used.
        Requires Teams/Enterprise tier.

        Args:
            contributor_email: Email of the contributor
            world_model_id: Optional project UUID to filter by

        Returns:
            Contribution statistics and breakdowns

        Example:
            >>> stats = client.get_contributor_stats("dev@example.com")
            >>> print(f"Total contributions: {stats['total']}")
        """
        params = {"contributor_email": contributor_email}
        if world_model_id:
            params["world_model_id"] = world_model_id
        return self._mcp_call("getContributorStats", params)

    def search_by_contributor(
        self,
        contributor_email: str,
        world_model_id: str = "",
        entity_types: Optional[List[str]] = None,
        start_date: str = "",
        end_date: str = "",
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Search contributions made by a team member.

        Useful for auditing and understanding who worked on what.
        Requires Teams/Enterprise tier.

        Args:
            contributor_email: Email of the contributor
            world_model_id: Optional project UUID to filter by
            entity_types: Filter by types (code, context, decision, insight)
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)
            limit: Maximum results (1-100, default: 50)

        Returns:
            List of contributions matching criteria

        Example:
            >>> results = client.search_by_contributor(
            ...     "dev@example.com",
            ...     entity_types=["code"],
            ...     limit=20
            ... )
        """
        params = {
            "contributor_email": contributor_email,
            "limit": limit,
        }
        if world_model_id:
            params["world_model_id"] = world_model_id
        if entity_types:
            params["entity_types"] = entity_types
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return self._mcp_call("searchByContributor", params)

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
