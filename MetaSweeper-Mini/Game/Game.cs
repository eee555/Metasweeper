using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;

internal sealed class Game : IDisposable
{
    internal const byte Covered = 10, Flag = 11, WrongFlag = 14, HitMine = 15, Mine = 16;
    internal enum Phase { Ready, Playing, Won, Lost }

    private readonly NativeCore core;
    private readonly byte[] visible;
    private bool flagOnWin;
    private IntPtr handle;
    private GameStatus status;
    private byte[] replay;
    private string player = GameSettings.Anonymous;
    private string race = "";
    private string country = "";
    private Point? lastCursor;
    private ulong? startedAt;
    private ulong lastClockCheck;
    internal bool UsedCursorLimit { get; set; }
    internal bool TimingValid { get; private set; }

    [DllImport("kernel32.dll")]
    private static extern ulong GetTickCount64();

    internal readonly int Rows, Columns, Mines;
    internal Phase State { get { return (Phase)status.Phase; } }
    internal uint MouseVisual { get { return status.MouseVisual; } }
    internal bool CanPlay { get { return State == Phase.Ready || State == Phase.Playing; } }
    internal bool CanSaveReplay { get { return !CanPlay && TimingValid; } }
    internal int Remaining { get { return State == Phase.Won && flagOnWin ? 0 : Mines - (int)status.Flags; } }
    internal double ElapsedSeconds { get { return status.Seconds; } }
    internal long Seconds { get { return (long)status.Seconds; } }
    internal string PlayerIdentifier { get { return player; } }
    internal string CountryCode { get { return country; } }
    internal int Left { get { return (int)status.Left; } }
    internal int Right { get { return (int)status.Right; } }
    internal int Chords { get { return (int)status.Chords; } }
    internal double CursorPath { get { return status.Path; } }
    internal ReplayMetrics? Metrics { get; private set; }

    internal Game(NativeCore core, int rows, int columns, int mines, bool flagOnWin)
    {
        this.core = core;
        this.flagOnWin = flagOnWin;
        TimingValid = true;
        Rows = rows;
        Columns = columns;
        Mines = mines;
        visible = new byte[rows * columns];
        for (int index = 0; index < visible.Length; index++)
            visible[index] = Covered;
        handle = core.CreateGame(rows, columns, mines);
    }

    internal byte Display(int index) { return visible[index]; }

    internal void SetIdentity(string playerIdentifier, string raceIdentifier, string countryCode)
    {
        if (State != Phase.Ready)
            return;
        player = playerIdentifier;
        race = raceIdentifier;
        country = countryCode;
    }

    internal void SetFlagOnWin(bool enabled)
    {
        flagOnWin = enabled;
    }

    internal bool Input(MouseButtons button, bool down, Point position)
    {
        if (!CanPlay || (button != MouseButtons.Left && button != MouseButtons.Right))
            return false;
        uint code = button == MouseButtons.Left ? 0u : 2u;
        bool ready = State == Phase.Ready;
        ulong before = GetTickCount64();
        if (!core.Button(handle, code + (down ? 0u : 1u), position, flagOnWin, visible))
            return false;
        lastCursor = position;
        RefreshStatus();
        if (ready && State != Phase.Ready)
            startedAt = before;
        if (!CanPlay)
            CheckTiming(before, true);
        return true;
    }

    internal void TrackCursor(Point position)
    {
        if (CanPlay && lastCursor != position)
        {
            lastCursor = position;
            core.Move(handle, position);
        }
    }

    internal void RefreshStatus()
    {
        ulong sampledAt = GetTickCount64();
        status = core.ReadStatus(handle);
        if (State == Phase.Playing)
            CheckTiming(sampledAt, false);
        if (!CanPlay && !Metrics.HasValue)
            Metrics = core.ReadMetrics(handle);
    }

    private void CheckTiming(ulong sampledAt, bool terminal)
    {
        if (!startedAt.HasValue || !TimingValid)
            return;
        if (!terminal && sampledAt - lastClockCheck < 1000)
            return;
        lastClockCheck = sampledAt;
        TimingValid = Math.Abs(ElapsedSeconds * 1000 - (sampledAt - startedAt.Value)) <= 100;
    }

    internal byte[] GetReplay()
    {
        if (!CanSaveReplay)
            throw new InvalidOperationException(UiText.Get(TextId.ReplayTooEarly));
        if (replay == null)
            replay = ReplayChecksum.Sign(
                core.EncodeReplay(handle, player, race, country, UsedCursorLimit));
        return (byte[])replay.Clone();
    }

    public void Dispose()
    {
        if (handle == IntPtr.Zero)
            return;
        core.DestroyGame(handle);
        handle = IntPtr.Zero;
    }
}
