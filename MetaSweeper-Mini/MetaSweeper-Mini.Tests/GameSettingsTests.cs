using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using Xunit;

public sealed class GameSettingsTests : IDisposable
{
    private readonly string root = Path.Combine(Path.GetTempPath(), "MetaSweeper-Mini.Tests", Guid.NewGuid().ToString("N"));

    public GameSettingsTests()
    {
        Directory.CreateDirectory(root);
    }

    public void Dispose()
    {
        if (Directory.Exists(root))
            Directory.Delete(root, true);
    }

    [Fact]
    public void NewConfigurationContainsOnlyOwnedKeys()
    {
        var settings = new GameSettings(root);
        Assert.True(settings.ShowIdentity);
        Assert.Equal("zh_CN", settings.Language);

        Dictionary<string, List<string>> sections = ReadSections(File.ReadAllText(Path.Combine(root, "gameSetting.ini")));
        Assert.Equal(new[] { "DEFAULT", "WINFORMS", "BEGINNER", "INTERMEDIATE", "EXPERT" }, sections.Keys.ToArray());
        Assert.Equal(new[] {
            "player_identifier", "race_identifier", "country", "autosave_video", "row", "column",
            "minenum", "end_then_flag", "cursor_limit", "scoreboard_pixsize", "language"
        }, sections["DEFAULT"].ToArray());
        Assert.Equal(new[] { "autosave_losses", "show_counter", "show_identity" }, sections["WINFORMS"].ToArray());
        Assert.Equal(new[] { "pixsize" }, sections["BEGINNER"].ToArray());
        Assert.Equal(new[] { "pixsize" }, sections["INTERMEDIATE"].ToArray());
        Assert.Equal(new[] { "pixsize" }, sections["EXPERT"].ToArray());
    }

    [Fact]
    public void AutomaticWriteDoesNotReplaceAnExistingReplay()
    {
        string path = Path.Combine(root, "game.evf");
        Assert.True(LocalFiles.TryWriteNew(path, new byte[] { 1, 2 }));
        Assert.False(LocalFiles.TryWriteNew(path, new byte[] { 3, 4 }));
        Assert.Equal(new byte[] { 1, 2 }, File.ReadAllBytes(path));
        Assert.Single(Directory.GetFiles(root));
    }

    [Fact]
    public void ShortcutBindingsAreFixedAndUnique()
    {
        var ids = new HashSet<string>(StringComparer.Ordinal);
        var keys = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        for (int i = 0; i < ShortcutCatalog.Count; i++)
        {
            Assert.True(ids.Add(ShortcutCatalog.Id(i)));
            Assert.True(keys.Add(ShortcutCatalog.DefaultKey(i)));
            Assert.Equal(ShortcutCatalog.DefaultKey(i), ShortcutCatalog.Key(ShortcutCatalog.Id(i)));
        }
        Assert.Equal("", ShortcutCatalog.Key("unknown"));
        Assert.Equal("Ctrl+I", ShortcutCatalog.Key("toggle_identity"));
    }

