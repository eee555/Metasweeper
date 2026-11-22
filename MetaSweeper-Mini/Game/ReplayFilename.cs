using System;
using System.Globalization;
using System.IO;
using System.Text;

internal static class ReplayFilename
{
    internal static string Create(int level, double seconds, int bbbv,
        double bbbvPerSecond, string player, bool failed)
    {
        string prefix;
        switch (level)
        {
            case 0: prefix = "b_"; break;
            case 1: prefix = "i_"; break;
            case 2: prefix = "e_"; break;
            default: prefix = "c_"; break;
        }

        string name = prefix + "0_" + Format(seconds) + "_" + bbbv + "_"
            + Format(bbbvPerSecond) + "_" + SafeIdentifier(player);
        if (failed)
            name += "_fail";
        return name;
    }

    internal static string UniquePath(string directory, string baseName)
    {
        string path = Path.Combine(directory, baseName + ".evf");
        if (!File.Exists(path))
            return path;
        for (int index = 2; ; index++)
        {
            path = Path.Combine(directory, baseName + "(" + index + ").evf");
            if (!File.Exists(path))
                return path;
        }
    }

    internal static string SafeIdentifier(string value)
    {
        if (value == null)
            value = "";
        var invalid = Path.GetInvalidFileNameChars();
        var result = new StringBuilder(value.Length);
        foreach (char character in value)
        {
            if (char.IsControl(character) || Array.IndexOf(invalid, character) >= 0)
                result.Append('_');
            else
                result.Append(character);
        }
        return result.ToString().Trim().TrimEnd('.');
    }

    private static string Format(double value)
    {
        if (double.IsNaN(value))
            return "nan";
        if (double.IsPositiveInfinity(value))
            return "inf";
        if (double.IsNegativeInfinity(value))
            return "-inf";
        return value.ToString("0.000", CultureInfo.InvariantCulture);
    }
}
