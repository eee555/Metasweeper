"""Extract every built-in plugin with Qt, keeping plugin contexts isolated.

Run from any directory. Existing translations are retained by source/comment;
--seed-host is for the one-time move from src/ui to plugin-owned catalogs.
No Python module is imported, so extraction has no plugin side effects.
"""
from __future__ import annotations

import argparse
import ast
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from audit_plugin_translations import CONTEXTS, LOCALES, ROOT
from compile_plugin_translations import qt_tool


def complete(message):
    translation = message.find('translation')
    return (translation is not None and translation.get('type') not in ('unfinished', 'vanished', 'obsolete')
            and bool(''.join(translation.itertext()).strip()))


def messages(tree):
    result = {}
    for message in tree.findall('.//message'):
        key = message.findtext('source', ''), message.findtext('comment', '')
        if key not in result or complete(message):
            result[key] = message
    return result


def write_catalog(root: ET.Element, path: Path) -> None:
    ET.indent(root, space='    ')
    path.write_text('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>\n'
                    + ET.tostring(root, encoding='unicode') + '\n', encoding='utf-8')


def update(seed_host: bool = False) -> None:
    tool = qt_tool('lupdate')
    for plugin, context in CONTEXTS.items():
        directory = ROOT / 'src/plugins' / plugin
        sources = sorted(directory.rglob('*.py'))
        output = directory / 'translations'
        output.mkdir(exist_ok=True)
        for locale in LOCALES:
            path = output / f'{locale}.ts'
            previous = messages(ET.parse(path)) if path.exists() else {}
            if seed_host:
                host = messages(ET.parse(ROOT / 'src/ui' / f'{locale}.ts'))
                previous = {key: value for key, value in previous.items() if complete(value)}
                previous = {**host, **previous}
            # Qt scans real source files; the bound PluginTranslate context is
            # applied below, exactly as it is by the runtime helper.
            with tempfile.TemporaryDirectory(prefix='plugin-lupdate-') as temp:
                raw = Path(temp) / f'{locale}.ts'
                # Qt's Python parser can miss multiple calls on one line and
                # templates passed through _row_error(). Supplement those with
                # simple, literal calls, still extracted by Qt itself.
                literals = set()
                for source in sources:
                    tree = ast.parse(source.read_text(encoding='utf-8'))
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                            if node.func.id in ('_translate', '_row_error') and len(node.args) >= 2:
                                text = node.args[1]
                                if isinstance(text, ast.Constant) and isinstance(text.value, str):
                                    literals.add(text.value)
                        if isinstance(node, ast.FunctionDef) and node.name == 'validate_column_name':
                            literals.update(ret.value.value for ret in ast.walk(node)
                                            if isinstance(ret, ast.Return) and isinstance(ret.value, ast.Constant)
                                            and isinstance(ret.value.value, str))
                hints = Path(temp) / 'extraction_hints.py'
                hints.write_text('from PySide6.QtCore import QCoreApplication\n'
                                 + '\n'.join('QCoreApplication.translate(' + json.dumps(context) + ', '
                                             + json.dumps(text, ensure_ascii=False) + ')'
                                             for text in sorted(literals)), encoding='utf-8')
                subprocess.run([str(tool), *map(str, sources), str(hints), '-ts', str(raw),
                                '-noobsolete', '-tr-function-alias', 'translate+=_translate'],
                               check=True, capture_output=True)
                extracted = ET.parse(raw).getroot()
                catalog = ET.Element('TS', version='2.1', language=locale,
                                     sourcelanguage='zh_CN')
                group = ET.SubElement(catalog, 'context')
                ET.SubElement(group, 'name').text = context
                unique = {}
                for message in extracted.findall('.//message'):
                    key = message.findtext('source', ''), message.findtext('comment', '')
                    if key[0] not in literals:
                        continue
                    for location in message.findall('location'):
                        filename = location.get('filename')
                        if filename:
                            absolute = (raw.parent / filename).resolve()
                            if absolute == hints:
                                message.remove(location)
                            else:
                                location.set('filename', Path(os.path.relpath(absolute, output)).as_posix())
                    if key in unique:
                        for location in message.findall('location'):
                            unique[key].insert(0, copy.deepcopy(location))
                        continue
                    old = previous.get(key)
                    translation = old.find('translation') if old is not None else None
                    if translation is not None:
                        message.remove(message.find('translation'))
                        message.append(copy.deepcopy(translation))
                    group.append(message)
                    unique[key] = message
                write_catalog(catalog, path)
            print(f'{plugin}/{locale}: {len(unique)} messages')