    [Fact]
    public void ReadsCompatibleMetaSweeperConfiguration()
    {
        WriteConfiguration(
            "[DEFAULT]",
            "player_identifier = [live]Tester",
            "race_identifier = Race-42",
            "country = China",
            "autosave_video = True",
            "row = 16",
            "column = 16",
            "minenum = 40",
            "end_then_flag = False",
            "cursor_limit = True",
            "scoreboard_pixsize = 34",
            "mainwinleft = 120",
            "mainwintop = 140",
            "scoreboardleft = 70",
            "scoreboardtop = 90",
            "[BEGINNER]",
            "pixsize = 20",
            "row = 99",
            "column = 99",
            "mine_num = 99",
            "gamemode = 7",
            "[INTERMEDIATE]",
            "pixsize = 30",
            "[EXPERT]",
            "pixsize = 40",
            "[KEYBINDINGS]",
            "restart = Ctrl+R",
            "[PLUGIN]",
            "untouched = yes");

        var settings = new GameSettings(root);

        Assert.Equal("[live]Tester", settings.Player);
        Assert.Equal("Race-42", settings.Race);
        Assert.Equal("China", settings.Country);
        Assert.Equal(AutoSaveMode.Wins, settings.AutoSave);
        Assert.False(settings.FlagOnWin);
        Assert.True(settings.CursorLimit);
        Assert.Equal(34, settings.CounterPixels);
        Assert.Equal(1, settings.InitialLevel);
        Assert.Equal(new Point(120, 140), settings.MainPosition);
        Assert.Equal(new Point(70, 90), settings.CounterPosition);
        Assert.Equal(20, settings.Preset(0).Pixels);
        Assert.True(settings.Preset(0).Matches(8, 8, 10));
        Assert.Equal(30, settings.Preset(1).Pixels);
        Assert.True(settings.Preset(1).Matches(16, 16, 40));
        Assert.Equal(40, settings.Preset(2).Pixels);
        Assert.True(settings.Preset(2).Matches(16, 30, 99));
    }

    [Theory]
    [InlineData("True", "False", (int)AutoSaveMode.Wins)]
    [InlineData("True", "True", (int)AutoSaveMode.All)]
    [InlineData("False", "True", (int)AutoSaveMode.Off)]
    public void AutosaveCompatibilityCombinesMetaSweeperAndMiniKeys(
        string autosaveVideo, string autosaveLosses, int expected)
    {
        WriteConfiguration(
            "[DEFAULT]",
            "autosave_video = " + autosaveVideo,
            "[WINFORMS]",
            "autosave_losses = " + autosaveLosses);

        Assert.Equal((AutoSaveMode)expected, new GameSettings(root).AutoSave);
    }

    [Fact]
    public void StoreUpdatesOwnedSettingsAndPreservesForeignKeys()
    {
        WriteConfiguration(
            "[DEFAULT]",
            "player_identifier = old",
            "[PLUGIN]",
            "untouched = yes");
        var settings = new GameSettings(root);

        settings.Store("New Player", "New Race", "China", AutoSaveMode.All,
            false, true, false, 40, false, "DE_de");

        Assert.Equal("New Player", settings.Player);
        Assert.Equal("New Race", settings.Race);
        Assert.Equal("China", settings.Country);
        Assert.Equal(AutoSaveMode.All, settings.AutoSave);
        Assert.False(settings.ShowCounter);
        Assert.False(settings.ShowIdentity);
        Assert.Equal("de_DE", settings.Language);
        Assert.True(settings.CursorLimit);
        Assert.False(settings.FlagOnWin);
        Assert.Equal(40, settings.CounterPixels);

        string text = File.ReadAllText(Path.Combine(root, "gameSetting.ini"));
        Assert.Contains("untouched = yes", text);
        Assert.Contains("autosave_video = True", text);
        Assert.Contains("autosave_losses = True", text);

        var reloaded = new GameSettings(root);
        Assert.Equal(AutoSaveMode.All, reloaded.AutoSave);
        Assert.False(reloaded.ShowCounter);
        Assert.False(reloaded.ShowIdentity);
        Assert.Equal("de_DE", reloaded.Language);
        Assert.True(reloaded.CursorLimit);
        Assert.False(reloaded.FlagOnWin);
        Assert.Equal(40, reloaded.CounterPixels);
    }

    [Theory]
    [InlineData("zh_CN", "zh_CN")]
    [InlineData("en_US", "en_US")]
    [InlineData("de_DE", "de_DE")]
    [InlineData("pl_PL", "pl_PL")]
    [InlineData("ja_JP", "ja_JP")]
    [InlineData("es_ES", "zh_CN")]
    [InlineData("", "zh_CN")]
    public void ReadsOriginalLanguageCodesWithChineseFallback(string configured, string expected)
    {
        WriteConfiguration("[DEFAULT]", "language = " + configured);
        Assert.Equal(expected, new GameSettings(root).Language);
    }

