"""Pre-save check: finds parameters set to "Custom" whose value box is empty."""
import re

from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QStackedWidget, QTabWidget, QWidget

from osdagbridge.core.bridge_types.plate_girder.ui_fields_additional_input import ADDITIONAL_INPUTS_SCHEMA
from osdagbridge.core.utils.common import (
    SUFFIX_MODE_COMBO,
    SUFFIX_VALUE_INPUT,
    TYPE_COMBOBOX,
    TYPE_MODE_LINE,
    TYPE_TEXTBOX,
    VALUE_CUSTOM,
)


def _iter_groups(node):
    if isinstance(node, dict):
        if isinstance(node.get("rows"), list):
            yield node
        for value in node.values():
            yield from _iter_groups(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _iter_groups(item)


def _group_fields(group):
    for row in group.get("rows", []):
        if isinstance(row, dict):
            yield from row.get("fields", [])


def _build_rules():
    mode_lines, combo_groups = {}, []
    for tab_def in ADDITIONAL_INPUTS_SCHEMA:
        for group in _iter_groups(tab_def["schema"]):
            fields = [f for f in _group_fields(group) if isinstance(f, dict)]
            tab_label = group.get("label", "")
            for f in fields:
                if f.get("type") == TYPE_MODE_LINE and f.get("id"):
                    mode_lines[f["id"]] = (tab_label, f.get("label", ""))
            combo_ids = [
                f["id"] for f in fields
                if f.get("type") == TYPE_COMBOBOX and VALUE_CUSTOM in (f.get("choices") or [])
            ]
            textboxes = {
                f["id"]: (tab_label, f.get("label", "")) for f in fields
                if f.get("type") == TYPE_TEXTBOX and f.get("id")
            }
            if combo_ids and textboxes:
                combo_groups.append((combo_ids, textboxes))
    return mode_lines, combo_groups


_MODE_LINES, _COMBO_GROUPS = _build_rules()


def _clean(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return text.strip().rstrip(":").strip()


def _display_name(dialog, key, labels):
    tab_label, schema_label = labels
    label_widget = dialog.findChild(QLabel, key + "_label")
    name = _clean(label_widget.text() if label_widget is not None else schema_label) or key
    tab = _clean(tab_label)
    return f"{tab} - {name}" if tab else name


def _is_reachable(widget, dialog):
    # Pages of inactive tabs are hidden by Qt, so only disabled tabs count as unreachable.
    if not widget.isEnabled():
        return False
    node = widget
    while node is not None and node is not dialog:
        parent = node.parentWidget()
        if isinstance(parent, QStackedWidget) and isinstance(parent.parentWidget(), QTabWidget):
            tabs = parent.parentWidget()
            index = tabs.indexOf(node)
            if index >= 0 and not tabs.isTabEnabled(index):
                return False
        elif node.isHidden():
            return False
        node = parent
    return True


def find_empty_custom_fields(dialog):
    missing, seen = [], set()

    def report(key, labels):
        if key not in seen:
            seen.add(key)
            missing.append(_display_name(dialog, key, labels))

    for field_id, labels in _MODE_LINES.items():
        mode = dialog.findChild(QComboBox, field_id + SUFFIX_MODE_COMBO)
        value = dialog.findChild(QLineEdit, field_id + SUFFIX_VALUE_INPUT)
        if mode is None or value is None:
            continue
        if mode.currentText() == VALUE_CUSTOM and _is_reachable(value, dialog) and not value.text().strip():
            report(field_id, labels)

    for combo_ids, textboxes in _COMBO_GROUPS:
        custom_selected = False
        for combo_id in combo_ids:
            combo = dialog.findChild(QComboBox, combo_id)
            if combo is not None and combo.currentText() == VALUE_CUSTOM and _is_reachable(combo, dialog):
                custom_selected = True
                break
        if not custom_selected:
            continue
        for box_id, labels in textboxes.items():
            box = dialog.findChild(QLineEdit, box_id)
            if box is None or not _is_reachable(box, dialog):
                continue
            if not box.text().strip():
                report(box_id, labels)

    return missing
