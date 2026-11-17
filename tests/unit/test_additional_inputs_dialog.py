import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit

from osdagbridge.core.bridge_types.plate_girder.defaults import BASIC_INPUT_DICT, solve_extend_basic_input_dict
from osdagbridge.core.utils.common import (
    KEY_CARRIAGEWAY_WIDTH,
    KEY_CB_HEIGHT,
    KEY_CB_LOAD,
    KEY_CB_TYPE,
    KEY_CB_WIDTH,
    KEY_MD_HEIGHT,
    KEY_MD_LOAD,
    KEY_MD_TYPE,
    KEY_MD_WIDTH,
    KEY_PROJECT_LOCATION,
    KEY_SKEW_ANGLE,
    KEY_SPAN,
    KEY_TS_DECK_THICKNESS,
    KEY_WC_DENSITY,
    KEY_WC_MATERIAL,
    KEY_WC_THICKNESS,
    KEY_WL_GUST_FACTOR,
    SUFFIX_MODE_COMBO,
    SUFFIX_VALUE_INPUT,
    VALUE_CUSTOM,
)
from osdagbridge.desktop.ui.dialogs.additional_input import additional_inputs as module
from osdagbridge.desktop.ui.dialogs.additional_input.custom_field_validation import find_empty_custom_fields


class StubMessageBox:
    """Records the dialogs the code would show and answers with `answer`."""

    shown = []
    answer = "OK"

    def __init__(self, **kwargs):
        StubMessageBox.shown.append(kwargs)

    def exec(self):
        return StubMessageBox.answer


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialog(app, monkeypatch):
    monkeypatch.setattr(module, "CustomMessageBox", StubMessageBox)
    StubMessageBox.shown = []
    StubMessageBox.answer = "OK"

    inputs = dict(BASIC_INPUT_DICT)
    inputs.update({KEY_SPAN: 30.0, KEY_CARRIAGEWAY_WIDTH: 7.5, KEY_SKEW_ANGLE: 0.0, KEY_PROJECT_LOCATION: "Panjim, Goa"})
    solve_extend_basic_input_dict(inputs)

    dlg = module.AdditionalInputs()
    dlg.set_input_dictionary(inputs)
    dlg.show()
    app.processEvents()
    app.processEvents()
    yield dlg
    dlg.is_modified = False
    dlg.close()


def set_text(app, dlg, key, text):
    dlg.findChild(QLineEdit, key).setText(text)
    app.processEvents()


def set_combo(app, dlg, key, text):
    dlg.findChild(QComboBox, key).setCurrentText(text)
    app.processEvents()


def test_no_custom_selected_reports_nothing(dialog):
    assert find_empty_custom_fields(dialog) == []


def test_empty_custom_wearing_course_is_reported(app, dialog):
    set_combo(app, dialog, KEY_WC_MATERIAL, VALUE_CUSTOM)
    set_text(app, dialog, KEY_WC_DENSITY, "")
    set_text(app, dialog, KEY_WC_THICKNESS, "")
    names = find_empty_custom_fields(dialog)
    assert any("Density" in n for n in names)
    assert any("Thickness" in n for n in names)


def test_save_is_blocked_and_names_the_field(app, dialog):
    set_combo(app, dialog, KEY_WC_MATERIAL, VALUE_CUSTOM)
    set_text(app, dialog, KEY_WC_DENSITY, "")
    set_text(app, dialog, KEY_WC_THICKNESS, "65")
    dialog._save_inputs()
    (box,) = StubMessageBox.shown
    assert box["text"].startswith("Error: The custom value for '")
    assert "Density" in box["text"]
    assert dialog.is_modified


def test_save_succeeds_once_custom_values_are_filled(app, dialog):
    set_combo(app, dialog, KEY_WC_MATERIAL, VALUE_CUSTOM)
    set_text(app, dialog, KEY_WC_DENSITY, "22")
    set_text(app, dialog, KEY_WC_THICKNESS, "65")
    dialog._save_inputs()
    assert [b["title"] for b in StubMessageBox.shown] == ["Saved"]
    assert not dialog.is_modified


def test_crash_barrier_custom_fields_are_reported(app, dialog):
    set_combo(app, dialog, KEY_CB_TYPE, VALUE_CUSTOM)
    for key in (KEY_CB_WIDTH, KEY_CB_HEIGHT, KEY_CB_LOAD):
        set_text(app, dialog, key, "")
    assert len(find_empty_custom_fields(dialog)) == 3


def test_mode_line_custom_value_is_reported(app, dialog):
    set_combo(app, dialog, KEY_WL_GUST_FACTOR + SUFFIX_MODE_COMBO, VALUE_CUSTOM)
    dialog.findChild(QLineEdit, KEY_WL_GUST_FACTOR + SUFFIX_VALUE_INPUT).setText("")
    assert len(find_empty_custom_fields(dialog)) == 1


def test_disabled_tab_is_not_reported(app, dialog):
    set_combo(app, dialog, KEY_MD_TYPE, VALUE_CUSTOM)
    for key in (KEY_MD_WIDTH, KEY_MD_HEIGHT, KEY_MD_LOAD):
        dialog.findChild(QLineEdit, key).setText("")
    dialog.refresh_typical_section()  # no median selected, so the Median tab is disabled
    assert find_empty_custom_fields(dialog) == []


def deck_thickness(dlg):
    return dlg.findChild(QLineEdit, KEY_TS_DECK_THICKNESS)


def test_opening_and_closing_untouched_does_not_warn(dialog):
    assert not dialog.is_modified
    dialog.close()
    assert StubMessageBox.shown == []
    assert not dialog.isVisible()


def test_editing_sets_modified(app, dialog):
    set_text(app, dialog, KEY_TS_DECK_THICKNESS, "300")
    assert dialog.is_modified


def test_close_with_cancel_keeps_dialog_open(app, dialog):
    set_text(app, dialog, KEY_TS_DECK_THICKNESS, "300")
    StubMessageBox.answer = module.BTN_CANCEL
    dialog.close()
    (box,) = StubMessageBox.shown
    assert box["text"] == module.MSG_UNSAVED_CHANGES
    assert box["buttons"] == [module.BTN_DISCARD, module.BTN_CANCEL]
    assert dialog.isVisible()
    assert deck_thickness(dialog).text() == "300"


def test_close_with_discard_restores_saved_value(app, dialog):
    saved = deck_thickness(dialog).text()
    set_text(app, dialog, KEY_TS_DECK_THICKNESS, "300")
    StubMessageBox.answer = module.BTN_DISCARD
    dialog.close()
    assert not dialog.isVisible()
    assert deck_thickness(dialog).text() == saved
    assert not dialog.is_modified


def test_escape_goes_through_the_same_guard(app, dialog):
    set_text(app, dialog, KEY_TS_DECK_THICKNESS, "300")
    StubMessageBox.answer = module.BTN_CANCEL
    dialog.reject()
    assert dialog.isVisible()
    assert len(StubMessageBox.shown) == 1


def test_no_warning_after_save(app, dialog):
    set_text(app, dialog, KEY_TS_DECK_THICKNESS, "310")
    dialog._save_inputs()
    StubMessageBox.shown.clear()
    dialog.close()
    assert StubMessageBox.shown == []
    assert not dialog.isVisible()


def test_discard_re_disables_dependent_fields(app, dialog):
    set_combo(app, dialog, KEY_WC_MATERIAL, VALUE_CUSTOM)
    density = dialog.findChild(QLineEdit, KEY_WC_DENSITY)
    assert density.isEnabled()
    StubMessageBox.answer = module.BTN_DISCARD
    dialog.close()
    assert not density.isEnabled()
