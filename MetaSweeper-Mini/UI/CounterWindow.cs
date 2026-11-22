using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Globalization;
using System.Windows.Forms;

internal sealed class CounterWindow : Form
{
    private const int HeadingHeight = 37;
    private const int HitTest = 0x84, MoveEnded = 0x232;
    internal event EventHandler PositionCommitted;
    internal Func<Keys, bool> HandleShortcut;

    private static readonly string[] Names = {
        null, "rtime", "Est Rtime", "3bv", "3bv/s", "zini", "ops", "isls",
        "left", "right", "double", "stnb", "ioe", "thrp", "corr", "path", "pluck"
    };

    private readonly string[] values = new string[Names.Length];
    private string gameModeName;
    private int nameWidth;
    private bool finalShown;
    private Font body = new Font(SystemFonts.MessageBoxFont.FontFamily, 15, GraphicsUnit.Pixel);
    private readonly TextFormatFlags cellText = TextFormatFlags.Left | TextFormatFlags.VerticalCenter
        | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix | TextFormatFlags.PreserveGraphicsClipping;

    protected override bool ShowWithoutActivation { get { return true; } }

    internal CounterWindow()
    {
        FormBorderStyle = FormBorderStyle.None;
        ShowInTaskbar = false;
        StartPosition = FormStartPosition.Manual;
        DoubleBuffered = true;
        BackColor = Color.FromArgb(245, 245, 245);
        for (int i = 0; i < values.Length; i++)
            values[i] = "--";
    }

    internal void ApplyLanguage()
    {
        Text = UiText.Get(TextId.Counter);
        AccessibleName = Text;
        gameModeName = UiText.Get(TextId.GameMode);
        values[0] = UiText.Get(TextId.Standard);
    }

    protected override void WndProc(ref Message message)
    {
        base.WndProc(ref message);
        if (message.Msg == HitTest && message.Result == new IntPtr(1))
        {
            long packed = message.LParam.ToInt64();
            var screen = new Point(unchecked((short)packed), unchecked((short)(packed >> 16)));
            if (PointToClient(screen).Y < HeadingHeight)
                message.Result = new IntPtr(2);
        }
        else if (message.Msg == MoveEnded && PositionCommitted != null)
            PositionCommitted(this, EventArgs.Empty);
    }

    protected override bool ProcessCmdKey(ref Message message, Keys key)
    {
        return (HandleShortcut != null && HandleShortcut(key)) || base.ProcessCmdKey(ref message, key);
    }

    internal void Adapt(float scale, int maxHeight)
    {
        SuspendLayout();
        finalShown = false;
        body.Dispose();
        body = new Font(SystemFonts.MessageBoxFont.FontFamily, Math.Max(12, 15 * scale), GraphicsUnit.Pixel);
        int row = Math.Max(19, (int)Math.Round(33 * scale));
        int baseWidth = (int)Math.Round(256 * scale);
        int defaultNameWidth = (baseWidth - 17) * 35 / 100;
        nameWidth = Math.Max(defaultNameWidth, TextRenderer.MeasureText(gameModeName, body).Width + 6);
        ClientSize = new Size(baseWidth + nameWidth - defaultNameWidth,
            Math.Min(maxHeight, row * values.Length + (int)Math.Round(48 * scale)));
        using (var outline = new GraphicsPath())
        {
            int right = ClientSize.Width, bottom = ClientSize.Height;
            const int diameter = 16;
            outline.AddArc(0, 0, diameter, diameter, 180, 90);
            outline.AddArc(right - diameter, 0, diameter, diameter, 270, 90);
            outline.AddArc(right - diameter, bottom - diameter, diameter, diameter, 0, 90);
            outline.AddArc(0, bottom - diameter, diameter, diameter, 90, 90);
            outline.CloseFigure();
            Region = new Region(outline);
        }
        ResumeLayout(true);
        if (IsHandleCreated)
            Refresh();
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
            body.Dispose();
        base.Dispose(disposing);
    }

