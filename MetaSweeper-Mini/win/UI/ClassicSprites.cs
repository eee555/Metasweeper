using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;

internal static class ClassicSprites
{
    private const int CellCount = 17, FaceCount = 5;
    private static readonly Shape[][] Shapes = ReadShapes();
    private static readonly Atlas Cells = new Atlas(0, CellCount, 160);
    private static readonly Atlas Faces = new Atlas(CellCount, FaceCount, 260);
    private const int DigitWidth = 13, DigitHeight = 23;
    private static readonly Brush DimSegment = new SolidBrush(Color.FromArgb(128, 0, 0));
    private static readonly DigitAtlas Digits = new DigitAtlas(10);

    // The original LED glyphs are 13 x 23 pixel patterns with three colors.
    // Each row packs two bits per pixel: black, dark red, or lit red.
    private static readonly uint[][] LedRows = {
        new uint[] {
            0x0000000u, 0x02AAAA0u, 0x08AAA88u, 0x0A2AA28u, 0x0A800A8u, 0x0A800A8u,
            0x0A800A8u, 0x0A800A8u, 0x0A800A8u, 0x0A00028u, 0x0811108u, 0x0044440u,
            0x0811108u, 0x0A00028u, 0x0A800A8u, 0x0A800A8u, 0x0A800A8u, 0x0A800A8u,
            0x0A800A8u, 0x0A2AA28u, 0x08AAA88u, 0x02AAAA0u, 0x0000000u
        },
        new uint[] {
            0x0000000u, 0x0044440u, 0x0811104u, 0x0A04410u, 0x0A80044u, 0x0A80010u,
            0x0A80044u, 0x0A80010u, 0x0A80044u, 0x0A00010u, 0x0811104u, 0x0044440u,
            0x0811104u, 0x0A00010u, 0x0A80044u, 0x0A80010u, 0x0A80044u, 0x0A80010u,
            0x0A80044u, 0x0A04410u, 0x0811104u, 0x0044440u, 0x0000000u
        },
        new uint[] {
            0x0000000u, 0x02AAAA0u, 0x08AAA84u, 0x0A2AA10u, 0x0A80044u, 0x0A80010u,
            0x0A80044u, 0x0A80010u, 0x0A80044u, 0x0A00010u, 0x08AAA84u, 0x02AAAA0u,
            0x04AAA88u, 0x0100028u, 0x04400A8u, 0x01000A8u, 0x04400A8u, 0x01000A8u,
            0x04400A8u, 0x012AA28u, 0x04AAA88u, 0x02AAAA0u, 0x0000000u
        },
        new uint[] {
            0x0000000u, 0x02AAAA0u, 0x08AAA84u, 0x0A2AA10u, 0x0A80044u, 0x0A80010u,
            0x0A80044u, 0x0A80010u, 0x0A80044u, 0x0A00010u, 0x08AAA84u, 0x02AAAA0u,
            0x08AAA84u, 0x0A00010u, 0x0A80044u, 0x0A80010u, 0x0A80044u, 0x0A80010u,
            0x0A80044u, 0x0A2AA10u, 0x08AAA84u, 0x02AAAA0u, 0x0000000u
        },
        new uint[] {
            0x0000000u, 0x0044440u, 0x0811108u, 0x0A04428u, 0x0A800A8u, 0x0A800A8u,
            0x0A800A8u, 0x0A800A8u, 0x0A800A8u, 0x0A00028u, 0x08AAA88u, 0x02AAAA0u,
            0x08AAA84u, 0x0A00010u, 0x0A80044u, 0x0A80010u, 0x0A80044u, 0x0A80010u,
            0x0A80044u, 0x0A04410u, 0x0811104u, 0x0044440u, 0x0000000u
        },
        new uint[] {
            0x0000000u, 0x02AAAA0u, 0x04AAA88u, 0x012AA28u, 0x04400A8u, 0x01000A8u,
            0x04400A8u, 0x01000A8u, 0x04400A8u, 0x0100028u, 0x04AAA88u, 0x02AAAA0u,
            0x08AAA84u, 0x0A00010u, 0x0A80044u, 0x0A80010u, 0x0A80044u, 0x0A80010u,
            0x0A80044u, 0x0A2AA10u, 0x08AAA84u, 0x02AAAA0u, 0x0000000u
        },
        new uint[] {
            0x0000000u, 0x02AAAA0u, 0x04AAA88u, 0x012AA28u, 0x04400A8u, 0x01000A8u,
            0x04400A8u, 0x01000A8u, 0x04400A8u, 0x0100028u, 0x04AAA88u, 0x02AAAA0u,
            0x08AAA88u, 0x0A00028u, 0x0A800A8u, 0x0A800A8u, 0x0A800A8u, 0x0A800A8u,
            0x0A800A8u, 0x0A2AA28u, 0x08AAA88u, 0x02AAAA0u, 0x0000000u
        },
        new uint[] {
            0x0000000u, 0x02AAAA0u, 0x08AAA84u, 0x0A2AA10u, 0x0A80044u, 0x0A80010u,
            0x0A80044u, 0x0A80010u, 0x0A80044u, 0x0A00010u, 0x0811104u, 0x0044440u,
            0x0811104u, 0x0A00010u, 0x0A80044u, 0x0A80010u, 0x0A80044u, 0x0A80010u,
            0x0A80044u, 0x0A04410u, 0x0811104u, 0x0044440u, 0x0000000u
        },
        new uint[] {
            0x0000000u, 0x02AAAA0u, 0x08AAA88u, 0x0A2AA28u, 0x0A800A8u, 0x0A800A8u,
            0x0A800A8u, 0x0A800A8u, 0x0A800A8u, 0x0A00028u, 0x08AAA88u, 0x02AAAA0u,
            0x08AAA88u, 0x0A00028u, 0x0A800A8u, 0x0A800A8u, 0x0A800A8u, 0x0A800A8u,
            0x0A800A8u, 0x0A2AA28u, 0x08AAA88u, 0x02AAAA0u, 0x0000000u
        },
        new uint[] {
            0x0000000u, 0x02AAAA0u, 0x08AAA88u, 0x0A2AA28u, 0x0A800A8u, 0x0A800A8u,
            0x0A800A8u, 0x0A800A8u, 0x0A800A8u, 0x0A00028u, 0x08AAA88u, 0x02AAAA0u,
            0x08AAA84u, 0x0A00010u, 0x0A80044u, 0x0A80010u, 0x0A80044u, 0x0A80010u,
            0x0A80044u, 0x0A2AA10u, 0x08AAA84u, 0x02AAAA0u, 0x0000000u
        },
    };

