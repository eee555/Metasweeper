internal static class ShortcutCatalog
{
    internal static readonly string[,] Defaults = {
        { "restart", "F2" },
        { "menu_new_game", "N" },
        { "preset_beginner", "1" },
        { "menu_beginner", "B" },
        { "preset_intermediate", "2" },
        { "menu_intermediate", "I" },
        { "preset_expert", "3" },
        { "menu_expert", "E" },
        { "toggle_counter", "/" },
        { "toggle_identity", "Ctrl+I" },
        { "menu_save", "Ctrl+S" },
        { "menu_open_replay", "W" },
        { "menu_settings", "S" },
        { "menu_quit", "Ctrl+X" },
        { "menu_keybindings", "Z" }
    };

    internal static int Count
    {
        get { return Defaults.GetLength(0); }
    }

    internal static string Id(int index)
    {
        return Defaults[index, 0];
    }

    internal static string DefaultKey(int index)
    {
        return Defaults[index, 1];
    }

    internal static string Key(string id)
    {
        for (int i = 0; i < Count; i++)
            if (Defaults[i, 0] == id)
                return Defaults[i, 1];
        return "";
    }
}
