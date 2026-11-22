using System;
using System.Windows.Forms;

internal sealed class FaceButton : Button
{
    private Game.Phase state;
    private bool pressing;

    internal FaceButton()
    {
        AccessibleName = "新一局";
        Cursor = Cursors.Hand;
        BackColor = ClassicFrame.Canvas;
        TabStop = false;
        SetStyle(ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer, true);
    }

    internal void UpdateFace(Game.Phase phase, bool isPressing)
    {
        if (state == phase && pressing == isPressing)
            return;
        state = phase;
        pressing = isPressing;
        Invalidate();
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        int sprite = Capture ? 4 : state == Game.Phase.Won ? 3 : state == Game.Phase.Lost ? 2 : pressing ? 1 : 0;
        ClassicSprites.DrawFace(e.Graphics, ClientRectangle, sprite);
    }
}
