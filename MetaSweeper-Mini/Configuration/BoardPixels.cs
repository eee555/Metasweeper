using System;

internal static class BoardPixels
{
    internal const int Minimum = 5;
    internal const int Maximum = 255;

    internal static int Clamp(int value)
    {
        return Math.Max(Minimum, Math.Min(Maximum, value));
    }
}
