"""
Create State Python SDK

Enterprise AI Code Intelligence Platform - Python Client Library.
Provides programmatic access to Create State's knowledge graph, code analysis,
and AI-powered development tools.

Usage:
    from createstate import CreateStateClient

    client = CreateStateClient(api_key="your-api-key")
    result = client.analyze_code("def hello(): pass", language="python")

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

from .client import CreateStateClient
from .exceptions import (
    APIError,
    AuthenticationError,
    CreateStateError,
    RateLimitError,
    ValidationError,
)

__version__ = "0.1.25"
__all__ = [
    "CreateStateClient",
    "CreateStateError",
    "AuthenticationError",
    "APIError",
    "RateLimitError",
    "ValidationError",
]
