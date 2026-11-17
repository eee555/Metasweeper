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
    for locale in LOCALES:
        subprocess.run([str(qt_tool('lupdate')), *sources, '-ts', f'{locale}.ts',
                        '-noobsolete', '-tr-function-alias', 'translate+=_translate'],
                       check=True, cwd=directory)


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
