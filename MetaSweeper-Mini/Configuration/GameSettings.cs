using System;
using System.Drawing;
using System.IO;

internal sealed class GameSettings
{
    private const string Common = "DEFAULT", Local = "WINFORMS";
    internal const string Anonymous = "匿名玩家";
    internal static readonly string[] PresetSections = { "BEGINNER", "INTERMEDIATE", "EXPERT" };
    private static readonly int[,] Defaults = { { 8, 8, 10 }, { 16, 16, 40 }, { 16, 30, 99 } };

    private readonly IniFile configuration;
    private readonly BoardPreset[] presets = new BoardPreset[PresetSections.Length];
    private readonly bool[] standardModes = new bool[PresetSections.Length];
    private readonly bool[] resized = new bool[PresetSections.Length];
    internal readonly string Root, ReplayDirectory;
    internal string Player { get; private set; }
    internal string Race { get; private set; }
    internal string Country { get; private set; }
    internal AutoSaveMode AutoSave { get; private set; }
    internal bool ShowCounter { get; private set; }
    internal Point? CounterPosition { get; private set; }
    internal readonly Point? MainPosition;
    internal readonly int InitialLevel;
    internal int CounterPixels { get; private set; }
    internal bool FlagOnWin { get; private set; }
    internal bool CursorLimit { get; private set; }