    [Fact]
    public void IdentityVisibilityPersistsWithoutChangingLanguageOrPlayer()
    {
        WriteConfiguration("[DEFAULT]", "language = ja_JP", "player_identifier = Test Player");
        var settings = new GameSettings(root);
        Assert.True(settings.ShowIdentity);

        settings.StoreIdentityVisibility(false);
        Assert.False(settings.ShowIdentity);
        var reloaded = new GameSettings(root);
        Assert.False(reloaded.ShowIdentity);
        Assert.Equal("ja_JP", reloaded.Language);
        Assert.Equal("Test Player", reloaded.Player);

        reloaded.StoreIdentityVisibility(true);
        Assert.True(new GameSettings(root).ShowIdentity);
    }

    [Fact]
    public void EverySupportedLanguageHasAllUiStrings()
    {
        try
        {
            var gameMenuNames = new HashSet<string>(StringComparer.Ordinal);
            for (int index = 0; index < UiText.LanguageNames.Length; index++)
            {
                string code = UiText.LanguageCode(index);
                Assert.Equal(index, UiText.LanguageIndex(code));
                UiText.SetLanguage(code);
                foreach (TextId id in Enum.GetValues(typeof(TextId)))
                    Assert.False(string.IsNullOrWhiteSpace(UiText.Get(id)));
                Assert.True(gameMenuNames.Add(UiText.Get(TextId.GameMenu)));
                string status = string.Format(UiText.Get(TextId.DisplayStatus), 123, 456);
                Assert.Contains("123", status);
                Assert.Contains("456", status);
            }
        }
        finally
        {
            UiText.SetLanguage(UiText.DefaultLanguage);
        }
    }

    [Fact]
    public void StoreCounterVisibilityDoesNotRewriteOtherSettings()
    {
        var settings = new GameSettings(root);

        settings.StoreCounterVisibility(false);

        Assert.False(settings.ShowCounter);
        var reloaded = new GameSettings(root);
        Assert.False(reloaded.ShowCounter);
        Assert.Equal(GameSettings.Anonymous, reloaded.Player);
    }

    [Fact]
    public void EmptyPlayerFallsBackToAnonymousDuringLoadAndStore()
    {
        WriteConfiguration("[DEFAULT]", "player_identifier = ");
        var settings = new GameSettings(root);
        Assert.Equal(GameSettings.Anonymous, settings.Player);

        settings.Store("", "", "", AutoSaveMode.Off, true, false, true, 27, true, "zh_CN");
        Assert.Equal(GameSettings.Anonymous, settings.Player);
        Assert.Equal(GameSettings.Anonymous, new GameSettings(root).Player);
    }

    [Fact]
    public void WindowAndCounterPositionsArePersisted()
    {
        var settings = new GameSettings(root);

        settings.StoreCounterPosition(new Point(12, 34));
        settings.RememberPresetSize(2, 64);
        settings.StoreWindow(new Point(56, 78), settings.Preset(2));

        var reloaded = new GameSettings(root);
        Assert.Equal(new Point(12, 34), reloaded.CounterPosition);
        Assert.Equal(new Point(56, 78), reloaded.MainPosition);
        Assert.Equal(64, reloaded.Preset(2).Pixels);
    }

    [Fact]
    public void SettingsPageGridSizeIsPersistedImmediatelyForCurrentLevel()
    {
        var settings = new GameSettings(root);

        settings.StorePresetSize(1, 123);

        Assert.Equal(123, settings.Preset(1).Pixels);
        Assert.Equal(123, new GameSettings(root).Preset(1).Pixels);
        Assert.Equal(20, new GameSettings(root).Preset(0).Pixels);
        Assert.Equal(20, new GameSettings(root).Preset(2).Pixels);
    }

