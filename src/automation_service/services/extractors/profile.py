"""
Profile data extractor for Club Virtual.

This module extracts user profile information from the /mi-perfil page,
including basic information, contact details, and social media links.

Profile Page Structure:
----------------------
1. Información Básica:
   - Número de cuenta (account number)
   - Usuario (username)
   - Nombre completo (full name)
   - Género (gender)
   - Cumpleaños (birthday with age)

2. Información de Contacto:
   - Mi Presentación (bio)
   - Teléfono (phone)
   - Dirección (address)
   - Correo electrónico (email)
   - Twitter, Facebook, Instagram
"""

import contextlib
from typing import TYPE_CHECKING, Any

import structlog

from automation_service.services.extractors.base import BaseExtractor, ExtractorRegistry

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = structlog.get_logger()


@ExtractorRegistry.register
class ProfileExtractor(BaseExtractor):
    """
    Extracts user profile information from Club Virtual.

    Navigates to /mi-perfil and extracts all available user information
    including basic info, contact details, and social media links.
    """

    name = "profile"
    description = "Extracts user profile information (name, email, birthday, etc.)"
    requires_navigation = True

    async def extract(self, page: "Page", base_url: str) -> dict[str, Any]:
        """
        Extract user profile from the profile page.

        Args:
            page: Playwright Page (logged in)
            base_url: Base URL of Club Virtual

        Returns:
            Dictionary with profile fields:
            - account_number, username, full_name, gender, birthday, age
            - email, phone, address, bio
            - twitter, facebook, instagram
            - avatar_url
        """
        try:
            # Wait for current page to stabilize
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(1000)

            # Navigate to profile page
            profile_url = f"{base_url}/mi-perfil"
            try:
                await page.goto(profile_url, wait_until="networkidle", timeout=15000)
            except Exception:
                # If networkidle times out, try with just domcontentloaded
                await page.goto(profile_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)

            # Wait for profile content to load
            await page.wait_for_selector("h2", timeout=10000)

            # Extract profile data
            profile_data = await self._parse_profile_page(page)

            logger.debug("ProfileExtractor: extracted data", data=profile_data)
            return profile_data

        except Exception as e:
            logger.warning("ProfileExtractor: extraction failed", error=str(e))
            # Try basic extraction as fallback
            return await self._extract_basic_profile(page)

    async def _parse_profile_page(self, page: "Page") -> dict[str, Any]:
        """Parse the profile page and extract all user information."""
        profile_data: dict[str, Any] = {"username": "unknown"}

        # Get full name from h2 heading
        full_name = await self._get_text_content(page, "h2")
        if full_name:
            profile_data["full_name"] = full_name.strip()

        # Get avatar URL if available
        avatar = await page.query_selector("img.profile-image, img.avatar, .profile-photo img")
        if avatar:
            profile_data["avatar_url"] = await avatar.get_attribute("src")

        # Extract detailed fields
        profile_data.update(await self._extract_profile_fields(page))

        return profile_data

    async def _extract_profile_fields(self, page: "Page") -> dict[str, Any]:
        """Extract all profile fields using JavaScript."""
        result = await page.evaluate(
            """() => {
                const fields = {};
                const placeholder = 'Haz click en el icono';
                const ignorePhrases = ['Estos datos', 'Para cambiar', 'Guardar', 'Cancelar'];

                const fieldMappings = {
                    'Número de cuenta': 'account_number',
                    'Usuario': 'username',
                    'Nombre completo': 'full_name',
                    'Género': 'gender',
                    'Cumpleaños': 'birthday',
                    'Correo electrónico': 'email',
                    'Teléfono': 'phone',
                    'Dirección': 'address',
                    'Mi Presentación': 'bio',
                    'Twitter': 'twitter',
                    'Facebook': 'facebook',
                    'Instagram': 'instagram'
                };

                const shouldIgnore = (value) => {
                    if (!value || value.length === 0) return true;
                    if (value.includes(placeholder)) return true;
                    for (const phrase of ignorePhrases) {
                        if (value.includes(phrase)) return true;
                    }
                    for (const label of Object.keys(fieldMappings)) {
                        if (value.includes(label)) return true;
                    }
                    return false;
                };

                // Strategy 1: Table rows
                const tableRows = document.querySelectorAll('tr');
                for (const row of tableRows) {
                    const cells = row.querySelectorAll('td, th');
                    if (cells.length >= 2) {
                        const label = cells[0].textContent?.trim();
                        const value = cells[1].textContent?.trim();
                        if (label && fieldMappings[label] && value && !shouldIgnore(value)) {
                            fields[fieldMappings[label]] = value;
                        }
                    }
                }

                // Strategy 2: List items with strong labels
                const listItems = document.querySelectorAll('li');
                for (const li of listItems) {
                    const strong = li.querySelector('strong, b, .font-bold, .font-weight-bold');
                    if (strong) {
                        const label = strong.textContent?.trim();
                        if (label && fieldMappings[label] && !fields[fieldMappings[label]]) {
                            const fullText = li.textContent || '';
                            const labelIndex = fullText.indexOf(label);
                            if (labelIndex >= 0) {
                                let value = fullText.substring(labelIndex + label.length).trim();
                                value = value.replace(/^[:\\s]+/, '').trim();
                                if (!shouldIgnore(value)) {
                                    fields[fieldMappings[label]] = value;
                                }
                            }
                        }
                    }
                }

                // Strategy 3: Definition lists
                const dlItems = document.querySelectorAll('dl');
                for (const dl of dlItems) {
                    const dts = dl.querySelectorAll('dt');
                    const dds = dl.querySelectorAll('dd');
                    for (let i = 0; i < dts.length && i < dds.length; i++) {
                        const label = dts[i].textContent?.trim();
                        const value = dds[i].textContent?.trim();
                        if (label && fieldMappings[label] && value && !shouldIgnore(value)) {
                            fields[fieldMappings[label]] = value;
                        }
                    }
                }

                // Strategy 4: Spans/divs with adjacent labels
                const spans = document.querySelectorAll('span, div.col, div.value, p.value');
                for (const span of spans) {
                    const text = span.textContent?.trim();
                    if (text) {
                        const parent = span.parentElement;
                        if (parent) {
                            const prevSibling = span.previousElementSibling;
                            if (prevSibling) {
                                const label = prevSibling.textContent?.trim();
                                if (label && fieldMappings[label] && !fields[fieldMappings[label]]) {
                                    if (!shouldIgnore(text)) {
                                        fields[fieldMappings[label]] = text;
                                    }
                                }
                            }
                        }
                    }
                }

                return fields;
            }"""
        )

        fields = result if result else {}

        # Post-process birthday to extract age
        if "birthday" in fields and " - " in str(fields.get("birthday", "")):
            birthday_str = str(fields["birthday"])
            parts = birthday_str.split(" - ")
            fields["birthday"] = parts[0].strip()
            if len(parts) > 1:
                age_str = parts[1].replace("años", "").strip()
                with contextlib.suppress(ValueError):
                    fields["age"] = float(age_str)

        return dict(fields)

    async def _get_text_content(self, page: "Page", selector: str) -> str | None:
        """Get text content from the first matching element."""
        try:
            element = await page.query_selector(selector)
            if element:
                text = await element.text_content()
                return str(text) if text else None
        except Exception:
            pass
        return None

    async def _extract_basic_profile(self, page: "Page") -> dict[str, Any]:
        """Fallback: extract basic profile info from any page."""
        try:
            username = "unknown"
            session_element = await page.query_selector(':text("Iniciaste sesión como")')
            if session_element:
                parent = await session_element.evaluate_handle("el => el.parentElement")
                text = await parent.evaluate("el => el.textContent")
                if text and "Iniciaste sesión como" in text:
                    username = text.split("Iniciaste sesión como")[-1].strip().split()[0]

            full_name = None
            name_element = await page.query_selector("h2")
            if name_element:
                full_name = await name_element.text_content()
                if full_name:
                    full_name = full_name.strip()

            return {"username": username, "full_name": full_name}

        except Exception as e:
            logger.warning("Basic profile extraction failed", error=str(e))
            return {"username": "unknown"}
