using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;

internal static class Countries
{
    private static readonly Dictionary<string, string> Codes = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    internal static readonly string[] Names;

    static Countries()
    {
        var names = new List<string>();
        var seen = new Dictionary<string, string>(StringComparer.Ordinal);
        using (var resource = typeof(Countries).Assembly.GetManifestResourceStream("countries.deflate"))
        using (var compressed = new DeflateStream(resource, CompressionMode.Decompress))
        using (var table = new StreamReader(compressed))
        {
            for (string line = table.ReadLine(); line != null; line = table.ReadLine())
            {
                string code = line.Substring(0, 2);
                string name = line.Substring(3);
                Codes[name] = code;
                if (!seen.ContainsKey(code))
                {
                    seen.Add(code, name);
                    names.Add(name);
                }
            }
        }
        names.Sort(StringComparer.CurrentCultureIgnoreCase);
        Names = names.ToArray();
    }

    internal static string Code(string value)
    {
        value = value.Trim();
        if (value.Length == 2)
        {
            string upper = value.ToUpperInvariant();
            if (upper[0] >= 'A' && upper[0] <= 'Z' && upper[1] >= 'A' && upper[1] <= 'Z')
                return upper == "XX" ? "" : upper;
        }

        string code;
        return Codes.TryGetValue(value, out code) && code != "XX" ? code : "";
    }
}
