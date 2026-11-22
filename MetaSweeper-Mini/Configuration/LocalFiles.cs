using System;
using System.IO;

internal static class LocalFiles
{
    internal static void Write(string path, byte[] data)
    {
        Write(path, data, true);
    }

    internal static bool TryWriteNew(string path, byte[] data)
    {
        return Write(path, data, false);
    }

    private static bool Write(string path, byte[] data, bool replaceExisting)
    {
        string temporary = Path.Combine(Path.GetDirectoryName(path), "." + Guid.NewGuid().ToString("N") + ".tmp");
        try
        {
            using (var file = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                file.Write(data, 0, data.Length);
            if (replaceExisting && File.Exists(path))
                File.Replace(temporary, path, null);
            else
            {
                try { File.Move(temporary, path); }
                catch (IOException)
                {
                    if (!replaceExisting && File.Exists(path))
                        return false;
                    throw;
                }
            }
            return true;
        }
        finally
        {
            if (File.Exists(temporary))
                File.Delete(temporary);
        }
    }
}