    internal void Display(Game game)
    {
        double time = game.ElapsedSeconds;
        ReplayMetrics? final = game.Metrics;
        bool hasFinal = final.HasValue;

        Rectangle table = TableArea;
        int x = Divider(table) + 1;
        UpdateRow(1, Format(time, "0.000"), table, x);
        UpdateRow(8, Rate(game.Left, time), table, x);
        UpdateRow(9, Rate(game.Right, time), table, x);
        UpdateRow(10, Rate(game.Chords, time), table, x);
        UpdateRow(15, Format(game.CursorPath, "0.0"), table, x);

        if (!hasFinal)
        {
            ResetFinalRows(table, x);
        }
        else if (!finalShown)
        {
            finalShown = true;
            ReplayMetrics metrics = final.Value;
            UpdateRow(2, Format(metrics.EstimatedTime, "0.000"), table, x);
            UpdateRow(3, metrics.Solved + "/" + metrics.Total, table, x);
            UpdateRow(4, Format(metrics.Speed, "0.000"), table, x);
            UpdateRow(5, metrics.Zini + "@" + Format(metrics.Zini / metrics.EstimatedTime, "0.000"), table, x);
            UpdateRow(6, metrics.Openings.ToString(), table, x);
            UpdateRow(7, metrics.Islands.ToString(), table, x);
            UpdateRow(11, Format(metrics.Stnb, "0.000"), table, x);
            UpdateRow(12, Format(metrics.Ioe, "0.000"), table, x);
            UpdateRow(13, Format(metrics.Thrp, "0.000"), table, x);
            UpdateRow(14, Format(metrics.Corr, "0.000"), table, x);
            UpdateRow(16, Format(metrics.Pluck, "0.000"), table, x);
        }
    }

    private void ResetFinalRows(Rectangle table, int x)
    {
        UpdateRow(2, "--", table, x);
        UpdateRow(3, "--", table, x);
        UpdateRow(4, "--", table, x);
        UpdateRow(5, "--", table, x);
        UpdateRow(6, "--", table, x);
        UpdateRow(7, "--", table, x);
        UpdateRow(11, "--", table, x);
        UpdateRow(12, "--", table, x);
        UpdateRow(13, "--", table, x);
        UpdateRow(14, "--", table, x);
        UpdateRow(16, "--", table, x);
    }

    private void UpdateRow(int index, string text, Rectangle table, int x)
    {
        if (values[index] == text)
            return;
        values[index] = text;
        Rectangle row = RowArea(table, index);
        if (table.Right > x && row.Height > 1)
            Invalidate(Rectangle.FromLTRB(x, row.Top + 1, table.Right, row.Bottom));
    }

    private static string Rate(int count, double time)
    {
        return count + "@" + Format(time > 0 ? count / time : 0, "0.000");
    }

    private static string Format(double value, string pattern)
    {
        if (double.IsNaN(value))
            return "--";
        if (double.IsPositiveInfinity(value))
            return "∞";
        return value.ToString(pattern, CultureInfo.InvariantCulture);
    }

    private Rectangle TableArea
    {
        get
        {
            const int edge = 8;
            return new Rectangle(edge, HeadingHeight, ClientSize.Width - edge * 2 - 1, ClientSize.Height - HeadingHeight - edge);
        }
    }

    private int Divider(Rectangle table) { return table.Left + nameWidth; }

    private Rectangle RowArea(Rectangle table, int index)
    {
        int top = table.Top + index * table.Height / Names.Length;
        int bottom = table.Top + (index + 1) * table.Height / Names.Length;
        return Rectangle.FromLTRB(table.Left, top, table.Right, bottom);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        Rectangle table = TableArea;
        int divider = Divider(table);
        var heading = new Rectangle(0, 0, ClientSize.Width, HeadingHeight);
        if (heading.IntersectsWith(e.ClipRectangle))
            TextRenderer.DrawText(e.Graphics, Text, body, heading, ClassicFrame.Ink,
                TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPrefix);
        e.Graphics.FillRectangle(Brushes.White, Rectangle.Intersect(table, e.ClipRectangle));
        using (var pen = new Pen(Color.FromArgb(211, 211, 211)) { DashStyle = DashStyle.Dash })
        {
            for (int index = 0; index < Names.Length; index++)
            {
                Rectangle row = RowArea(table, index);
                if (!e.Graphics.IsVisible(row))
                    continue;
                if (index != 0)
                    e.Graphics.DrawLine(pen, table.Left, row.Top, table.Right, row.Top);
                var name = new Rectangle(table.Left + 3, row.Top, divider - table.Left - 5, row.Height);
                var value = new Rectangle(divider + 4, row.Top, table.Right - divider - 5, row.Height);
                if (e.Graphics.IsVisible(name))
                    TextRenderer.DrawText(e.Graphics, Names[index] ?? gameModeName, body, name, ClassicFrame.Muted, cellText);
                if (e.Graphics.IsVisible(value))
                    TextRenderer.DrawText(e.Graphics, values[index], body, value, ClassicFrame.Ink, cellText);
            }
            e.Graphics.DrawLine(pen, divider, table.Top, divider, table.Bottom);
        }
        using (var border = new Pen(ClassicFrame.Line))
            e.Graphics.DrawRectangle(border, table);
    }
}
