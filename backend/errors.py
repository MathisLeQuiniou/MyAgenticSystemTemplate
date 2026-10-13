"""Errors raised on purpose by the application.

Every error inherits from `AppError` and carries the HTTP status it maps to.
The API turns them into `{"detail": message}` responses with that status
(see `register_error_handlers` in `backend.api.main`), so routes don't need
their own try/except. Add a new case by subclassing the closest error:

    class GraphBusyError(ConflictError):
        \"\"\"The graph is already running for this thread.\"\"\"

Unexpected exceptions (bugs) are deliberately NOT `AppError`s: they still
surface as 500s instead of being mistaken for a user mistake.
"""

from __future__ import annotations


class AppError(Exception):
    """Base of every error raised on purpose by the application."""

    status_code: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# --- 404 ---------------------------------------------------------------------
class NotFoundError(AppError):
    """A requested resource does not exist."""

    status_code = 404


class GraphNotFoundError(NotFoundError):
    """No graph is registered under this name."""


class SkillNotFoundError(NotFoundError):
    """No skill is loaded under this name."""


class ModelProfileNotFoundError(NotFoundError):
    """No model profile is defined under this name in models.yaml."""


class RunNotFoundError(NotFoundError):
    """No run exists with this id."""


# --- 409 ---------------------------------------------------------------------
class ConflictError(AppError):
    """The action is incompatible with the current state of the resource."""

    status_code = 409


class RunActiveError(ConflictError):
    """The run is still pending/running and must be cancelled first."""
