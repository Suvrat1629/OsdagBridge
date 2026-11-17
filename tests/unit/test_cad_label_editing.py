import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from osdagbridge.core.bridge_types.plate_girder.defaults import BASIC_INPUT_DICT
from osdagbridge.core.bridge_types.plate_girder.ui_fields import FrontendData
from osdagbridge.core.utils.common import (
    KEY_CARRIAGEWAY_WIDTH,
    KEY_SPAN,
    KEY_TS_DECK_THICKNESS,
    KEY_TS_GIRDER_SPACING,
)
from osdagbridge.desktop.ui import template_page
from osdagbridge.desktop.ui.dialogs.additional_input import additional_inputs
from osdagbridge.desktop.ui.docks import input_dock as input_dock_module
from osdagbridge.desktop.ui.docks.cad_cross_section import CrossSectionCADWidget
from osdagbridge.desktop.ui.docks.cad_dual_view import BridgeDualCADWidget
from osdagbridge.desktop.ui.docks.input_dock import InputDock

HOST_METHODS = (
    "_cad_label_edit_allowed",
    "_cad_label_value",
    "_apply_cad_label_edit",
    "_get_additional_inputs",
    "update_cad_from_inputs",
    "update_2d_cad",
)


class StubMessageBox:
    shown = []

    def __init__(self, **kwargs):
        StubMessageBox.shown.append(kwargs)

    def exec(self):
        return "OK"


class Backend:
    def input_values(self):
        return FrontendData().input_values()


class Host(QWidget):
    """The parts of the main window that wire the CAD labels to the inputs."""


for _name in HOST_METHODS:
    setattr(Host, _name, getattr(template_page.CustomWindow, _name))


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def host(app, monkeypatch):
    for module in (template_page, additional_inputs, input_dock_module):
        monkeypatch.setattr(module, "CustomMessageBox", StubMessageBox)
    StubMessageBox.shown = []

    window = Host()
    window.resize(1500, 900)
    window.input_dict = dict(BASIC_INPUT_DICT)
    window._additional_inputs_dialog = None
    window.input_dock = InputDock(backend=Backend(), parent=window)
    window.cad_comp_widget = BridgeDualCADWidget(window)
    QVBoxLayout(window).addWidget(window.cad_comp_widget)
    window.cad_comp_widget.set_label_edit_hooks(window._cad_label_edit_allowed, window._cad_label_value)
    window.cad_comp_widget.label_value_edited.connect(window._apply_cad_label_edit)
    window.input_dock.input_value_changed.connect(window.update_cad_from_inputs)
    window.show()
    for key, value in ((KEY_SPAN, "30"), (KEY_CARRIAGEWAY_WIDTH, "7.5")):
        box = window.input_dock._w(key)
        box.setText(value)
        box.editingFinished.emit()
    app.processEvents()
    yield window
    window.close()


def cross(host):
    return host.cad_comp_widget.cross_section_widget


def top(host):
    return host.cad_comp_widget.top_view_widget


def double_click(app, view, key):
    view.grab()
    QTest.mouseDClick(view, Qt.LeftButton, Qt.NoModifier, view._label_rect(key).center().toPoint())
    app.processEvents()


def submit(app, view, text):
    view._editor.setText(text)
    QTest.keyClick(view._editor, Qt.Key_Return)
    app.processEvents()
    app.processEvents()


def test_only_editable_labels_are_registered(host):
    cross(host).grab()
    top(host).grab()
    assert {k for _, k in cross(host)._editable_labels} == {KEY_CARRIAGEWAY_WIDTH, KEY_TS_GIRDER_SPACING, KEY_TS_DECK_THICKNESS}
    assert {k for _, k in top(host)._editable_labels} == {KEY_SPAN, KEY_TS_GIRDER_SPACING}


def test_double_click_opens_editor_with_current_value(app, host):
    double_click(app, top(host), KEY_SPAN)
    assert top(host)._editor.text() == "30"


def test_double_click_elsewhere_opens_nothing(app, host):
    view = cross(host)
    view.grab()
    QTest.mouseDClick(view, Qt.LeftButton, Qt.NoModifier, QPoint(1, 1))
    assert view._editor is None


def test_valid_span_updates_input_and_drawing(app, host):
    double_click(app, top(host), KEY_SPAN)
    submit(app, top(host), "35")
    assert host.input_dock._w(KEY_SPAN).text() == "35"
    assert host.input_dict[KEY_SPAN] == "35"
    assert top(host).params["span_length"] == 35000


def test_invalid_span_is_rejected_and_old_value_kept(app, host):
    double_click(app, top(host), KEY_SPAN)
    submit(app, top(host), "99")
    assert len(StubMessageBox.shown) == 1
    assert host.input_dock._w(KEY_SPAN).text() == "30"
    assert host.input_dict[KEY_SPAN] == "30"


def test_escape_cancels_the_edit(app, host):
    double_click(app, top(host), KEY_SPAN)
    top(host)._editor.setText("40")
    QTest.keyClick(top(host)._editor, Qt.Key_Escape)
    app.processEvents()
    assert top(host)._editor is None
    assert host.input_dock._w(KEY_SPAN).text() == "30"


def test_carriageway_width_edit_re_solves_the_layout(app, host):
    spacing_before = host.input_dict[KEY_TS_GIRDER_SPACING]
    double_click(app, cross(host), KEY_CARRIAGEWAY_WIDTH)
    submit(app, cross(host), "8")
    assert host.input_dock._w(KEY_CARRIAGEWAY_WIDTH).text() == "8"
    assert cross(host).params["carriageway_width"] == 8000
    assert host.input_dict[KEY_TS_GIRDER_SPACING] != spacing_before


def test_deck_thickness_edit_updates_input_and_drawing(app, host):
    double_click(app, cross(host), KEY_TS_DECK_THICKNESS)
    assert cross(host)._editor.text() == "250"
    submit(app, cross(host), "300")
    assert host.input_dict[KEY_TS_DECK_THICKNESS] == 300
    assert cross(host).params["deck_thickness"] == 300
    assert not host._additional_inputs_dialog.is_modified


def test_girder_spacing_edit_updates_input_and_drawing(app, host):
    double_click(app, cross(host), KEY_TS_GIRDER_SPACING)
    submit(app, cross(host), "2.5")
    assert host.input_dict[KEY_TS_GIRDER_SPACING] == 2.5
    assert cross(host).params["girder_spacing"] == 2500


def test_editing_is_blocked_while_locked(app, host):
    host.input_dock.is_locked = True
    double_click(app, cross(host), KEY_TS_DECK_THICKNESS)
    assert cross(host)._editor is None


def test_preview_in_additional_inputs_is_not_editable(app):
    preview = CrossSectionCADWidget()
    preview.resize(800, 500)
    preview.grab()
    assert preview._editable_labels == []