def update_host() -> None:
    """Use the maintained host source list from src/ui/生成ts文件.bat."""
    directory = ROOT / 'src/ui'
    variables = {}
    for line in (directory / '生成ts文件.bat').read_text(encoding='utf-8').splitlines():
        match = re.match(r'set (\w+)=(.*)', line, re.IGNORECASE)
        if match:
            value = re.sub(r'%(\w+)%', lambda found: variables[found[1]], match[2])
            variables[match[1]] = value
    sources = variables['ALL_SOURCES'].split()
    if any('/plugins/' in source for source in sources):
        raise ValueError('Plugin source leaked into host extraction list')
    # ``_tr()`` is deliberately a small one-argument wrapper around
    # QCoreApplication.translate().  lupdate cannot infer its context or
    # recognize the wrapper, so add a generated source file containing the
    # same literal calls.  This keeps the hand-maintained source list useful
    # while ensuring market/download/uninstall messages are never dropped by
    # ``-noobsolete``.
    all_paths = [directory / source for source in sources]
    contexts = {
        "plugin_download.py": "PluginDownloadDialog",
        "plugin_repositories.py": "PluginDownloadDialog",
        "plugin_market_dialog.py": "PluginMarketDialog",
        "plugin_catalog.py": "PluginMarketDialog",
        "plugin_uninstall.py": "PluginManagerWindow",
        "plugin_lib_env.py": "PluginEnvironmentDialog",
        "dependency_scan.py": "PluginManagerWindow",
        "settings_manager.py": "PluginEnvironmentDialog",
        "icons.py": "PluginManagerWindow",
        "restart.py": "PluginManagerWindow",
    }
    literals: dict[str, set[str]] = {}
    for path in all_paths:
        if not path.is_file() or path.suffix != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {child: node for node in ast.walk(tree)
                   for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            context = contexts.get(path.name)
            text = None
            if (isinstance(node.func, ast.Name)
                    and node.func.id in {"_tr", "_translate"} and node.args):
                if (len(node.args) >= 2 and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)):
                    context = node.args[0].value
                    text = node.args[1]
                else:
                    text = node.args[0]
            elif (isinstance(node.func, ast.Attribute) and node.func.attr == "tr"
                  and node.args):
                # self.tr("...") belongs to the enclosing class context.
                parent = node
                while parent in parents and not isinstance(parent, ast.ClassDef):
                    parent = parents[parent]
                context = parent.name if isinstance(parent, ast.ClassDef) else None
                text = node.args[0]
            elif (isinstance(node.func, ast.Attribute) and node.func.attr == "translate"
                  and len(node.args) >= 2 and isinstance(node.args[0], ast.Constant)):
                context = node.args[0].value
                text = node.args[1]
            if context and isinstance(text, ast.Constant) and isinstance(text.value, str):
                literals.setdefault(context, set()).add(text.value)
        # Market states are passed through _tr(STATE_*), so include the
        # constant values as well.
        for node in tree.body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id.startswith("STATE_")
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)):
                literals.setdefault(context, set()).add(node.value.value)
        # Enum labels are passed to self.tr() through a computed lookup, which
        # Qt's extractor cannot follow. Keep those source labels translatable.
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "LABELS":
                for value in ast.walk(node):
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        literals.setdefault("PluginSettingsDialog", set()).add(value.value)

    with tempfile.TemporaryDirectory(prefix="host-lupdate-") as temp:
        hints = Path(temp) / "translation_hints.py"
        lines = ["from PySide6.QtCore import QCoreApplication"]
        for context, texts in sorted(literals.items()):
            lines.extend(
                "QCoreApplication.translate(" + json.dumps(context)
                + ", " + json.dumps(text, ensure_ascii=False) + ")"
                for text in sorted(texts)
            )
        hints.write_text("\n".join(lines), encoding="utf-8")
        for locale in LOCALES:
            target = directory / f'{locale}.ts'
            subprocess.run([
                str(qt_tool('lupdate')), *sources, str(hints), '-ts', f'{locale}.ts',
                '-noobsolete', '-tr-function-alias', 'translate+=_translate',
            ], check=True, cwd=directory)
            # Hint calls are synthetic and must not leave a machine-specific
            # temporary path in the checked-in catalog.
            text = target.read_text(encoding='utf-8')
            text = re.sub(
                r'\s*<location filename="[^"]*translation_hints\.py" line="\d+"\s*/>',
                '', text,
            )
            target.write_text(text, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed-host', action='store_true')
    parser.add_argument('--host', action='store_true', help='Extract host only, using its batch source list')
    args = parser.parse_args()
    if args.host:
        update_host()
    else:
        update(args.seed_host)


if __name__ == '__main__':
    main()