    internal static void DrawCell(Graphics g, Rectangle target, byte value)
    {
        Cells.Draw(g, target, value);
    }

    internal static void DrawFace(Graphics g, Rectangle target, int face)
    {
        Faces.Draw(g, target, face);
    }

    internal static void DrawDigit(Graphics g, Rectangle target, int digit)
    {
        Digits.Draw(g, target, digit);
    }

    private static void DrawDigitInto(Graphics g, Rectangle target, int digit)
    {
        uint[] rows = LedRows[digit];
        for (int y = 0; y < DigitHeight; y++)
        {
            int top = ScaleEdge(y, target.Height, DigitHeight);
            int bottom = ScaleEdge(y + 1, target.Height, DigitHeight);
            uint row = rows[y];
            for (int x = 0; x < DigitWidth; x++, row >>= 2)
            {
                uint shade = row & 3;
                if (shade == 0)
                    continue;
                int left = ScaleEdge(x, target.Width, DigitWidth);
                int right = ScaleEdge(x + 1, target.Width, DigitWidth);
                g.FillRectangle(shade == 1 ? DimSegment : Brushes.Red,
                    target.Left + left, target.Top + top, right - left, bottom - top);
            }
        }
    }

    private sealed class DigitAtlas
    {
        private readonly Bitmap[] tiles;
        private int side, width;

        internal DigitAtlas(int count)
        {
            tiles = new Bitmap[count];
        }

        internal void Draw(Graphics g, Rectangle destination, int digit)
        {
            if (destination.Width <= 0 || destination.Height <= 0)
                return;
            if (side != destination.Height || width != destination.Width)
            {
                for (int i = 0; i < tiles.Length; i++)
                {
                    if (tiles[i] != null)
                        tiles[i].Dispose();
                    tiles[i] = null;
                }
                side = destination.Height;
                width = destination.Width;
            }
            if (tiles[digit] == null)
            {
                var tile = new Bitmap(Math.Max(1, width), Math.Max(1, side));
                using (var paint = Graphics.FromImage(tile))
                {
                    paint.Clear(Color.Black);
                    DrawDigitInto(paint, new Rectangle(0, 0, tile.Width, tile.Height), digit);
                }
                tiles[digit] = tile;
            }
            g.DrawImageUnscaled(tiles[digit], destination.Location);
        }
    }

