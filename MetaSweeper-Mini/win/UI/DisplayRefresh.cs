using System.Runtime.InteropServices;

internal static class DisplayRefresh
{
    // DEVMODEW has a fixed layout shared by Windows architectures.
    [StructLayout(LayoutKind.Explicit, Size = 220)]
    private struct DisplayMode
    {
        [FieldOffset(68)] internal ushort Size;
        [FieldOffset(184)] internal int Frequency;
    }

    [DllImport("user32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern bool EnumDisplaySettingsW(string device, int mode, ref DisplayMode settings);

    internal static int Read(string device)
    {
        var mode = new DisplayMode { Size = (ushort)Marshal.SizeOf(typeof(DisplayMode)) };
        return EnumDisplaySettingsW(device, -1, ref mode) && mode.Frequency > 1 ? mode.Frequency : 60;
    }
}
