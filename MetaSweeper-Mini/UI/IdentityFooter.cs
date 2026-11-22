using System;
using System.Drawing;
using System.Windows.Forms;

internal sealed class IdentityFooter : Control
{
    private readonly ToolTip tooltip = new ToolTip();

    internal IdentityFooter()
    {
        Dock = DockStyle.Bottom;
        BackColor = ClassicFrame.Canvas;
        ForeColor = ClassicFrame.Muted;
        DoubleBuffered = true;
        ResizeRedraw = true;
    }

    internal void ShowIdentity(string player, string countryCode)
    {
        Text = countryCode.Length == 0 ? player : player + "  ·  " + countryCode;
        AccessibleName = Text;
        tooltip.SetToolTip(this, Text);
        Invalidate();
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
            tooltip.Dispose();
        base.Dispose(disposing);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        Rectangle area = Rectangle.Inflate(ClientRectangle, -10, 0);
        const TextFormatFlags flags = TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter
            | TextFormatFlags.SingleLine | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix;
        TextRenderer.DrawText(e.Graphics, Text, Font, area, ForeColor, flags);
    }
}
