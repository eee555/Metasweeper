using System;
using System.Drawing;
using System.Runtime.InteropServices;

internal sealed class CursorLock
{
    [StructLayout(LayoutKind.Sequential)]
    private struct Rect { internal int Left, Top, Right, Bottom; }

    [DllImport("user32.dll", EntryPoint = "ClipCursor", ExactSpelling = true)]
    private static extern bool Clip(ref Rect bounds);

    [DllImport("user32.dll", EntryPoint = "ClipCursor", ExactSpelling = true)]
    private static extern bool Clip(IntPtr bounds);

    [DllImport("user32.dll")]
    internal static extern IntPtr GetForegroundWindow();

    private Rectangle applied;

    internal bool Apply(Rectangle bounds)
    {
        if (bounds.Width <= 0 || bounds.Height <= 0)
        {
            Release();
            return false;
        }
        if (bounds == applied)
            return true;
        var rect = new Rect { Left = bounds.Left, Top = bounds.Top, Right = bounds.Right, Bottom = bounds.Bottom };
        if (!Clip(ref rect))
        {
            Release();
            return false;
        }
        applied = bounds;
        return true;
    }

    internal void Release()
    {
        if (applied.IsEmpty)
            return;
        Clip(IntPtr.Zero);
        applied = Rectangle.Empty;
    }
}
