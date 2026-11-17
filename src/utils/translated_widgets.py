"""Qt widgets retaining PluginText templates for LanguageChange events.

Only explicitly tagged text is refreshed. Ordinary strings, user input, paths,
SQL, and configuration values are never inferred or translated.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QLabel, QPushButton, QDialog, QLineEdit, QTextBrowser, QGroupBox

from .plugin_i18n import PluginText, translated


class _TranslatedProperties:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if args and isinstance(args[0], PluginText):
            if isinstance(self, QGroupBox):
                self.setTitle(args[0])
            elif isinstance(self, (QLabel, QPushButton)):
                self.setText(args[0])

    def _set_translation(self, method, text):
        bindings = self.__dict__.setdefault('_translation_bindings', {})
        if isinstance(text, PluginText):
            bindings[method] = text
        else:
            bindings.pop(method, None)
        getattr(super(), method)(translated(text))

    def setText(self, text):
        self._set_translation('setText', text)

    def setWindowTitle(self, text):
        self._set_translation('setWindowTitle', text)

    def setToolTip(self, text):
        self._set_translation('setToolTip', text)

    def setPlaceholderText(self, text):
        self._set_translation('setPlaceholderText', text)

    def setHtml(self, text):
        self._set_translation('setHtml', text)

    def setTitle(self, text):
        self._set_translation('setTitle', text)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.LanguageChange:
            for method, text in tuple(getattr(self, '_translation_bindings', {}).items()):
                getattr(super(), method)(translated(text))


class TranslatedLabel(_TranslatedProperties, QLabel):
    pass


class TranslatedPushButton(_TranslatedProperties, QPushButton):
    pass


class TranslatedDialog(_TranslatedProperties, QDialog):
    pass


class TranslatedLineEdit(_TranslatedProperties, QLineEdit):
    pass


class TranslatedTextBrowser(_TranslatedProperties, QTextBrowser):
    pass


class TranslatedGroupBox(_TranslatedProperties, QGroupBox):
    pass
