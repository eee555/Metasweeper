using System;
using System.Runtime.InteropServices;
using System.Windows.Forms;

[assembly: System.Runtime.Versioning.TargetFramework(".NETFramework,Version=v4.8")]
[assembly: DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
[assembly: System.Reflection.AssemblyTitle(Program.Name)]
[assembly: System.Reflection.AssemblyProduct(Program.Name)]

internal static class Program
{
    internal const string Name = "MetaSweeper-Mini";

    [DllImport("user32.dll")]
    private static extern bool SetProcessDPIAware();

    [DllImport("kernel32.dll")]
    private static extern IntPtr GetCurrentProcess();

    [DllImport("kernel32.dll")]
    private static extern bool SetPriorityClass(IntPtr process, uint priorityClass);

    // HIGH_PRIORITY_CLASS keeps the game ahead of ordinary background work without
    // starving the desktop compositor like a realtime class would.
    private const uint HighPriorityClass = 0x00000080;

    [STAThread]
    private static void Main(string[] args)
    {
        if (NativeCore.HandleCleanup(args))
            return;

        SetProcessDPIAware();
        SetPriorityClass(GetCurrentProcess(), HighPriorityClass);
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        try
        {
            using (var core = new NativeCore())
            using (var form = new GameWindow(core))
                Application.Run(form);
        }
        catch (Exception error)
        {
            MessageBox.Show("无法启动扫雷。\r\n" + error.Message, Name, MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
