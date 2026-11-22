using System.Runtime.InteropServices;

[StructLayout(LayoutKind.Sequential)]
internal struct GameStatus
{
    internal double Seconds, Path;
    internal uint Phase, Left, Right, Chords, Flags, MouseVisual;
}
[StructLayout(LayoutKind.Sequential)]
internal struct ReplayMetrics
{
    internal double EstimatedTime, Speed, Stnb, Ioe, Thrp, Corr, Pluck;
    internal uint Solved, Total, Zini, Openings, Islands;
}
