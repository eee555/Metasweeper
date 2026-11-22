import json
import re
import runpy
import sys
from pathlib import Path

linux = Path(__file__).resolve().parent
mini = linux.parent
source = mini.parent / "src"
out = Path(sys.argv[1])

assets = runpy.run_path(str(mini / "win/Build/build_resources.py"))
assets["compile_sprites"](source / "media", out / "classic-shapes.bin")
assets["pack_countries"](source / "country_name.py", out / "countries.deflate")

text = (mini / "win/Configuration/UiText.cs").read_text(encoding="utf-8-sig")
rows = re.findall(r"^\s*\{ (.*?) \}, // (\w+)\s*$", text, re.MULTILINE)
ids = re.search(r"enum TextId\s*\{(.*?)\}", text, re.S).group(1)
assert [name for _, name in rows] == re.findall(r"(\w+)\s*,", ids)
rows.append((json.dumps([
    "文件已存在，再按一次确定覆盖。",
    "This file exists. Confirm again to replace it.",
    "Die Datei existiert. Erneut bestätigen, um sie zu ersetzen.",
    "Plik już istnieje. Potwierdź ponownie, aby go zastąpić.",
    "同名ファイルがあります。もう一度確定すると上書きします。",
], ensure_ascii=False)[1:-1], "OverwriteReplay"))
translations = []
for values, name in rows:
    values = json.loads("[" + values + "]")
    assert len(values) == 5, name
    translations.append("        [" + ", ".join(json.dumps(s, ensure_ascii=False) for s in values) + "],")
(out / "text.rs").write_text(
    "#[allow(dead_code)]\n#[derive(Clone, Copy)]\npub enum Text {\n"
    + "".join(f"    {name},\n" for _, name in rows)
    + "}\npub const STRINGS: &[[&str; 5]] = &[\n"
    + "\n".join(translations)
    + "\n];\n",
    encoding="utf-8",
)

checksum = (mini / "win/Game/ReplayChecksum.cs").read_text(encoding="utf-8-sig")
key_source = re.search(r"byte\[\] Key\s*=\s*\{([^}]+)\}", checksum).group(1)
key = bytes(int(byte, 16) for byte in re.findall(r"0x([0-9a-fA-F]{2})", key_source))
assert len(key) == 32
(out / "replay-key.bin").write_bytes(key)

digits = (mini / "win/UI/ClassicSprites.cs").read_text(encoding="utf-8-sig")
rows = re.findall(r"0x([0-9a-fA-F]+)u", digits)
assert len(rows) == 230
(out / "led.bin").write_bytes(b"".join(int(row, 16).to_bytes(4, "little") for row in rows))
