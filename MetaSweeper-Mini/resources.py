import ast
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

CELLS = (
    "celldown", *(f"cell{i}" for i in range(1, 9)), None, "cellup", "cellflag",
    None, None, "falsemine", "blast", "cellmine",
)
FACES = ("smileface", "clickface", "lostface", "winface", "smilefacedown")
TOKEN = re.compile(r"[A-Za-z]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)")
COMMAND_ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "Q": 4, "T": 2, "C": 6, "Z": 0}


def path_operations(data: str):
    tokens = iter(TOKEN.findall(data))
    point = (0.0, 0.0)
    previous_control = None
    for command in tokens:
        args = tuple(float(next(tokens)) for _ in range(COMMAND_ARGS[command]))
        control = None
        if command == "Z":
            yield 0, ()
        elif command == "M":
            point = args
            yield 1, point
        elif command in ("Q", "T"):
            if command == "Q":
                control, end = args[:2], args[2:]
            else:
                start_control = previous_control or point
                control = tuple(2 * a - b for a, b in zip(point, start_control))
                end = args
            first = tuple((a + 2 * b) / 3 for a, b in zip(point, control))
            second = tuple((a + 2 * b) / 3 for a, b in zip(end, control))
            point = end
            yield 3, first + second + end
        elif command == "C":
            point = args[-2:]
            yield 3, args
        else:
            point = (args[0], point[1]) if command == "H" else (point[0], args[0]) if command == "V" else args
            yield 2, point
        previous_control = control


def shape_operations(kind: str, attributes: dict[str, str]):
    def coordinates(*names):
        return tuple(float(attributes[k]) for k in names)

    if kind == "rect":
        yield 4, coordinates("x", "y", "width", "height")
    elif kind in ("circle", "ellipse"):
        cx, cy = coordinates("cx", "cy")
        rx, ry = coordinates("rx", "ry") if kind == "ellipse" else coordinates("r") * 2
        yield 5, (cx - rx, cy - ry, 2 * rx, 2 * ry)
    elif kind == "line":
        yield 1, coordinates("x1", "y1")
        yield 2, coordinates("x2", "y2")
    elif kind == "polygon":
        points = iter(float(point) for point in TOKEN.findall(attributes["points"]))
        for index, point in enumerate(zip(points, points)):
            yield (1 if index == 0 else 2), point
        yield 0, ()
    elif kind == "path":
        yield from path_operations(attributes["d"])
    else:
        raise ValueError(f"Unsupported SVG element: {kind}")


def compile_sprites(media: Path, output: Path) -> None:
    colors = [0]

    def color(value):
        rgba = 0 if value in ("none", "transparent") else 0xFF000000 | int(value.lstrip("#"), 16)
        if rgba not in colors:
            colors.append(rgba)
        return colors.index(rgba)

    sprites = bytearray()
    for name in (*CELLS, *FACES):
        if name is None:
            sprites.extend(struct.pack("<HB", 0, 0))
            continue
        svg = ET.parse(media / f"{name}.svg").getroot()
        shapes = []
        for shape in svg:
            kind = shape.tag.split("}")[-1]
            attributes = shape.attrib
            fill = color(attributes.get("fill", "none" if kind == "line" else "#000000"))
            stroke = color(attributes.get("stroke", "none"))
            if not fill and not stroke:
                continue
            operations = list(shape_operations(kind, attributes))
            binary = bytearray(struct.pack("<BBHB", fill, stroke, round(float(attributes.get("stroke-width", "1")) * 3),
                                           len(operations)))
            for code, values in operations:
                binary.append(code)
                binary.extend(struct.pack(f"<{len(values)}h", *(round(value * 3) for value in values)))
            shapes.append(binary)
        sprites.extend(struct.pack("<HB", int(svg.attrib["width"]), len(shapes)))
        for shape in shapes:
            sprites.extend(shape)
    output.write_bytes(bytes([len(colors)]) + struct.pack(f"<{len(colors)}I", *colors) + sprites)



def pack_countries(source: Path, output: Path) -> None:
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    mapping = ast.literal_eval(tree.body[0].value)
    rows = (f"{code.upper()}\t{name}\n" for name, code in mapping.items()
            if len(code) == 2 and code.isascii() and code.isalpha())
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    output.write_bytes(compressor.compress("".join(rows).encode("utf-8")) + compressor.flush())


if __name__ == "__main__":
    source = Path(__file__).resolve().parents[1] / "src"
    output = Path(sys.argv[1])
    compile_sprites(source / "media", output / "classic-shapes.bin")
    pack_countries(source / "country_name.py", output / "countries.deflate")
