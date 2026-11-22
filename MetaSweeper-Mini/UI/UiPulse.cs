using System;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32.SafeHandles;

internal sealed class UiPulse : IDisposable
{
    private int interval = IntervalForRefreshRate(60);
    private const uint HighResolution = 0x00000002;
    private const uint ModifyStateAndSynchronize = 0x00100002;
    private const uint KeyboardMouseOrPaint = 0x0027;

    [DllImport("user32.dll")]
    private static extern uint GetQueueStatus(uint flags);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern SafeWaitHandle CreateWaitableTimerExW(IntPtr attributes, string name, uint flags, uint access);

    [DllImport("kernel32.dll")]
    private static extern bool SetWaitableTimer(SafeWaitHandle timer, ref long dueTime, int period,
        IntPtr completion, IntPtr context, bool resume);

    [DllImport("kernel32.dll")]
    private static extern bool CancelWaitableTimer(SafeWaitHandle timer);

    private sealed class ClockHandle : WaitHandle
    {
        internal ClockHandle(SafeWaitHandle handle) { SafeWaitHandle = handle; }
    }

    private readonly Control owner;
    private readonly Action tick;
    private readonly System.Windows.Forms.Timer fallback;
    private readonly ClockHandle clock;
    private readonly ManualResetEvent stop;
    private readonly Thread worker;
    private readonly MethodInvoker deliver;
    private bool enabled;
    private volatile bool disposed;
    private int queued;

    internal UiPulse(Control owner, Action tick)
    {
        this.owner = owner;
        this.tick = tick;
        deliver = Deliver;
        fallback = new System.Windows.Forms.Timer { Interval = interval };
        fallback.Tick += (sender, args) => tick();

        SafeWaitHandle handle = CreateWaitableTimerExW(IntPtr.Zero, null, HighResolution, ModifyStateAndSynchronize);
        if (handle.IsInvalid)
        {
            handle.Dispose();
            return;
        }

        clock = new ClockHandle(handle);
        stop = new ManualResetEvent(false);
        worker = new Thread(Run) { IsBackground = true, Name = "Minesweeper display refresh" };
        worker.Start();
    }

    internal bool Enabled
    {
        get { return enabled; }
        set
        {
            if (disposed || enabled == value)
                return;
            enabled = value;
            if (!value)
            {
                fallback.Stop();
                if (clock != null)
                    CancelWaitableTimer(clock.SafeWaitHandle);
                return;
            }

            Arm();
        }
    }

    internal static int IntervalForRefreshRate(int refreshRate)
    {
        if (refreshRate <= 1)
            refreshRate = 60;
        return Math.Max(1, (int)Math.Round(1000.0 / refreshRate));
    }

    internal void UpdateRefreshRate(int refreshRate)
    {
        int target = IntervalForRefreshRate(refreshRate);
        if (disposed || interval == target)
            return;
        interval = target;
        fallback.Interval = interval;
        if (enabled)
            Arm();
    }

    private void Arm()
    {
        long due = -interval * 10000L;
        bool started = clock != null && SetWaitableTimer(clock.SafeWaitHandle, ref due, interval,
            IntPtr.Zero, IntPtr.Zero, false);
        if (!started && clock != null)
            CancelWaitableTimer(clock.SafeWaitHandle);
        fallback.Enabled = !started;
    }

    private void Run()
    {
        WaitHandle[] signals = { stop, clock };
        while (WaitHandle.WaitAny(signals) == 1)
        {
            // Keep at most one pending UI tick when painting or sizing takes longer.
            if (Interlocked.Exchange(ref queued, 1) != 0)
                continue;
            try { owner.BeginInvoke(deliver); }
            catch (InvalidOperationException) { Interlocked.Exchange(ref queued, 0); }
        }
    }

    private void Deliver()
    {
        try
        {
            // Posted timer callbacks otherwise run ahead of mouse and paint messages.
            if (enabled && !disposed && (GetQueueStatus(KeyboardMouseOrPaint) >> 16) == 0)
                tick();
        }
        finally
        {
            Interlocked.Exchange(ref queued, 0);
        }
    }

    public void Dispose()
    {
        if (disposed)
            return;
        Enabled = false;
        disposed = true;
        fallback.Dispose();
        if (worker == null)
            return;
        stop.Set();
        worker.Join();
        stop.Dispose();
        clock.Dispose();
    }
}
