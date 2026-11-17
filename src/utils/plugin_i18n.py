"""Plugin-local Qt contexts and text that can be resolved after module import.

The first argument remains compatible with Qt's translate API and lupdate.
A bound translator always uses its plugin's context, including legacy call sites.
The extraction tool applies the same context to the plugin's catalogs.
"""
from __future__ import annotations

from PySide6.QtCore import QCoreApplication


class PluginText(str):
    """A str accepted by Qt, retaining its source for configuration retranslation."""

    def __new__(cls, context: str, source: str, disambiguation=None, n: int = -1,
                operations: tuple = ()):
        value = QCoreApplication.translate(context, source, disambiguation, n)
        for method, args, kwargs in operations:
            args = tuple(translated(arg) if isinstance(arg, str) else arg for arg in args)
            kwargs = {key: translated(arg) if isinstance(arg, str) else arg for key, arg in kwargs.items()}
            value = getattr(value, method)(*args, **kwargs)
        instance = super().__new__(cls, value)
        instance.context = context
        instance.source = source
        instance.disambiguation = disambiguation
        instance.n = n
        instance.operations = operations
        return instance

    def translated(self) -> str:
        return str(PluginText(self.context, self.source, self.disambiguation,
                              self.n, self.operations))

    def __reduce__(self):
        return (PluginText, (self.context, self.source, self.disambiguation,
                             self.n, self.operations))

    def format(self, *args, **kwargs) -> PluginText:
        return PluginText(self.context, self.source, self.disambiguation, self.n,
                          self.operations + (('format', args, kwargs),))

    def replace(self, old: str, new: str, count: int = -1) -> PluginText:
        return PluginText(self.context, self.source, self.disambiguation, self.n,
                          self.operations + (('replace', (old, new, count), {}),))


class PluginTranslate:
    """Bind every explicit translate call in a plugin to one unique context."""

    def __init__(self, context: str):
        self.context = context

    def __call__(self, context: str, source: str, disambiguation=None,
                 n: int = -1) -> PluginText:
        return PluginText(self.context, source, disambiguation, n)


def translated(value: str) -> str:
    """Resolve configuration text using the translator installed now."""
    return value.translated() if isinstance(value, PluginText) else value