    private static int ScaleEdge(int index, int length, int original)
    {
        return (index * length + original / 2) / original;
    }

    private sealed class Atlas
    {
        private readonly int start, designSize;
        private readonly Bitmap[] tiles;
        private int side;

        internal Atlas(int start, int count, int designSize)
        {
            this.start = start;
            this.designSize = designSize;
            tiles = new Bitmap[count];
        }

        internal void Draw(Graphics g, Rectangle destination, int index)
        {
            if (destination.Width <= 0 || destination.Height <= 0)
                return;
            if (side != destination.Width)
            {
                for (int i = 0; i < tiles.Length; i++)
                {
                    if (tiles[i] != null)
                        tiles[i].Dispose();
                    tiles[i] = null;
                }
                side = destination.Width;
            }
            if (tiles[index] == null)
            {
                var tile = new Bitmap(side, side);
                using (var paint = Graphics.FromImage(tile))
                {
                    paint.Clear(ClassicFrame.Canvas);
                    paint.SmoothingMode = SmoothingMode.AntiAlias;
                    paint.ScaleTransform((float)side / designSize, (float)side / designSize);
                    foreach (Shape shape in Shapes[start + index])
                        shape.Draw(paint);
                }
                tiles[index] = tile;
            }
            g.DrawImageUnscaled(tiles[index], destination.Location);
        }
    }

    private sealed class Shape
    {
        private readonly GraphicsPath path = new GraphicsPath(FillMode.Winding);
        private readonly Brush fill;
        private readonly Pen stroke;

        internal Shape(BinaryReader data, Color[] palette)
        {
            Color face = palette[data.ReadByte()];
            Color edge = palette[data.ReadByte()];
            float width = data.ReadUInt16() / 3f;
            if (face.A != 0)
                fill = new SolidBrush(face);
            if (edge.A != 0)
                stroke = new Pen(edge, width);
            PointF previous = PointF.Empty;
            int operations = data.ReadByte();
            for (int i = 0; i < operations; i++)
            {
                switch (data.ReadByte())
                {
                    case 0:
                        path.CloseFigure();
                        break;
                    case 1:
                        path.StartFigure();
                        previous = ReadPoint(data);
                        break;
                    case 2:
                        PointF end = ReadPoint(data);
                        path.AddLine(previous, end);
                        previous = end;
                        break;
                    case 3:
                        PointF c1 = ReadPoint(data), c2 = ReadPoint(data), next = ReadPoint(data);
                        path.AddBezier(previous, c1, c2, next);
                        previous = next;
                        break;
                    case 4:
                        path.AddRectangle(ReadRectangle(data));
                        break;
                    case 5:
                        path.AddEllipse(ReadRectangle(data));
                        break;
                }
            }
        }

        internal void Draw(Graphics g)
        {
            if (fill != null)
                g.FillPath(fill, path);
            if (stroke != null)
                g.DrawPath(stroke, path);
        }
    }

    private static PointF ReadPoint(BinaryReader data)
    {
        return new PointF(data.ReadInt16() / 3f, data.ReadInt16() / 3f);
    }

    private static RectangleF ReadRectangle(BinaryReader data)
    {
        PointF origin = ReadPoint(data), extent = ReadPoint(data);
        return new RectangleF(origin.X, origin.Y, extent.X, extent.Y);
    }

    private static Shape[][] ReadShapes()
    {
        var sprites = new Shape[CellCount + FaceCount][];
        using (var bytes = typeof(ClassicSprites).Assembly.GetManifestResourceStream("classic-shapes.bin"))
        using (var data = new BinaryReader(bytes))
        {
            var palette = new Color[data.ReadByte()];
            for (int i = 0; i < palette.Length; i++)
                palette[i] = Color.FromArgb(data.ReadInt32());
            for (int i = 0; i < sprites.Length; i++)
            {
                data.ReadUInt16();
                var sprite = new Shape[data.ReadByte()];
                for (int element = 0; element < sprite.Length; element++)
                    sprite[element] = new Shape(data, palette);
                sprites[i] = sprite;
            }
        }
        return sprites;
    }
}
