"""Design dialog: edit the separator look with a live preview.

Changes show instantly in the dialog's preview and on the Decks screen behind
it. Save keeps them; Cancel or closing the window puts the old look back.
"""

from __future__ import annotations

import html
from collections.abc import Callable
from dataclasses import replace

from aqt.main import AnkiQt
from aqt.qt import (
    QCheckBox,
    QColor,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    Qt,
    QVBoxLayout,
    QWidget,
    qconnect,
)
from aqt.utils import disable_help_button, restoreGeom, saveGeom
from aqt.webview import AnkiWebView

from .design import LABEL_POSITIONS, LABEL_STYLES, LINE_STYLES, RANGES, Design


def separator_row(label: str, columns: int) -> str:
    """One separator row for Anki's deck table. The look comes entirely from CSS."""
    if label:
        return (
            f"<tr class='deck-separator ds-row-labelled'><td colspan={columns}>"
            "<div class='ds-line ds-labelled'>"
            f"<span class='ds-label'>{html.escape(label)}</span></div></td></tr>"
        )
    return (
        f"<tr class='deck-separator ds-row-plain'><td colspan={columns}>"
        "<div class='ds-line ds-plain'></div></td></tr>"
    )


def _preview_deck(name: str, level: int, new: int, learn: int, due: int) -> str:
    def count(n: int, klass: str) -> str:
        return f"<span class='{klass if n else 'zero-count'}'>{n}</span>"

    indent = "&nbsp;" * 6 * (level - 1)
    return (
        "<tr class='deck'>"
        f"<td class=decktd colspan=5>{indent}<span class=collapse></span>"
        f"<a class=deck>{html.escape(name)}</a></td>"
        f"<td align=end>{count(new, 'new-count')}</td>"
        f"<td align=end>{count(learn, 'learn-count')}</td>"
        f"<td align=end>{count(due, 'review-count')}</td>"
        "<td class=opts></td></tr>"
    )


def _preview_body(design: Design, columns: int) -> str:
    rows = "".join(
        [
            _preview_deck("French", 1, 20, 0, 41),
            separator_row("Science", columns),
            _preview_deck("Biology", 1, 0, 3, 120),
            _preview_deck("Cells", 2, 0, 0, 12),
            _preview_deck("Genetics", 2, 0, 3, 108),
            separator_row("", columns),
            _preview_deck("Chemistry", 1, 15, 0, 0),
        ]
    )
    return (
        f"{design.style_tag()}<center><table cellspacing=0 cellpadding=3>{rows}</table></center>"
    )


