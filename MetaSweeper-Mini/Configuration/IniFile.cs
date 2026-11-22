using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;

internal sealed class IniFile
{
    private readonly string path;
    private readonly List<string> lines;

    internal IniFile(string path)
    {
        this.path = path;
        try { lines = new List<string>(File.ReadAllLines(path, Encoding.UTF8)); }
        catch (FileNotFoundException) { lines = new List<string>(); }
        catch (DirectoryNotFoundException) { lines = new List<string>(); }
    }

    internal string Read(string section, string key, string fallback = null)
    {
        int end;
        int index = Locate(section, key, out end);
        if (index < 0)
            return fallback;
        int split = lines[index].IndexOfAny(new[] { '=', ':' });
        return lines[index].Substring(split + 1).Trim();
    }

    internal int ReadInt(string section, string key, int fallback)
    {
        int value;
        return int.TryParse(Read(section, key), NumberStyles.Integer, CultureInfo.InvariantCulture, out value)
            ? value : fallback;
    }

    internal bool ReadBool(string section, string key, bool fallback)
    {
        string value = Read(section, key, "").ToLowerInvariant();
        switch (value)
        {
            case "1": case "true": case "on": case "yes": return true;
            case "0": case "false": case "off": case "no": return false;
            default: return fallback;
        }
    }

    internal void Set(string section, string key, object value)
    {
        int end;
        int index = Locate(section, key, out end);
        string line = key + " = " + Convert.ToString(value, CultureInfo.InvariantCulture);
        if (index >= 0)
        {
            lines[index] = line;
            return;
        }
        if (end < 0)
        {
            if (lines.Count != 0 && lines[lines.Count - 1].Length != 0)
                lines.Add("");
            lines.Add("[" + section + "]");
            end = lines.Count;
        }
        while (end > 0 && lines[end - 1].Length == 0)
            end--;
        lines.Insert(end, line);
    }

    private int Locate(string section, string key, out int end)
    {
        string current = "";
        int found = -1;
        end = section.Length == 0 ? 0 : -1;
        for (int n = 0; n < lines.Count; n++)
        {
            string text = lines[n].Trim();
            if (text.StartsWith("[", StringComparison.Ordinal))
            {
                int close = text.IndexOf(']');
                if (close > 0)
                    current = text.Substring(1, close - 1).Trim();
            }
            if (!string.Equals(current, section, StringComparison.OrdinalIgnoreCase))
                continue;

            end = n + 1;
            if (text.Length == 0 || text[0] == ';' || text[0] == '#' || text[0] == '[')
                continue;
            int split = text.IndexOfAny(new[] { '=', ':' });
            if (split > 0 && string.Equals(text.Substring(0, split).Trim(), key, StringComparison.OrdinalIgnoreCase))
                found = n;
        }
        return found;
    }

    internal void Save()
    {
        LocalFiles.Write(path, Encoding.UTF8.GetBytes(string.Join(Environment.NewLine, lines) + Environment.NewLine));
    }
}
