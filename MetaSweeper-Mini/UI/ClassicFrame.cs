using System;
using System.Drawing;
using System.Windows.Forms;

internal sealed class ClassicFrame : Panel
{
    internal static readonly Color Canvas = Color.Silver;
    internal static readonly Color Surface = Color.White;
    internal static readonly Color Line = Color.Gray;
    internal static readonly Color Ink = Color.Black;
    internal static readonly Color Muted = Color.FromArgb(36, 36, 36);

    private static readonly Brush Shade = new SolidBrush(Color.FromArgb(160, 160, 160));
    internal int Edge { get; set; }

    internal ClassicFrame()
    {
        BackColor = Canvas;
        DoubleBuffered = true;
        ResizeRedraw = true;
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        DrawBevel(e.Graphics, ClientRectangle, Edge, true);
    }

    internal static void DrawBevel(Graphics g, Rectangle r, int edge, bool raised)
    {
        if (r.Width <= 2 * edge || r.Height <= 2 * edge)
            return;
        int left = r.Left, top = r.Top, right = r.Right, bottom = r.Bottom;
        g.FillPolygon(raised ? Brushes.White : Shade, new[] {
            new Point(left, top), new Point(right, top), new Point(right - edge, top + edge),
            new Point(left + edge, top + edge), new Point(left + edge, bottom - edge), new Point(left, bottom)
        });
        g.FillPolygon(raised ? Shade : Brushes.White, new[] {
            new Point(right, bottom), new Point(left, bottom), new Point(left + edge, bottom - edge),
            new Point(right - edge, bottom - edge), new Point(right - edge, top + edge), new Point(right, top)
        });
    }
}