    internal GameSettings(string root, string replayDirectory = null)
    {
        Root = root;
        ReplayDirectory = replayDirectory ?? Path.Combine(root, "replay");
        bool exists = File.Exists(FilePath);
        configuration = new IniFile(FilePath);
        Player = CleanIdentifier(configuration.Read(Common, "player_identifier", Anonymous));
        if (Player.Length == 0)
            Player = Anonymous;
        Race = CleanIdentifier(configuration.Read(Common, "race_identifier", ""));
        Country = CleanIdentifier(configuration.Read(Common, "country", ""));
        AutoSave = !configuration.ReadBool(Common, "autosave_video", true) ? AutoSaveMode.Off
            : configuration.ReadBool(Local, "autosave_losses", !exists) ? AutoSaveMode.All : AutoSaveMode.Wins;
        ShowCounter = configuration.ReadBool(Local, "show_counter", true);
        CounterPosition = ReadPosition("scoreboardleft", "scoreboardtop");
        MainPosition = ReadPosition("mainwinleft", "mainwintop");
        FlagOnWin = configuration.ReadBool(Common, "end_then_flag", true);
        CursorLimit = configuration.ReadBool(Common, "cursor_limit", false);
        CounterPixels = ClampCounterPixels(configuration.ReadInt(Common, "scoreboard_pixsize", 27));

        for (int i = 0; i < presets.Length; i++)
        {
            presets[i] = ReadPreset(i);
            standardModes[i] = configuration.Read(PresetSections[i], "gamemode", "0").Trim() == "0";
        }
        int rows = configuration.ReadInt(Common, "row", presets[0].Rows);
        int columns = configuration.ReadInt(Common, "column", presets[0].Columns);
        int mines = configuration.ReadInt(Common, "minenum", presets[0].Mines);
        int initialLevel = 0;
        if (configuration.Read(Common, "gamemode", "0").Trim() == "0")
        {
            for (int i = 0; i < presets.Length; i++)
            {
                if (standardModes[i] && presets[i].Matches(rows, columns, mines))
                {
                    initialLevel = i;
                    break;
                }
            }
        }
        InitialLevel = initialLevel;

        if (!exists)
        {
            try
            {
                Directory.CreateDirectory(Root);
                WriteOwnedSettings(configuration);
                for (int i = 0; i < presets.Length; i++)
                    configuration.Set(PresetSections[i], "pixsize", presets[i].Pixels);
                configuration.Save();
            }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
        try
        {
            Directory.CreateDirectory(ReplayDirectory);
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }

    internal static GameSettings Load()
    {
        return new GameSettings(Directory.GetCurrentDirectory());
    }

    private string FilePath { get { return Path.Combine(Root, "gameSetting.ini"); } }
    internal BoardPreset Preset(int selected) { return presets[selected]; }

    private Point? ReadPosition(string x, string y)
    {
        int left = configuration.ReadInt(Common, x, int.MinValue);
        int top = configuration.ReadInt(Common, y, int.MinValue);
        return left == int.MinValue || top == int.MinValue ? (Point?)null : new Point(left, top);
    }

    private BoardPreset ReadPreset(int index)
    {
        int pixels = ClampPixels(configuration.ReadInt(PresetSections[index], "pixsize", 27));
        return new BoardPreset(Defaults[index, 0], Defaults[index, 1], Defaults[index, 2], pixels);
    }

    private static int ClampPixels(int pixels)
    {
        return Math.Max(10, Math.Min(256, pixels));
    }

    private static int ClampCounterPixels(int pixels)
    {
        return Math.Max(12, Math.Min(48, pixels));
    }

    internal void Store(string player, string race, string country, AutoSaveMode autoSave,
        bool showCounter, bool cursorLimit, bool flagOnWin, int counterPixels)
    {
        player = CleanIdentifier(player);
        race = CleanIdentifier(race);
        if (player.Length == 0)
            player = Anonymous;
        country = CleanIdentifier(country);
        counterPixels = ClampCounterPixels(counterPixels);

        var ini = new IniFile(FilePath);
        SetGeneral(ini, player, race, country, autoSave, showCounter);
        ini.Set(Common, "end_then_flag", flagOnWin);
        ini.Set(Common, "cursor_limit", cursorLimit);
        ini.Set(Common, "scoreboard_pixsize", counterPixels);
        ini.Save();

        Player = player;
        Race = race;
        Country = country;
        AutoSave = autoSave;
        ShowCounter = showCounter;
        CursorLimit = cursorLimit;
        FlagOnWin = flagOnWin;
        CounterPixels = counterPixels;
    }

    internal void StoreCounterVisibility(bool visible)
    {
        var ini = new IniFile(FilePath);
        ini.Set(Local, "show_counter", visible);
        ini.Save();
        ShowCounter = visible;
    }

    internal void RememberPresetSize(int level, int pixels)
    {
        pixels = ClampPixels(pixels);
        if (presets[level].Pixels != pixels)
        {
            presets[level].Pixels = pixels;
            resized[level] = true;
        }
    }

    internal void StoreCounterPosition(Point position)
    {
        CounterPosition = position;
        var ini = new IniFile(FilePath);
        ini.Set(Common, "scoreboardleft", position.X);
        ini.Set(Common, "scoreboardtop", position.Y);
        ini.Save();
    }

    internal void StoreWindow(Point position, BoardPreset board)
    {
        var ini = new IniFile(FilePath);
        ini.Set(Common, "mainwinleft", position.X);
        ini.Set(Common, "mainwintop", position.Y);
        SetBoard(ini, board);
        for (int i = 0; i < presets.Length; i++)
            if (resized[i])
                ini.Set(PresetSections[i], "pixsize", presets[i].Pixels);
        ini.Save();
    }

    private void WriteOwnedSettings(IniFile ini)
    {
        SetGeneral(ini, Player, Race, Country, AutoSave, ShowCounter);
        SetBoard(ini, presets[InitialLevel]);
        ini.Set(Common, "end_then_flag", FlagOnWin);
        ini.Set(Common, "cursor_limit", CursorLimit);
        ini.Set(Common, "scoreboard_pixsize", CounterPixels);
    }

    private static void SetGeneral(IniFile ini, string player, string race, string country, AutoSaveMode autoSave, bool showCounter)
    {
        ini.Set(Common, "player_identifier", player);
        ini.Set(Common, "race_identifier", race);
        ini.Set(Common, "country", country);
        ini.Set(Common, "autosave_video", autoSave != AutoSaveMode.Off);
        ini.Set(Local, "autosave_losses", autoSave == AutoSaveMode.All);
        ini.Set(Local, "show_counter", showCounter);
    }

    private static void SetBoard(IniFile ini, BoardPreset board)
    {
        ini.Set(Common, "row", board.Rows);
        ini.Set(Common, "column", board.Columns);
        ini.Set(Common, "minenum", board.Mines);
    }

    private static string CleanIdentifier(string value)
    {
        value = value.Replace("\0", "").Replace("\r", "").Replace("\n", "").Trim();
        return value.Length > 128 ? value.Substring(0, char.IsHighSurrogate(value[127]) ? 127 : 128) : value;
    }
}
