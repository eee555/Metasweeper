using System;
using System.Drawing;
using System.Windows.Forms;

internal sealed class BoardView : Control
{
    internal int Inset { get; set; }
    internal int TilePixels { get; set; }

    private Game game;
    private byte[] visibleTiles;
    private MouseButtons buttons;
    private Point pointer = new Point(-1, -1);
    private bool facePressed;
    private bool releasing;

    internal bool Pressing { get { return game != null && game.CanPlay && facePressed; } }
    internal event EventHandler Changed;
    internal event EventHandler PressChanged;

    internal BoardView()
    {
        BackColor = ClassicFrame.Canvas;
        Inset = 4;
        TilePixels = BoardPixels.Minimum;
        DoubleBuffered = true;
        ResizeRedraw = true;
        SetStyle(ControlStyles.StandardClick | ControlStyles.StandardDoubleClick, false);
    }

    internal void SetGame(Game newGame)
    {
        game = newGame;
        visibleTiles = new byte[game.Rows * game.Columns];
        for (int i = 0; i < visibleTiles.Length; i++)
            visibleTiles[i] = game.Display(i);
        buttons = MouseButtons.None;
        pointer = new Point(-1, -1);
        facePressed = false;
        Capture = false;
        Invalidate();
    }

    internal Rectangle ScreenBoardBounds { get { return RectangleToScreen(BoardBounds); } }

    private Rectangle BoardBounds
    {
        get
        {
            var size = new Size(game.Columns * TilePixels, game.Rows * TilePixels);
            const int gap = BoardLayout.BoardGap;
            return new Rectangle((Width - size.Width) / 2, gap + (Height - gap - size.Height) / 2,
                size.Width, size.Height);
        }
    }

    private int CellAt(Point point)
    {
        if (game == null)
            return -1;
        Rectangle bounds = BoardBounds;
        if (!bounds.Contains(point))
            return -1;
        return (point.Y - bounds.Top) / TilePixels * game.Columns + (point.X - bounds.Left) / TilePixels;
    }

    private Point ReplayPoint(Point point)
    {
        Rectangle bounds = BoardBounds;
        int scale = NativeCore.CellPixels;
        if (!bounds.Contains(point))
            return new Point(game.Columns * scale, game.Rows * scale);
        return new Point((point.X - bounds.X) * scale / TilePixels, (point.Y - bounds.Y) * scale / TilePixels);
    }

    protected override void OnMouseMove(MouseEventArgs e)
    {
        base.OnMouseMove(e);
        MovePointer(e.Location);
    }

    protected override void OnMouseLeave(EventArgs e)
    {
        base.OnMouseLeave(e);
        MovePointer(new Point(-1, -1));
    }

    private void MovePointer(Point position)
    {
        if (game == null || !game.CanPlay)
            return;
        Rectangle before = PressedArea();
        pointer = position;
        game.TrackCursor(ReplayPoint(position));
        InvalidatePress(before, PressedArea());
    }

    protected override void OnMouseDown(MouseEventArgs e)
    {
        if (game == null || !game.CanPlay || CellAt(e.Location) < 0 ||
            (e.Button != MouseButtons.Left && e.Button != MouseButtons.Right) ||
            (buttons & e.Button) != 0)
            return;
        base.OnMouseDown(e);
        buttons |= e.Button;
        Capture = true;
        SendButton(e.Button, true, e.Location);
    }

    protected override void WndProc(ref Message message)
    {
        if (message.Msg == 0x0203 || message.Msg == 0x0206) // Double click also includes a button-down.
            message.Msg -= 2;
        if (message.Msg != 0x0202 && message.Msg != 0x0205) // WM_LBUTTONUP / WM_RBUTTONUP
        {
            base.WndProc(ref message);
            return;
        }
        releasing = true;
        try { base.WndProc(ref message); }
        finally
        {
            releasing = false;
            // WinForms releases capture on each button-up, even when the other button is held.
            if (buttons != MouseButtons.None && game != null && game.CanPlay)
                Capture = true;
        }
    }

    protected override void OnMouseCaptureChanged(EventArgs e)
    {
        base.OnMouseCaptureChanged(e);
        if (Capture || releasing || buttons == MouseButtons.None)
            return;
        MouseButtons held = buttons;
        buttons = MouseButtons.None;
        var outside = new Point(-1, -1);
        if ((held & MouseButtons.Left) != 0)
            SendButton(MouseButtons.Left, false, outside);
        if ((held & MouseButtons.Right) != 0)
            SendButton(MouseButtons.Right, false, outside);
    }

