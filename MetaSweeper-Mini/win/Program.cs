using System;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Windows.Forms;

[assembly: System.Runtime.Versioning.TargetFramework(".NETFramework,Version=v4.8")]
[assembly: DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
[assembly: System.Reflection.AssemblyTitle(Program.Name)]
[assembly: System.Reflection.AssemblyProduct(Program.Name)]
[assembly: System.Reflection.AssemblyFileVersion("3.4.0.0")]
[assembly: System.Reflection.AssemblyInformationalVersion("3.4.0")]

internal static class Program
{
    internal const string Name = "MetaSweeper-Mini";

    [DllImport("user32.dll")]
    private static extern bool SetProcessDPIAware();

    [DllImport("user32.dll")]
    private static extern bool SetProcessDpiAwarenessContext(IntPtr context);

    [DllImport("kernel32.dll")]
    private static extern IntPtr GetCurrentProcess();

    [DllImport("kernel32.dll")]
    private static extern bool SetPriorityClass(IntPtr process, uint priorityClass);

    private const uint HighPriorityClass = 0x00000080;
    private const uint RealtimePriorityClass = 0x00000100;

    [STAThread]
    private static void Main(string[] args)
    {
        if (NativeCore.HandleCleanup(args))
            return;

        ConfigureDpiAwareness();
        // Realtime is available only to elevated sessions. Keep the High fallback
        // because policy, sandboxing, or a filtered token can still reject it.
        uint priority = IsAdministrator() ? RealtimePriorityClass : HighPriorityClass;
        if (!SetPriorityClass(GetCurrentProcess(), priority))
            SetPriorityClass(GetCurrentProcess(), HighPriorityClass);
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        try
        {
            GameSettings settings = GameSettings.Load();
            UiText.SetLanguage(settings.Language);
            using (var core = new NativeCore())
            using (var form = new GameWindow(core, settings))
                Application.Run(form);
        }
        catch (Exception error)
        {
            MessageBox.Show(UiText.Get(TextId.StartupError) + "\r\n" + error.Message,
                UiText.Get(TextId.Title), MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private static void ConfigureDpiAwareness()
    {
        try
        {
            // Keep Windows from stretching the board when the window crosses monitors.
            if (SetProcessDpiAwarenessContext(new IntPtr(-4))) // Per-monitor V2
                return;
        }
        catch (EntryPointNotFoundException) { }
        SetProcessDPIAware();
    }

    private static bool IsAdministrator()
    {
        using (WindowsIdentity identity = WindowsIdentity.GetCurrent())
            return new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator);
    }
}
