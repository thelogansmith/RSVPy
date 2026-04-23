"""
Theme colors.

Kept separate from the UI modules so every widget pulls from a single
source of truth. Values match the Phase 1 spec's color palette.

Phase 4: accent_color override support. If a custom accent is set in
config, get_theme() can return a theme with that accent substituted.
"""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Theme:
    name: str
    background: str
    text: str
    accent: str
    # Subtle variant of background for the status bar and control strip,
    # so they read as distinct zones without adding borders.
    surface: str
    # Muted text for secondary status-bar content.
    text_muted: str


DARK = Theme(
    name="dark",
    background="#1e1e1e",
    text="#e8e8e8",
    accent="#4a9eff",
    surface="#252525",
    text_muted="#9a9a9a",
)

LIGHT = Theme(
    name="light",
    background="#f5f5f5",
    text="#1a1a1a",
    accent="#2563eb",
    surface="#eaeaea",
    text_muted="#666666",
)


def get_theme(dark_mode: bool, accent_override: str | None = None) -> Theme:
    """Return the appropriate theme, optionally with a custom accent color."""
    base = DARK if dark_mode else LIGHT
    if accent_override:
        return replace(base, accent=accent_override)
    return base