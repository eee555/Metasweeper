using System;
using System.Drawing;
using System.Windows.Forms;

internal sealed class DisplayPanel : Panel
{
    private readonly FaceButton face = new FaceButton();
    private int remaining;
    private long seconds;
    private bool restartPressed;

    private BoardLayout layout;
    internal event EventHandler Restart;

    internal DisplayPanel()
    {
        BackColor = ClassicFrame.Canvas;
        Cursor = Cursors.Hand;
        Controls.Add(face);
        DoubleBuffered = true;
        ResizeRedraw = true;
        face.Click += (s, e) => RequestRestart();
    }

    protected override void OnResize(EventArgs e)
    {
        base.OnResize(e);
        PositionFace();
    }

    protected override void OnMouseDown(MouseEventArgs e)
    {
        base.OnMouseDown(e);
        if (e.Button == MouseButtons.Left)
        {
            restartPressed = true;
            Capture = true;
        }
    }

    protected override void OnMouseCaptureChanged(EventArgs e)
    {
        base.OnMouseCaptureChanged(e);
        if (!Capture)
            restartPressed = false;
    }

    protected override void OnMouseUp(MouseEventArgs e)
    {
        base.OnMouseUp(e);
        if (e.Button != MouseButtons.Left)
            return;
        bool restart = restartPressed && ClientRectangle.Contains(e.Location);
        restartPressed = false;
        Capture = false;
        if (restart)
            RequestRestart();
    }

    private void RequestRestart()
    {
        if (Restart != null)
            Restart(this, EventArgs.Empty);
    }

    private void PositionFace()
    {
        int size = layout.SpriteHeight;
        face.Bounds = new Rectangle((Width - size) / 2, (Height - size) / 2, size, size);
    }

    internal void ApplyLayout(BoardLayout layout)
    {
        if (this.layout.Tile == layout.Tile && this.layout.InnerEdge == layout.InnerEdge)
            return;
        this.layout = layout;
        Height = layout.StatusHeight;
        PositionFace();
        Invalidate();
    }

    internal void UpdatePress(Game.Phase state, bool pressing)
    {
        face.UpdateFace(state, pressing);
    }

    internal void Update(int mines, long elapsed, Game.Phase state, bool pressing)
    {
        face.UpdateFace(state, pressing);
        if (remaining == mines && seconds == elapsed)
            return;

        remaining = mines;
        seconds = elapsed;
        UpdateAccessibleStatus();
        Invalidate();
    }

    internal void ApplyLanguage()
    {
        face.AccessibleName = UiText.Get(TextId.Restart);
        UpdateAccessibleStatus();
    }

    private void UpdateAccessibleStatus()
    {
        AccessibleName = string.Format(UiText.Get(TextId.DisplayStatus), remaining, seconds);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        if (layout.Tile == 0)
            return;
        ClassicFrame.DrawBevel(e.Graphics, ClientRectangle, layout.InnerEdge, false);
        int height = layout.SpriteHeight;
        int width = layout.DigitWidth;
        int y = (Height - height) / 2;
        int margin = layout.StatusInset;
        DrawCounter(e.Graphics, margin, y, width, height, Math.Max(0, Math.Min(999, remaining)));
        DrawCounter(e.Graphics, Width - margin - 3 * width, y, width, height, (int)Math.Min(seconds, 999));
    }

    private static void DrawCounter(Graphics g, int x, int y, int w, int h, int value)
    {
        ClassicSprites.DrawDigit(g, new Rectangle(x, y, w, h), value / 100);
        ClassicSprites.DrawDigit(g, new Rectangle(x + w, y, w, h), value / 10 % 10);
        ClassicSprites.DrawDigit(g, new Rectangle(x + 2 * w, y, w, h), value % 10);
    }
}
