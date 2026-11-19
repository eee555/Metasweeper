"""Audit built-in plugin catalogs (no imports or plugin startup required)."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ('en_US', 'de_DE', 'ja_JP', 'pl_PL')
CONTEXTS = {
    'challenge_mode': 'ChallengeMode',
    'SaoleiWebsite': 'SaoleiWebsite',
    'skin_manager': 'SkinManagerPlugin',
    'XianNiUpgrade': 'XianNiUpgrade',
}


def main():
    for name, context in CONTEXTS.items():
        catalogs = ROOT / 'src/plugins' / name / 'translations'
        for locale in LOCALES:
            path = catalogs / f'{locale}.ts'
            if not path.exists():
                print(f'{name}/{locale}: missing catalog')
                continue
            tree = ET.parse(path)
            messages = tree.findall('.//message')
            missing = [m.findtext('source') for m in messages
                       if m.find('translation') is None
                       or m.find('translation').get('type') in ('unfinished', 'vanished', 'obsolete')
                       or not ''.join(m.find('translation').itertext()).strip()]
            print(f'{name}/{locale}: {len(messages)} messages, {len(missing)} incomplete')
            for text in missing:
                print(json.dumps(text, ensure_ascii=False))


if __name__ == '__main__':
    main()
