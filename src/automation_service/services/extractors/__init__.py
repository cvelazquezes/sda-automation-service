"""
Modular data extractors for Club Virtual automation.

This package contains individual extractors that can be composed
together to extract different types of data from Club Virtual.

Available Extractors:
- ProfileExtractor: Extracts user profile information
- TasksExtractor: Extracts active classes and task progress
- SpecialtiesExtractor: Extracts specialties/badges

Usage:
    from automation_service.services.extractors import (
        ProfileExtractor,
        TasksExtractor,
        ExtractorRegistry,
    )

    # Get extractor by name
    extractor = ExtractorRegistry.get("profile")
    data = await extractor.extract(page)
"""

from automation_service.services.extractors.base import BaseExtractor, ExtractorRegistry
from automation_service.services.extractors.profile import ProfileExtractor
from automation_service.services.extractors.tasks import TasksExtractor

__all__ = [
    "BaseExtractor",
    "ExtractorRegistry",
    "ProfileExtractor",
    "TasksExtractor",
]