    [Fact]
    public void ReplayDirectoryLivesBesideConfiguration()
    {
        var settings = new GameSettings(root);

        Assert.Equal(Path.Combine(root, "replay"), settings.ReplayDirectory);
        Assert.True(Directory.Exists(settings.ReplayDirectory));
        Assert.True(File.Exists(Path.Combine(root, "gameSetting.ini")));
        Assert.DoesNotContain("gamemode", File.ReadAllText(Path.Combine(root, "gameSetting.ini")));
    }

    [Fact]
    public void UnknownLevelFallsBackToBeginnerAndIdentifierLimitsAreApplied()
    {
        string longIdentifier = new string('a', 200) + "\r\n\0";
        WriteConfiguration(
            "[DEFAULT]",
            "player_identifier = " + longIdentifier,
            "row = 99",
            "column = 99",
            "minenum = 99",
            "scoreboard_pixsize = 999");

        var settings = new GameSettings(root);

        Assert.Equal(0, settings.InitialLevel);
        Assert.Equal(128, settings.Player.Length);
        Assert.DoesNotContain("\r", settings.Player);
        Assert.DoesNotContain("\n", settings.Player);
        Assert.DoesNotContain("\0", settings.Player);
        Assert.Equal(48, settings.CounterPixels);
    }

    [Fact]
    public void PresetPixelSizesUseMetaSweeperBounds()
    {
        WriteConfiguration(
            "[BEGINNER]",
            "pixsize = 1",
            "[INTERMEDIATE]",
            "pixsize = 256",
            "[EXPERT]",
            "pixsize = 999");

        var settings = new GameSettings(root);

        Assert.Equal(5, settings.Preset(0).Pixels);
        Assert.Equal(255, settings.Preset(1).Pixels);
        Assert.Equal(255, settings.Preset(2).Pixels);
    }

    [Theory]
    [InlineData(-20, 5)]
    [InlineData(5, 5)]
    [InlineData(27, 27)]
    [InlineData(255, 255)]
    [InlineData(500, 255)]
    public void BoardPixelClampMatchesMetaSweeper(int input, int expected)
    {
        Assert.Equal(expected, BoardPixels.Clamp(input));
    }

    [Theory]
    [InlineData("5", "0")]
    [InlineData("0", "5")]
    public void UnsupportedGameModesFallBackToBeginner(string defaultMode, string intermediateMode)
    {
        WriteConfiguration(
            "[DEFAULT]",
            "gamemode = " + defaultMode,
            "row = 16",
            "column = 16",
            "minenum = 40",
            "[BEGINNER]",
            "gamemode = 0",
            "pixsize = 20",
            "[INTERMEDIATE]",
            "gamemode = " + intermediateMode,
            "pixsize = 30",
            "[EXPERT]",
            "gamemode = 0",
            "pixsize = 40");

        var settings = new GameSettings(root);

        Assert.Equal(0, settings.InitialLevel);
        Assert.True(settings.Preset(0).Matches(8, 8, 10));
        Assert.True(settings.Preset(1).Matches(16, 16, 40));
        Assert.True(settings.Preset(2).Matches(16, 30, 99));
    }

    private void WriteConfiguration(params string[] lines)
    {
        File.WriteAllText(Path.Combine(root, "gameSetting.ini"), string.Join(Environment.NewLine, lines));
    }

    private static Dictionary<string, List<string>> ReadSections(string text)
    {
        var sections = new Dictionary<string, List<string>>(StringComparer.Ordinal);
        string current = "";
        foreach (string raw in text.Split(new[] { "\r\n", "\n" }, StringSplitOptions.None))
        {
            string line = raw.Trim();
            if (line.Length == 0)
                continue;
            if (line[0] == '[' && line[line.Length - 1] == ']')
            {
                current = line.Substring(1, line.Length - 2);
                sections.Add(current, new List<string>());
                continue;
            }
            int separator = line.IndexOf('=');
            if (separator > 0)
                sections[current].Add(line.Substring(0, separator).Trim());
        }
        return sections;
    }
}
