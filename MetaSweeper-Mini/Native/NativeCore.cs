using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

internal sealed class NativeCore : IDisposable
{
    internal const int CellPixels = 16;
    private const string TemporaryPrefix = "WinFormsMines-";
    private const string TemporaryLibrary = "mines_core.dll";
    private const string CleanupArgument = "--cleanup-native-core";

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate IntPtr NewGameFn(UIntPtr rows, UIntPtr columns, UIntPtr mines);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate void FreeGameFn(IntPtr game);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate uint ButtonFn(IntPtr game, uint button, UIntPtr x, UIntPtr y, uint flagOnWin, [Out] byte[] cells);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate void MoveFn(IntPtr game, UIntPtr x, UIntPtr y);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate void StatusFn(IntPtr game, out GameStatus status);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate uint MetricsFn(IntPtr game, out ReplayMetrics metrics);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate IntPtr EncodeReplayFn(IntPtr game, [In] byte[] identifiers, UIntPtr identifiersLength, uint usedCursorLimit, out UIntPtr length);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate void FreeReplayFn(IntPtr bytes, UIntPtr length);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
    private static extern IntPtr LoadLibraryExW(string path, IntPtr reserved, uint flags);

    [DllImport("kernel32.dll", ExactSpelling = true, SetLastError = true)]
    private static extern IntPtr GetProcAddress(IntPtr module, string name);

    [DllImport("kernel32.dll", ExactSpelling = true)]
    private static extern bool FreeLibrary(IntPtr module);

    [DllImport("cabinet.dll", SetLastError = true)]
    private static extern bool CreateDecompressor(uint algorithm, IntPtr allocation, out IntPtr decompressor);

    [DllImport("cabinet.dll", SetLastError = true)]
    private static extern bool Decompress(IntPtr decompressor, byte[] input, UIntPtr inputSize,
        [Out] byte[] output, UIntPtr outputSize, out UIntPtr written);

    [DllImport("cabinet.dll")]
    private static extern bool CloseDecompressor(IntPtr decompressor);

    private readonly Guid ticket = Guid.NewGuid();
    private readonly string directory;
    private IntPtr module;
    private bool mayHaveWorker;
    private readonly NewGameFn newGame;
    private readonly FreeGameFn freeGame;
    private readonly ButtonFn click;
    private readonly MoveFn move;
    private readonly StatusFn status;
    private readonly MetricsFn metrics;
    private readonly EncodeReplayFn encodeReplay;
    private readonly FreeReplayFn freeReplay;

