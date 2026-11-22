using System;
using System.Drawing;

internal struct BoardLayout
{
    internal const int MenuHeight = 27;
    internal const int IdentityHeight = 41;
    internal const int BoardGap = 8;
    private const int StatusGap = 8;

    internal readonly int Tile, OuterEdge, InnerEdge, OuterInset, StatusInset, SpriteHeight, DigitWidth;

    internal BoardLayout(int tile, int bevelReferenceTile)
    {
        Tile = tile;
        // The original starts with 6/4 px bevels and scales them from its initial cell size.
        double scale = bevelReferenceTile == 0 ? 1 : (double)tile / bevelReferenceTile;
        OuterEdge = Math.Max(1, (int)Math.Round(6 * scale));
        InnerEdge = Math.Max(1, (int)Math.Round(4 * scale));
        OuterInset = OuterEdge + 10;
        StatusInset = InnerEdge + 5;
        SpriteHeight = tile * 3 / 2;
        DigitWidth = tile * 312 / 368;
    }

    internal int StatusHeight { get { return SpriteHeight + 2 * StatusInset; } }

    internal Size ClientSize(int rows, int columns, bool showIdentity)
    {
        int boardWidth = columns * Tile + 2 * InnerEdge;
        int statusWidth = 6 * DigitWidth + SpriteHeight + 2 * StatusInset + 2 * StatusGap;
        int height = rows * Tile + 2 * InnerEdge + BoardGap + StatusHeight + 2 * OuterInset
            + MenuHeight + (showIdentity ? IdentityHeight : 0);
        return new Size(Math.Max(boardWidth, statusWidth) + 2 * OuterInset, height);
    }
}