    protected override void OnMouseUp(MouseEventArgs e)
    {
        if (game == null || !game.CanPlay)
            return;
        base.OnMouseUp(e);
        if ((buttons & e.Button) == 0)
            return;
        buttons &= ~e.Button;
        SendButton(e.Button, false, e.Location);
        if (buttons == MouseButtons.None)
            Capture = false;
    }

    private void SendButton(MouseButtons button, bool down, Point position)
    {
        if (game == null || !game.CanPlay)
            return;
        Rectangle before = PressedArea();
        bool wasPressing = Pressing;
        pointer = position;
        bool accepted = game.Input(button, down, ReplayPoint(position));
        facePressed = down && game.CanPlay;
        if (!game.CanPlay)
        {
            buttons = MouseButtons.None;
            Capture = false;
        }
        InvalidatePress(before, PressedArea());
        if (wasPressing != Pressing && PressChanged != null)
            PressChanged(this, EventArgs.Empty);
        if (!accepted)
            return;

        Rectangle dirty = ChangedCells();
        if (!dirty.IsEmpty)
            Invalidate(dirty);
        if (Changed != null)
            Changed(this, EventArgs.Empty);
    }

    private void InvalidatePress(Rectangle before, Rectangle after)
    {
        if (before == after)
            return;
        Rectangle dirty = before.IsEmpty ? after : after.IsEmpty ? before : Rectangle.Union(before, after);
        Invalidate(dirty);
    }

    private Rectangle PressedArea()
    {
        if (game == null || !game.CanPlay || game.MouseVisual == 0)
            return Rectangle.Empty;
        int index = CellAt(pointer);
        if (index < 0)
            return Rectangle.Empty;
        int row = index / game.Columns;
        int column = index % game.Columns;
        int radius = game.MouseVisual == 2 ? 1 : 0;
        return CellArea(Math.Max(0, row - radius), Math.Max(0, column - radius),
            Math.Min(game.Rows - 1, row + radius), Math.Min(game.Columns - 1, column + radius));
    }

    private Rectangle ChangedCells()
    {
        int top = game.Rows, left = game.Columns, bottom = -1, right = -1;
        for (int row = 0; row < game.Rows; row++)
            for (int column = 0; column < game.Columns; column++)
            {
                int index = row * game.Columns + column;
                byte value = game.Display(index);
                if (visibleTiles[index] == value)
                    continue;
                visibleTiles[index] = value;
                top = Math.Min(top, row);
                left = Math.Min(left, column);
                bottom = Math.Max(bottom, row);
                right = Math.Max(right, column);
            }
        return bottom < 0 ? Rectangle.Empty : CellArea(top, left, bottom, right);
    }

    private Rectangle CellArea(int top, int left, int bottom, int right)
    {
        Rectangle board = BoardBounds;
        int size = TilePixels;
        return new Rectangle(board.X + left * size, board.Y + top * size,
            (right - left + 1) * size, (bottom - top + 1) * size);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        if (game == null)
            return;
        Rectangle area = BoardBounds;
        Rectangle clip = Rectangle.Intersect(area, e.ClipRectangle);
        if (!area.Contains(e.ClipRectangle))
            ClassicFrame.DrawBevel(e.Graphics, Rectangle.Inflate(area, Inset, Inset), Inset, false);
        if (clip.Width <= 0 || clip.Height <= 0)
            return;

        int size = TilePixels;
        int endRow = (clip.Bottom - area.Top + size - 1) / size;
        int endColumn = (clip.Right - area.Left + size - 1) / size;
        Rectangle active = PressedArea();
        for (int row = (clip.Top - area.Top) / size; row < endRow; row++)
            for (int column = (clip.Left - area.Left) / size; column < endColumn; column++)
            {
                var rect = new Rectangle(area.X + column * size, area.Y + row * size, size, size);
                byte value = visibleTiles[row * game.Columns + column];
                ClassicSprites.DrawCell(e.Graphics, rect, value == Game.Covered && active.Contains(rect) ? (byte)0 : value);
            }
    }
}
