using System;
using System.Drawing;
using System.Windows.Forms;

internal sealed class IdentityFooter : Control
{
    private readonly ToolTip tooltip = new ToolTip();
    private string country = "";

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
        Text = player;
        country = countryCode;
        AccessibleName = country.Length == 0 ? player : player + "  ·  " + country;
        tooltip.SetToolTip(this, AccessibleName);
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
        const TextFormatFlags flags = TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter
            | TextFormatFlags.SingleLine | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix;
        int nameWidth = Width;
        if (country.Length != 0)
        {
            const int countryWidth = 51, countryHeight = 31, rightMargin = 6;
            nameWidth -= countryWidth + rightMargin;
            var countryArea = new Rectangle(nameWidth, (Height - countryHeight) / 2, countryWidth, countryHeight);
            TextRenderer.DrawText(e.Graphics, country, Font, countryArea, ForeColor, flags);
        }
        Rectangle area = new Rectangle(6, 0, Math.Max(0, nameWidth - 12), Height);
        TextRenderer.DrawText(e.Graphics, Text, Font, area, ForeColor, flags);
    }
}