    internal NativeCore()
    {
        directory = TemporaryDirectory(ticket);
        string path = Path.Combine(directory, TemporaryLibrary);
        Directory.CreateDirectory(directory);
        try
        {
            using (var output = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                WriteNativeLibrary(output);

            const uint LoadLibrarySearchSystem32 = 0x800;
            module = LoadLibraryExW(path, IntPtr.Zero, LoadLibrarySearchSystem32);
            if (module == IntPtr.Zero)
                throw new Win32Exception(Marshal.GetLastWin32Error());
            newGame = (NewGameFn)GetFunction("new_game", typeof(NewGameFn));
            freeGame = (FreeGameFn)GetFunction("free_game", typeof(FreeGameFn));
            click = (ButtonFn)GetFunction("game_button", typeof(ButtonFn));
            move = (MoveFn)GetFunction("game_move", typeof(MoveFn));
            status = (StatusFn)GetFunction("game_status", typeof(StatusFn));
            metrics = (MetricsFn)GetFunction("game_metrics", typeof(MetricsFn));
            encodeReplay = (EncodeReplayFn)GetFunction("encode_replay", typeof(EncodeReplayFn));
            freeReplay = (FreeReplayFn)GetFunction("free_replay", typeof(FreeReplayFn));
        }
        catch
        {
            Dispose();
            throw;
        }
    }

    private static void WriteNativeLibrary(Stream destination)
    {
        const uint Lzms = 5;
        using (var resource = typeof(NativeCore).Assembly.GetManifestResourceStream("mines_core.lzms"))
        using (var packed = new BinaryReader(resource))
        {
            byte[] bytes = new byte[packed.ReadInt32()];
            byte[] compressed = packed.ReadBytes(checked((int)(resource.Length - resource.Position)));
            IntPtr handle;
            if (!CreateDecompressor(Lzms, IntPtr.Zero, out handle))
                throw new Win32Exception(Marshal.GetLastWin32Error());
            try
            {
                UIntPtr written;
                if (!Decompress(handle, compressed, Size(compressed.Length), bytes, Size(bytes.Length), out written))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                if (written.ToUInt64() != (ulong)bytes.Length)
                    throw new InvalidDataException("内嵌扫雷库的大小不正确。");
                destination.Write(bytes, 0, bytes.Length);
            }
            finally
            {
                CloseDecompressor(handle);
            }
        }
    }

    private Delegate GetFunction(string name, Type signature)
    {
        IntPtr address = GetProcAddress(module, name);
        if (address == IntPtr.Zero)
            throw new Win32Exception(Marshal.GetLastWin32Error());
        return Marshal.GetDelegateForFunctionPointer(address, signature);
    }

    private static UIntPtr Size(int value) { return new UIntPtr((uint)value); }

    internal IntPtr CreateGame(int rows, int columns, int mines) { return newGame(Size(rows), Size(columns), Size(mines)); }
    internal void DestroyGame(IntPtr game) { freeGame(game); }

    internal bool Button(IntPtr game, uint button, Point position, bool flagOnWin, byte[] cells)
    {
        if (button == 1)
            mayHaveWorker = true;
        return click(game, button, Size(position.X), Size(position.Y), flagOnWin ? 1u : 0u, cells) != 0;
    }

    internal void Move(IntPtr game, Point position)
    {
        move(game, Size(position.X), Size(position.Y));
    }

    internal GameStatus ReadStatus(IntPtr game)
    {
        GameStatus current;
        status(game, out current);
        return current;
    }

    internal ReplayMetrics? ReadMetrics(IntPtr game)
    {
        ReplayMetrics current;
        return metrics(game, out current) == 0 ? (ReplayMetrics?)null : current;
    }

    internal byte[] EncodeReplay(IntPtr game, string player, string race, string country, bool usedCursorLimit)
    {
        byte[] identifiers = Encoding.UTF8.GetBytes(player + "\0" + race + "\0" + country);
        UIntPtr length;
        IntPtr nativeBytes = encodeReplay(game, identifiers, Size(identifiers.Length), usedCursorLimit ? 1u : 0u, out length);
        if (nativeBytes == IntPtr.Zero)
            throw new InvalidDataException("这一局的录像数据不可用。");

        try
        {
            byte[] bytes = new byte[checked((int)length.ToUInt64())];
            Marshal.Copy(nativeBytes, bytes, 0, bytes.Length);
            return bytes;
        }
        finally
        {
            freeReplay(nativeBytes, length);
        }
    }

    public void Dispose()
    {
        if (module != IntPtr.Zero && mayHaveWorker)
        {
            // ms_toollib owns detached workers. Keep their DLL mapped until the game process exits.
            module = IntPtr.Zero;
            try
            {
                using (var current = Process.GetCurrentProcess())
                using (Process.Start(new ProcessStartInfo(Application.ExecutablePath,
                    CleanupArgument + " " + ticket.ToString("N") + " " + current.Id)
                {
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    WindowStyle = ProcessWindowStyle.Hidden
                }))
                { }
            }
            catch (Win32Exception) { }
            return;
        }
        if (module != IntPtr.Zero)
        {
            FreeLibrary(module);
            module = IntPtr.Zero;
        }
        RemoveTemporaryDirectory(directory);
    }

    internal static bool HandleCleanup(string[] args)
    {
        if (args.Length == 0 || args[0] != CleanupArgument)
            return false;
        Guid tag;
        int parent;
        if (args.Length != 3 || !Guid.TryParseExact(args[1], "N", out tag)
            || !int.TryParse(args[2], out parent) || parent <= 0)
            return true;

        try
        {
            using (var process = Process.GetProcessById(parent))
                process.WaitForExit(5000);
        }
        catch (ArgumentException) { }
        catch (Win32Exception) { }

        string path = TemporaryDirectory(tag);
        for (int attempt = 0; attempt < 25 && !RemoveTemporaryDirectory(path); attempt++)
            Thread.Sleep(80);
        return true;
    }

    private static string TemporaryDirectory(Guid tag)
    {
        return Path.Combine(Path.GetTempPath(), TemporaryPrefix + tag.ToString("N"));
    }

    private static bool RemoveTemporaryDirectory(string path)
    {
        try
        {
            if (!Directory.Exists(path))
                return true;
            File.Delete(Path.Combine(path, TemporaryLibrary));
            Directory.Delete(path);
            return true;
        }
        catch (IOException) { return false; }
        catch (UnauthorizedAccessException) { return false; }
    }
}
