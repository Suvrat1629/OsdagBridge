from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import QLineEdit

MIN_EDITOR_WIDTH = 80


class _LabelEditor(QLineEdit):
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.setProperty("cancelled", True)
            self.clearFocus()
            return
        super().keyPressEvent(event)


class EditableLabelsMixin:
    """Double-click editing of dimension labels drawn with draw_text_with_background.

    A label is editable when drawn with edit_key=<input key>; labels drawn without one
    (derived values) stay read-only. Widgets using the mixin declare
    `label_value_edited = Signal(str, str)`, call _init_label_editing() in __init__,
    _reset_editable_labels() at the start of paintEvent and _sync_label_editor() at its end.
    Editing is off unless label_editing_enabled is set.
    """

    label_editing_enabled = False

    def _init_label_editing(self):
        self._editable_labels = []
        self._editor = None
        self._editor_key = None
        self.label_edit_allowed = lambda key: True
        self.label_value = lambda key: ""

    def _reset_editable_labels(self):
        self._editable_labels = []

    def _register_editable_label(self, rect, key):
        if key and self.label_editing_enabled:
            self._editable_labels.append((rect, key))

    def _label_rect(self, key):
        return next((rect for rect, k in self._editable_labels if k == key), None)

    def mouseDoubleClickEvent(self, event):
        pos = event.position()
        for rect, key in self._editable_labels:
            if rect.contains(pos) and self.label_edit_allowed(key):
                self._open_label_editor(key, rect)
                return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        self._close_label_editor(commit=True)
        super().mousePressEvent(event)

    def _open_label_editor(self, key, rect):
        self._close_label_editor(commit=False)
        editor = _LabelEditor(self.label_value(key), self)
        editor.setValidator(QDoubleValidator(editor))
        editor.setAlignment(Qt.AlignCenter)
        editor.editingFinished.connect(lambda: self._close_label_editor(commit=True))
        self._editor, self._editor_key = editor, key
        self._place_label_editor(rect)
        editor.show()
        editor.selectAll()
        editor.setFocus()

    def _place_label_editor(self, rect):
        width = max(MIN_EDITOR_WIDTH, int(rect.width()))
        self._editor.setGeometry(int(rect.center().x() - width / 2), int(rect.top()), width, max(22, int(rect.height())))

    def _sync_label_editor(self):
        if self._editor is None:
            return
        rect = self._label_rect(self._editor_key)
        if rect is None:
            self._close_label_editor(commit=False)
        else:
            self._place_label_editor(rect)

    def _close_label_editor(self, commit):
        editor, key = self._editor, self._editor_key
        if editor is None:
            return
        self._editor = self._editor_key = None
        text = editor.text().strip()
        cancelled = editor.property("cancelled")
        editor.hide()
        editor.deleteLater()
        if commit and not cancelled and text and text != self.label_value(key):
            self.label_value_edited.emit(key, text)