class DesignDialog(QDialog):
    GEOMETRY_KEY = "deckSeparatorsDesign"

    def __init__(
        self,
        mw: AnkiQt,
        saved: Design,
        columns: int,
        on_save: Callable[[Design], None],
        on_live_change: Callable[[Design], None],
    ) -> None:
        super().__init__(mw)
        self._saved = saved
        self._on_save = on_save
        self._on_live_change = on_live_change
        self._color = saved.color
        self._loading = True  # no previews until every widget exists
        self._saving = False

        self.setWindowTitle("Deck Separators: Design")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        disable_help_button(self)

        self.line_style = self._combo(LINE_STYLES)
        self.thickness = self._spin("line_thickness_px")
        self.custom_color = QCheckBox("Custom")
        self.color_button = QPushButton()
        self.color_button.setFixedWidth(64)
        qconnect(self.custom_color.toggled, self._changed)
        qconnect(self.color_button.clicked, self._pick_color)
        color_row = QWidget()
        color_layout = QHBoxLayout(color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.addWidget(self.custom_color)
        color_layout.addWidget(self.color_button)
        color_layout.addStretch()

        self.label_position = self._combo(LABEL_POSITIONS)
        self.label_style = self._combo(LABEL_STYLES)
        self.label_size = self._spin("label_size_px")
        self.padding_top = self._spin("padding_top_px")
        self.padding_bottom = self._spin("padding_bottom_px")

        form = QFormLayout()
        form.addRow(self._heading("Line"))
        form.addRow("Style", self.line_style)
        form.addRow("Thickness", self.thickness)
        form.addRow("Color", color_row)
        form.addRow(self._heading("Label"))
        form.addRow("Position", self.label_position)
        form.addRow("Style", self.label_style)
        form.addRow("Size", self.label_size)
        form.addRow(self._heading("Spacing"))
        form.addRow("Above", self.padding_top)
        form.addRow("Below", self.padding_bottom)

        self.web = AnkiWebView(self, title="deck separators preview")
        self.web.setMinimumSize(380, 260)

        controls = QWidget()
        controls.setLayout(form)
        body = QHBoxLayout()
        body.addWidget(controls)
        body.addWidget(self.web, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.RestoreDefaults
        )
        qconnect(buttons.accepted, self.accept)
        qconnect(buttons.rejected, self.reject)
        restore = buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults)
        qconnect(restore.clicked, lambda: self._show(Design()))

        layout = QVBoxLayout(self)
        layout.addLayout(body, 1)
        layout.addWidget(buttons)

        self.web.stdHtml(
            _preview_body(saved, columns), css=["css/deckbrowser.css"], context=self
        )
        self._show(saved)
        restoreGeom(self, self.GEOMETRY_KEY, default_size=(760, 420))

    # widgets

    def _heading(self, text: str) -> QLabel:
        label = QLabel(f"<b>{text}</b>")
        label.setContentsMargins(0, 8, 0, 0)
        return label

    def _combo(self, choices: dict[str, str]) -> QComboBox:
        combo = QComboBox()
        for key, text in choices.items():
            combo.addItem(text, key)
        qconnect(combo.currentIndexChanged, self._changed)
        return combo

    def _spin(self, key: str) -> QSpinBox:
        low, high = RANGES[key]
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setSuffix(" px")
        qconnect(spin.valueChanged, self._changed)
        return spin

    def _show(self, design: Design) -> None:
        """Put a design into the widgets, then refresh the previews once."""
        self._loading = True
        for combo, value in (
            (self.line_style, design.line_style),
            (self.label_position, design.label_position),
            (self.label_style, design.label_style),
        ):
            combo.setCurrentIndex(combo.findData(value))
        self.thickness.setValue(design.line_thickness_px)
        self.label_size.setValue(design.label_size_px)
        self.padding_top.setValue(design.padding_top_px)
        self.padding_bottom.setValue(design.padding_bottom_px)
        self._color = design.color
        self.custom_color.setChecked(bool(design.color))
        self._loading = False
        self._changed()

    def design(self) -> Design:
        return Design.from_config(
            {
                "line_style": self.line_style.currentData(),
                "line_thickness_px": self.thickness.value(),
                "color": self._color if self.custom_color.isChecked() else "",
                "label_position": self.label_position.currentData(),
                "label_style": self.label_style.currentData(),
                "label_size_px": self.label_size.value(),
                "padding_top_px": self.padding_top.value(),
                "padding_bottom_px": self.padding_bottom.value(),
            }
        )

    def _pick_color(self) -> None:
        start = QColor(self._color or "#8a8a8a")
        color = QColorDialog.getColor(start, self, "Separator color")
        if color.isValid():
            self._color = color.name()
            self.custom_color.setChecked(True)
            self._changed()

    def _changed(self, *_args: object) -> None:
        if self._loading:
            return
        if self.custom_color.isChecked() and not self._color:
            self._color = "#8a8a8a"
        self.color_button.setEnabled(self.custom_color.isChecked())
        swatch = self._color if self.custom_color.isChecked() else "transparent"
        self.color_button.setStyleSheet(
            f"background: {swatch}; border: 1px solid palette(mid); border-radius: 4px;"
            "min-height: 18px;"
        )
        design = self.design()
        self.web.eval(design.update_style_js())
        self._on_live_change(design)

    # closing

    def accept(self) -> None:
        self._saving = True
        self._on_save(self.design())
        super().accept()

    def done(self, result: int) -> None:
        if not self._saving:
            self._on_live_change(self._saved)  # undo the live preview
        saveGeom(self, self.GEOMETRY_KEY)
        self.web.cleanup()
        super().done(result)


def open_dialog(
    mw: AnkiQt,
    saved: Design,
    columns: int,
    on_save: Callable[[Design], None],
    on_live_change: Callable[[Design], None],
) -> None:
    global _dialog
    if _dialog is not None:
        _dialog.raise_()
        _dialog.activateWindow()
        return
    _dialog = DesignDialog(mw, replace(saved), columns, on_save, on_live_change)
    qconnect(_dialog.finished, _forget_dialog)
    _dialog.show()


def _forget_dialog(*_args: object) -> None:
    global _dialog
    _dialog = None


_dialog: DesignDialog | None = None
