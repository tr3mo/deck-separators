"""Deck Separators: horizontal lines between decks on the Decks screen.

Click a deck's gear icon ▸ Separator, then tick "Above this deck" or
"Below this deck". "Below" sits after the deck *and* its visible subdecks, so
the line stays where you put it when you expand or collapse a deck. A separator
can carry an optional label (gear ▸ Separator ▸ Label above…/below…).

Gear ▸ Separator ▸ Design… (or Tools ▸ Add-ons ▸ Deck Separators ▸ Config)
changes the look of all separators, with a live preview.

Where separators are is stored in the collection config (key "deckSeparators"),
so they follow the deck when it is renamed or moved, are kept per profile and
sync with AnkiWeb. The design is stored in the add-on config. A separator under
a collapsed parent is hidden with that parent.
"""

from __future__ import annotations

from typing import Any

from aqt import gui_hooks, mw
from aqt.deckbrowser import DeckBrowser
from aqt.qt import QMenu, qconnect
from aqt.utils import getText

from .design import Design
from .dialog import open_dialog, separator_row

ADDON = __name__
CONFIG_KEY = "deckSeparators"
ABOVE = "above"
BELOW = "below"
# Anki's deck table: deck name (colspan 5) + New + Learn + Due + gear column.
COLUMNS = 9

Separators = dict[str, dict[str, str]]


# where separators are (collection config)


def _load() -> Separators:
    """{deck id as str: {"above"/"below": label}}; a missing key means no line."""
    if mw.col is None:
        return {}
    raw: Any = mw.col.get_config(CONFIG_KEY, {})
    if not isinstance(raw, dict):
        return {}
    data: Separators = {}
    for did, seps in raw.items():
        if isinstance(seps, dict):
            data[str(did)] = {
                pos: str(seps[pos] or "") for pos in (ABOVE, BELOW) if pos in seps
            }
    return data


def _refresh_deck_browser() -> None:
    # Only redraw when the Decks screen is showing; it re-renders when shown anyway.
    if mw.state == "deckBrowser":
        mw.deckBrowser.refresh()


def _save(data: Separators) -> None:
    mw.col.set_config(CONFIG_KEY, {did: seps for did, seps in data.items() if seps})
    _refresh_deck_browser()


# how separators look (add-on config)


def _design() -> Design:
    return Design.from_config(mw.addonManager.getConfig(ADDON))


def _save_design(design: Design) -> None:
    mw.addonManager.writeConfig(ADDON, design.to_config())
    _refresh_deck_browser()


def _preview_design(design: Design) -> None:
    if mw.state == "deckBrowser":
        mw.deckBrowser.web.eval(design.update_style_js())


def _open_design() -> None:
    open_dialog(mw, _design(), COLUMNS, _save_design, _preview_design)


# rendering

# _render_deck_node returns the HTML for one deck row followed by its visible
# subdecks, so wrapping it places "below" after the whole subtree.
_original_render_deck_node = DeckBrowser._render_deck_node


def _render_deck_node(self: DeckBrowser, node: Any, ctx: Any) -> str:
    buf = _original_render_deck_node(self, node, ctx)
    try:
        seps = _load().get(str(node.deck_id))
        if seps:
            if ABOVE in seps:
                buf = separator_row(seps[ABOVE], COLUMNS) + buf
            if BELOW in seps:
                buf += separator_row(seps[BELOW], COLUMNS)
    except Exception as exc:  # never break the Decks screen over a separator
        print(f"Deck Separators: {exc!r}")
    return buf


DeckBrowser._render_deck_node = _render_deck_node  # type: ignore[method-assign]


def _on_webview_will_set_content(web_content: Any, context: object | None) -> None:
    if isinstance(context, DeckBrowser):
        web_content.head += _design().style_tag()


# gear menu


def _toggle(deck_id: int, pos: str, on: bool) -> None:
    data = _load()
    seps = data.setdefault(str(deck_id), {})
    if on:
        seps.setdefault(pos, "")
    else:
        seps.pop(pos, None)
    _save(data)


def _edit_label(deck_id: int, pos: str) -> None:
    data = _load()
    seps = data.get(str(deck_id), {})
    if pos not in seps:
        return
    where = "above" if pos == ABOVE else "below"
    text, ok = getText(
        f"Label for the separator {where} this deck (leave empty for a plain line):",
        parent=mw,
        default=seps[pos],
        title="Deck Separators",
    )
    if not ok:
        return
    seps[pos] = text.strip()
    _save(data)


def _on_options_menu(menu: QMenu, deck_id: int) -> None:
    seps = _load().get(str(deck_id), {})
    sub = menu.addMenu("Separator")
    for pos, text in ((ABOVE, "Above this deck"), (BELOW, "Below this deck")):
        action = sub.addAction(text)
        action.setCheckable(True)
        action.setChecked(pos in seps)
        qconnect(
            action.triggered,
            lambda checked, pos=pos: _toggle(deck_id, pos, bool(checked)),
        )
    sub.addSeparator()
    for pos, text in ((ABOVE, "Label above…"), (BELOW, "Label below…")):
        action = sub.addAction(text)
        action.setEnabled(pos in seps)
        qconnect(action.triggered, lambda _checked=False, pos=pos: _edit_label(deck_id, pos))
    sub.addSeparator()
    qconnect(sub.addAction("Design…").triggered, lambda _checked=False: _open_design())


gui_hooks.deck_browser_will_show_options_menu.append(_on_options_menu)
gui_hooks.webview_will_set_content.append(_on_webview_will_set_content)
mw.addonManager.setConfigAction(ADDON, _open_design)
