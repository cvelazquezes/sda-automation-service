"""Custom exceptions for the automation service."""


class AutomationError(Exception):
    """Base exception for automation errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class LoginError(AutomationError):
    """Raised when login fails."""

    pass


class NavigationError(AutomationError):
    """Raised when page navigation fails."""

    pass


class ElementNotFoundError(AutomationError):
    """Raised when an expected element is not found."""

    pass


class SessionExpiredError(AutomationError):
    """Raised when a session has expired."""

    pass


class BrowserError(AutomationError):
    """Raised when browser operations fail."""

    pass
