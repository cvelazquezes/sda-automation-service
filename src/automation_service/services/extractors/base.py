"""
Base extractor class and registry for modular data extraction.

This module provides the foundation for all data extractors in the
automation service. Each extractor is responsible for navigating to
a specific section of Club Virtual and extracting structured data.

Architecture:
------------
                    ┌─────────────────┐
                    │  BaseExtractor  │ (Abstract)
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐  ┌─────────────────┐  ┌──────────────────┐
│ProfileExtractor│  │ TasksExtractor  │  │SpecialtiesExtractor│
└───────────────┘  └─────────────────┘  └──────────────────┘

Creating a New Extractor:
------------------------
1. Create a new file in extractors/ (e.g., my_extractor.py)
2. Inherit from BaseExtractor
3. Implement the required abstract methods
4. Register via @ExtractorRegistry.register decorator

Example:
    @ExtractorRegistry.register
    class MyExtractor(BaseExtractor):
        name = "my_data"
        description = "Extracts my custom data"

        async def extract(self, page: Page) -> dict:
            # Navigate and extract data
            return {"my_field": "value"}
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

import structlog

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = structlog.get_logger()


class ExtractorRegistry:
    """
    Registry for all available data extractors.

    The registry allows dynamic discovery and instantiation of extractors
    by name, which enables the configurable extraction endpoint.

    Usage:
        # Register an extractor (use decorator)
        @ExtractorRegistry.register
        class MyExtractor(BaseExtractor):
            ...

        # Get extractor by name
        extractor = ExtractorRegistry.get("profile")

        # List all available extractors
        names = ExtractorRegistry.list_extractors()
    """

    _extractors: ClassVar[dict[str, type["BaseExtractor"]]] = {}

    @classmethod
    def register(cls, extractor_class: type["BaseExtractor"]) -> type["BaseExtractor"]:
        """
        Register an extractor class.

        Can be used as a decorator:
            @ExtractorRegistry.register
            class MyExtractor(BaseExtractor):
                ...

        Args:
            extractor_class: The extractor class to register

        Returns:
            The same class (for decorator usage)
        """
        name = extractor_class.name
        if name in cls._extractors:
            logger.warning(
                "Overwriting existing extractor",
                name=name,
                old_class=cls._extractors[name].__name__,
                new_class=extractor_class.__name__,
            )
        cls._extractors[name] = extractor_class
        logger.debug("Registered extractor", name=name, class_name=extractor_class.__name__)
        return extractor_class

    @classmethod
    def get(cls, name: str) -> "BaseExtractor":
        """
        Get an extractor instance by name.

        Args:
            name: The extractor name (e.g., "profile", "tasks")

        Returns:
            An instance of the requested extractor

        Raises:
            ValueError: If extractor name is not found
        """
        if name not in cls._extractors:
            available = list(cls._extractors.keys())
            raise ValueError(f"Unknown extractor: '{name}'. Available: {available}")
        return cls._extractors[name]()

    @classmethod
    def list_extractors(cls) -> list[str]:
        """
        List all registered extractor names.

        Returns:
            List of extractor names
        """
        return list(cls._extractors.keys())

    @classmethod
    def get_all(cls) -> dict[str, "BaseExtractor"]:
        """
        Get instances of all registered extractors.

        Returns:
            Dict mapping names to extractor instances
        """
        return {name: ext_class() for name, ext_class in cls._extractors.items()}


class BaseExtractor(ABC):
    """
    Abstract base class for all data extractors.

    Each extractor is responsible for:
    1. Navigating to a specific section of Club Virtual
    2. Extracting structured data from the page
    3. Returning the data in a consistent format

    Subclasses must implement:
    - name: Unique identifier for this extractor
    - description: Human-readable description
    - extract(): The main extraction logic

    Attributes:
        name: Unique identifier (e.g., "profile", "tasks")
        description: Human-readable description of what this extracts
        requires_navigation: Whether this extractor needs to navigate away
    """

    # Class attributes to be overridden by subclasses
    name: str = ""
    description: str = ""
    requires_navigation: bool = True  # Most extractors navigate to a new page

    def __init__(self) -> None:
        """Initialize the extractor."""
        if not self.name:
            raise ValueError(f"{self.__class__.__name__} must define 'name' attribute")

    @abstractmethod
    async def extract(self, page: "Page", base_url: str) -> dict[str, Any]:
        """
        Extract data from Club Virtual.

        This method should:
        1. Navigate to the appropriate page (if requires_navigation)
        2. Wait for content to load
        3. Parse and extract the relevant data
        4. Return structured data

        Args:
            page: Playwright Page object (already logged in)
            base_url: Base URL of Club Virtual

        Returns:
            Dictionary containing the extracted data
        """

    async def validate_page(self, page: "Page") -> bool:
        """
        Validate that we're on the correct page for extraction.

        Override this method to add custom validation logic.

        Args:
            page: Playwright Page object

        Returns:
            True if page is valid for extraction
        """
        # Default implementation: check page is loaded
        _ = page  # Mark as used
        return True

    def __repr__(self) -> str:
        """Return string representation."""
        return f"{self.__class__.__name__}(name='{self.name}')"
