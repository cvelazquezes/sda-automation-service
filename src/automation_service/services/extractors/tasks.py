"""
Tasks and reports data extractor for Club Virtual.

This module extracts active class information from the /miembro/cursos-activos page,
including class names, completion percentages, and investiture status.

Page Structure:
--------------
The page displays a list of active classes, each showing:
- Class name (e.g., "Abejas", "Amigo")
- Progress percentage
- Progress bar
- Status message (e.g., "Autorizado para investir")
- Class badge/image

Aventureros Classes (ages 6-9):
- Abejas (Bees) - Age 6
- Rayitos de Sol (Sunbeams) - Age 7
- Constructores (Builders) - Age 8
- Manos Ayudadoras (Helping Hands) - Age 9

Conquistadores Classes (ages 10-15):
- Amigo (Friend) - Age 10
- Compañero (Companion) - Age 11
- Explorador (Explorer) - Age 12
- Orientador (Ranger) - Age 13
- Viajero (Voyager) - Age 14
- Guía (Guide) - Age 15
"""

from typing import TYPE_CHECKING, Any

import structlog

from automation_service.services.extractors.base import BaseExtractor, ExtractorRegistry

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = structlog.get_logger()


@ExtractorRegistry.register
class TasksExtractor(BaseExtractor):
    """
    Extracts active classes and task progress from Club Virtual.

    Navigates to /miembro/cursos-activos and extracts information about
    the user's active classes and their completion status.
    """

    name = "tasks"
    description = "Extracts active classes and task completion progress"
    requires_navigation = True

    async def extract(self, page: "Page", base_url: str) -> dict[str, Any]:
        """
        Extract active classes from the tasks and reports page.

        Args:
            page: Playwright Page (logged in)
            base_url: Base URL of Club Virtual

        Returns:
            Dictionary with:
            - active_classes: List of class dictionaries
            - total_classes: Number of active classes
            - overall_completion: Average completion percentage
        """
        try:
            # Navigate to tasks and reports page
            tasks_url = f"{base_url}/miembro/cursos-activos"
            await page.goto(tasks_url, wait_until="networkidle")

            # Wait for content to load
            await page.wait_for_selector("h2, h3", timeout=10000)

            # Extract active classes
            active_classes = await self._extract_active_classes(page)

            # Calculate overall completion
            overall_completion = None
            if active_classes:
                total = sum(c.get("completion_percentage", 0) for c in active_classes)
                overall_completion = total / len(active_classes)

            # Count classes ready for investiture
            ready_count = sum(1 for c in active_classes if c.get("is_ready_for_investiture", False))

            logger.debug(
                "TasksExtractor: extracted classes",
                count=len(active_classes),
                ready_for_investiture=ready_count,
            )

            return {
                "active_classes": active_classes,
                "total_classes": len(active_classes),
                "overall_completion": overall_completion,
                "ready_for_investiture_count": ready_count,
            }

        except Exception as e:
            logger.warning("TasksExtractor: extraction failed", error=str(e))
            return {
                "active_classes": [],
                "total_classes": 0,
                "overall_completion": None,
                "error": str(e),
            }

    async def _extract_active_classes(self, page: "Page") -> list[dict[str, Any]]:
        """Extract active class information using JavaScript."""
        result = await page.evaluate(
            """() => {
                const classes = [];

                // Look for class headings (h3 elements typically contain class names)
                const headings = document.querySelectorAll('h3');

                for (const heading of headings) {
                    const name = heading.textContent?.trim();

                    // Skip non-class headings
                    if (!name || name.includes('Cambiar') || name.includes('Investidura')) {
                        continue;
                    }

                    // Find the parent container
                    const container = heading.closest('div, section, article');
                    if (!container) continue;

                    const classInfo = {
                        name: name,
                        completion_percentage: 0,
                        status: null,
                        is_ready_for_investiture: false,
                        image_url: null
                    };

                    // Look for completion percentage text
                    const containerText = container.textContent || '';
                    const percentMatch = containerText.match(/(\\d+)\\s*%/);
                    if (percentMatch) {
                        classInfo.completion_percentage = parseInt(percentMatch[1], 10);
                    }

                    // Check for investiture status
                    if (containerText.includes('autorizado') ||
                        containerText.includes('Autorizado') ||
                        containerText.includes('investir')) {
                        classInfo.is_ready_for_investiture = true;
                        classInfo.status = 'Autorizado para investir';
                    } else if (classInfo.completion_percentage >= 100) {
                        classInfo.status = 'Completado';
                    } else if (classInfo.completion_percentage > 0) {
                        classInfo.status = 'En progreso';
                    } else {
                        classInfo.status = 'Sin iniciar';
                    }

                    // Look for image
                    const img = container.querySelector('img');
                    if (img) {
                        classInfo.image_url = img.src;
                    }

                    classes.push(classInfo);
                }

                return classes;
            }"""
        )

        return list(result) if result else []
