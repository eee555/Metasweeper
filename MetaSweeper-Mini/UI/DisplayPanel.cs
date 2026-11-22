using System;
using System.Drawing;
using System.Windows.Forms;

internal sealed class DisplayPanel : Panel
{
    private readonly FaceButton face = new FaceButton();
    private int remaining;
    private long seconds;
    private bool restartPressed;

    private int spriteSize;
    internal int SpriteSize
    {
        get { return spriteSize; }
        set
        {
            if (spriteSize == value)
                return;
            spriteSize = value;
            PositionFace();
            Invalidate();
        }
    }
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
        int size = Math.Max(1, SpriteSize);
        face.Bounds = new Rectangle((Width - size) / 2, (Height - size) / 2, size, size);
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
        AccessibleName = string.Format("剩雷 {0}，用时 {1} 秒", remaining, seconds);
        Invalidate();
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        int edge = Math.Max(2, SpriteSize / 10);
        ClassicFrame.DrawBevel(e.Graphics, ClientRectangle, edge, false);
        int height = Math.Max(1, SpriteSize);
        int width = Math.Max(1, height * 13 / 23);
        int y = (Height - height) / 2;
        int margin = edge + Math.Max(3, SpriteSize / 8);
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
