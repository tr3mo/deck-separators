"""The separator design: settings, validation and the CSS they produce.

Kept free of Anki imports so it can be tested on its own. Every value is
validated before it reaches the CSS, so a hand-edited config can never break
the Decks screen or inject styles.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from typing import Any

STYLE_ID = "deck-separators-style"

LINE_STYLES = {
    "solid": "Solid",
    "fade": "Fade",
    "dashed": "Dashed",
    "dotted": "Dotted",
    "double": "Double",
}
LABEL_POSITIONS = {"left": "Left", "center": "Center", "right": "Right"}
LABEL_STYLES = {"caps": "Small caps", "plain": "Plain", "pill": "Pill"}

# (min, max) for each pixel setting.
RANGES = {
    "line_thickness_px": (1, 8),
    "label_size_px": (8, 32),
    "padding_top_px": (0, 100),
    "padding_bottom_px": (0, 100),
}
CHOICES = {
    "line_style": LINE_STYLES,
    "label_position": LABEL_POSITIONS,
    "label_style": LABEL_STYLES,
}
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")


@dataclass
class Design:
    line_style: str = "solid"
    line_thickness_px: int = 1
    color: str = ""  # "" follows Anki's light/dark theme, otherwise "#rrggbb"
    label_position: str = "left"
    label_style: str = "caps"
    label_size_px: int = 11
    padding_top_px: int = 8
    padding_bottom_px: int = 8

    @classmethod
    def from_config(cls, config: Any) -> Design:
        """Build a design from the add-on config, replacing invalid values with defaults."""
        design = cls()
        if not isinstance(config, dict):
            return design
        for key, choices in CHOICES.items():
            if config.get(key) in choices:
                setattr(design, key, config[key])
        for key, (low, high) in RANGES.items():
            value = config.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and not math.isnan(value):
                setattr(design, key, int(round(min(max(value, low), high))))
        color = config.get("color")
        if isinstance(color, str) and _HEX_COLOR.fullmatch(color):
            design.color = color.lower()
        return design

    def to_config(self) -> dict[str, Any]:
        return asdict(self)

    def css(self) -> str:
        line = self.color or "var(--fg-faint)"
        text = self.color or "var(--fg-subtle)"
        thick = self.line_thickness_px
        css = f"""
tr.deck-separator td,
tr.deck-separator:hover td {{
    background: transparent !important;
    border: none !important;
    /* No side padding: the line spans the full row, like Anki's row border. */
    padding: {self.padding_top_px}px 0 {self.padding_bottom_px}px 0 !important;
    cursor: default;
}}
/* The separator takes the place of the row border right above it. */
tr.deck:has(+ tr.deck-separator) td {{
    border-bottom-color: transparent !important;
}}
/* Two separators next to each other show as one; a labelled one wins. */
tr.deck-separator + tr.ds-row-plain,
tr.ds-row-plain:has(+ tr.ds-row-labelled) {{
    display: none;
}}
.ds-line {{
    --ds-line: {line};
    --ds-text: {text};
    display: flex;
    align-items: center;
    gap: 0.75em;
}}
.ds-line::before,
.ds-line::after {{
    content: "";
    flex: 1 1 0;
    min-width: 1.5em;
}}
.ds-plain::before{_HIDE_FOR_POSITION[self.label_position]} {{
    display: none;
}}
.ds-label {{
    color: var(--ds-text);
    font-size: {self.label_size_px}px;
    line-height: 1.4;
    white-space: nowrap;{_LABEL_INSET[self.label_position]}
}}
"""
        css += _LINE_CSS[self.line_style](thick)
        css += _LABEL_CSS[self.label_style]
        return css

    def style_tag(self) -> str:
        return f'<style id="{STYLE_ID}">{self.css()}</style>'

    def update_style_js(self) -> str:
        """JS that swaps the CSS on an already rendered page (live preview)."""
        return (
            f"(() => {{ const el = document.getElementById({json.dumps(STYLE_ID)}); "
            f"if (el) el.textContent = {json.dumps(self.css())}; }})();"
        )


def _border_line(style: str) -> Any:
    def css(thick: int) -> str:
        width = max(3, 3 * thick) if style == "double" else thick
        return f"""
.ds-line::before,
.ds-line::after {{
    border-top: {width}px {style} var(--ds-line);
}}
"""

    return css


def _fade_line(thick: int) -> str:
    # Each line fades out away from the label; a line without a label fades at both ends.
    return f"""
.ds-line::before,
.ds-line::after {{
    height: {thick}px;
    border-radius: {thick}px;
}}
.ds-line::before {{
    background: linear-gradient(to right, transparent, var(--ds-line));
}}
.ds-line::after {{
    background: linear-gradient(to right, var(--ds-line), transparent);
}}
[dir=rtl] .ds-line::before {{
    background: linear-gradient(to left, transparent, var(--ds-line));
}}
[dir=rtl] .ds-line::after {{
    background: linear-gradient(to left, var(--ds-line), transparent);
}}
.ds-line.ds-plain::after {{
    background: linear-gradient(to right, transparent, var(--ds-line) 15%,
        var(--ds-line) 85%, transparent);
}}
"""


# Which half of a labelled line to hide for each label position.
_HIDE_FOR_POSITION = {
    "left": ",\n.ds-labelled::before",
    "center": "",
    "right": ",\n.ds-labelled::after",
}

# Line a left label up with the top-level deck names (Anki's 12px cell padding plus
# the 1em collapse-button column) and a right label with the count column.
_LABEL_INSET = {
    "left": "\n    margin-inline-start: calc(12px + 1rem);",
    "center": "",
    "right": "\n    margin-inline-end: 12px;",
}

_LINE_CSS = {
    "fade": _fade_line,
    "solid": _border_line("solid"),
    "dashed": _border_line("dashed"),
    "dotted": _border_line("dotted"),
    "double": _border_line("double"),
}

_LABEL_CSS = {
    "plain": """
.ds-label {
    font-weight: 600;
}
""",
    "caps": """
.ds-label {
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
""",
    "pill": """
.ds-label {
    font-weight: 600;
    padding: 0.15em 0.85em;
    border-radius: 999px;
    /* Outline pill where color-mix() is unavailable (Anki 23.10), tinted pill otherwise. */
    background: transparent;
    border: 1px solid var(--ds-line);
    background: color-mix(in srgb, var(--ds-line) 18%, transparent);
    border: 1px solid color-mix(in srgb, var(--ds-line) 45%, transparent);
}
""",
}
