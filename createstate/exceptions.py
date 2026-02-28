"""
Create State SDK Exceptions

Custom exception classes for the Create State Python SDK. These exceptions
provide structured error handling for API errors, authentication failures,
rate limiting, and input validation.

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


class CreateStateError(Exception):
    """Base exception for all Create State SDK errors."""

    def __init__(self, message: str, status_code: int = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class AuthenticationError(CreateStateError):
    """Raised when API authentication fails."""

    def __init__(self, message: str = "Invalid or missing API key"):
        super().__init__(message, status_code=401)


class APIError(CreateStateError):
    """Raised when the API returns an error response."""

    pass


class RateLimitError(CreateStateError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = None):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class ValidationError(CreateStateError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: str = None):
        super().__init__(message, status_code=400)
        self.field = field
