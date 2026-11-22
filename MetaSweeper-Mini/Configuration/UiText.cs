using System;

internal enum TextId
{
    Title,
    GameMenu,
    Restart,
    Beginner,
    Intermediate,
    Expert,
    SaveReplayMenu,
    OpenReplayFolder,
    Quit,
    SettingsMenu,
    GameSettings,
    Shortcuts,
    ViewMenu,
    Counter,
    IdentityBar,
    HelpMenu,
    Instructions,
    ClickHelp,
    WindowHelp,
    License,
    TimingWarning,
    ReplayGenerationError,
    ReplayAutoSaveError,
    ReplayFiles,
    SaveReplayTitle,
    ReplaySaveError,
    ReplayFolderError,
    SettingsSaveError,
    CounterSaveError,
    IdentitySaveError,
    CounterPositionError,
    Player,
    Race,
    Country,
    AutoSave,
    AllResults,
    WinsOnly,
    Off,
    TileSize,
    Mouse,
    LockCursor,
    GameEnd,
    FlagOnWin,
    ShowCounter,
    CounterScale,
    ShowIdentity,
    Language,
    Ok,
    Cancel,
    InvalidCountry,
    GameMode,
    Standard,
    Board,
    DisplayStatus,
    StartupError,
    ReplayTooEarly,
    ReplaySigned,
    InvalidChecksum,
    InvalidCoreSize,
    ReplayUnavailable,
}

internal static class UiText
{
    internal const string DefaultLanguage = "zh_CN";
    private static readonly string[] Codes = { DefaultLanguage, "en_US", "de_DE", "pl_PL", "ja_JP" };
    internal static readonly string[] LanguageNames = { "简体中文", "English", "Deutsch", "Polski", "日本語" };

    // Columns follow Codes. Keep identifiers, metrics and replay fields outside this table.
    private static readonly string[,] Translations = {
        { "元扫雷迷你版", "MetaSweeper Mini", "MetaSweeper Mini", "MetaSweeper Mini", "メタマインスイーパーミニ" }, // Title
        { "游戏", "Game", "Spiel", "Gra", "ゲーム" }, // GameMenu
        { "新一局", "New game", "Neues Spiel", "Nowa gra", "新しいゲーム" }, // Restart
        { "初级", "Beginner", "Anfänger", "Początkujący", "初級" }, // Beginner
        { "中级", "Intermediate", "Fortgeschritten", "Średnio zaawansowany", "中級" }, // Intermediate
        { "高级", "Expert", "Experte", "Ekspert", "上級" }, // Expert
        { "保存录像…", "Save replay…", "Aufzeichnung speichern…", "Zapisz nagranie…", "リプレイを保存…" }, // SaveReplayMenu
        { "打开录像目录", "Open replay folder", "Aufzeichnungsordner öffnen", "Otwórz folder nagrań", "リプレイフォルダーを開く" }, // OpenReplayFolder
        { "退出", "Exit", "Beenden", "Zakończ", "終了" }, // Quit
        { "设置", "Settings", "Einstellungen", "Ustawienia", "設定" }, // SettingsMenu
        { "游戏设置", "Game settings", "Spieleinstellungen", "Ustawienia gry", "ゲーム設定" }, // GameSettings
        { "快捷键", "Keyboard shortcuts", "Tastenkürzel", "Skróty klawiszowe", "キーボードショートカット" }, // Shortcuts
        { "查看", "View", "Ansicht", "Widok", "表示" }, // ViewMenu
        { "计数器", "Counter", "Zähler", "Licznik", "カウンター" }, // Counter
        { "玩家标识栏", "Player name bar", "Spielernamensleiste", "Pasek nazwy gracza", "プレイヤー名欄" }, // IdentityBar
        { "帮助", "Help", "Hilfe", "Pomoc", "ヘルプ" }, // HelpMenu
        { "操作说明", "How to play", "Spielanleitung", "Jak grać", "遊び方" }, // Instructions
        { "左键开格，右键标雷。旗数与数字相符时，点数字格或同时按左右键可快速开格。", "Left-click to open a cell and right-click to flag it. When the surrounding flags match a number, click the number or press both mouse buttons to open its neighbors.", "Linksklick öffnet ein Feld, Rechtsklick setzt eine Flagge. Stimmen Zahl und benachbarte Flaggen überein, öffnet ein Klick auf die Zahl oder ein Druck beider Tasten die Nachbarfelder.", "Kliknij lewym przyciskiem, aby odkryć pole, a prawym, aby je oflagować. Gdy liczba sąsiednich flag zgadza się z cyfrą, kliknij cyfrę lub naciśnij oba przyciski, aby odkryć sąsiednie pola.", "左クリックでマスを開き、右クリックで旗を立てます。周囲の旗の数が数字と一致したら、数字をクリックするか左右のボタンを同時に押すと周囲のマスを開けます。" }, // ClickHelp
        { "点击笑脸所在行或按 F2 开新一局。拖动窗口边缘可按比例缩放棋盘。对局结束后按 Ctrl+S 保存录像。", "Click the smiley row or press F2 to start a new game. Drag a window edge to resize the board proportionally. Press Ctrl+S after the game to save a replay.", "Klicke auf die Smiley-Zeile oder drücke F2 für ein neues Spiel. Ziehe am Fensterrand, um das Spielfeld proportional zu skalieren. Nach Spielende speichert Strg+S die Aufzeichnung.", "Kliknij pasek z buźką lub naciśnij F2, aby zacząć nową grę. Przeciągnij krawędź okna, aby proporcjonalnie zmienić rozmiar planszy. Po grze naciśnij Ctrl+S, aby zapisać nagranie.", "顔アイコンの行をクリックするか F2 を押すと新しいゲームを開始します。ウィンドウの端をドラッグすると盤面を同比率で拡大・縮小できます。終了後は Ctrl+S でリプレイを保存できます。" }, // WindowHelp
        { "开源许可", "Open-source license", "Open-Source-Lizenz", "Licencja open source", "オープンソースライセンス" }, // License
        { "本局计时异常，录像未保存。", "A timing error prevented this replay from being saved.", "Ein Zeitmessfehler hat das Speichern der Aufzeichnung verhindert.", "Błąd pomiaru czasu uniemożliwił zapisanie nagrania.", "計時に異常があったため、リプレイは保存されませんでした。" }, // TimingWarning
        { "未能生成录像。", "Could not generate the replay.", "Die Aufzeichnung konnte nicht erstellt werden.", "Nie udało się utworzyć nagrania.", "リプレイを作成できませんでした。" }, // ReplayGenerationError
        { "自动保存录像失败。仍可尝试使用 Ctrl+S 手动保存。", "Could not save the replay automatically. Press Ctrl+S to try saving it manually.", "Die Aufzeichnung konnte nicht automatisch gespeichert werden. Mit Strg+S kannst du sie manuell speichern.", "Nie udało się automatycznie zapisać nagrania. Naciśnij Ctrl+S, aby spróbować zapisać je ręcznie.", "リプレイを自動保存できませんでした。Ctrl+S で手動保存を試せます。" }, // ReplayAutoSaveError
        { "EVF 扫雷录像", "EVF Minesweeper replays", "EVF-Minesweeper-Aufzeichnungen", "Nagrania Sapera EVF", "EVF マインスイーパーリプレイ" }, // ReplayFiles
        { "保存本局录像", "Save this replay", "Diese Aufzeichnung speichern", "Zapisz to nagranie", "このリプレイを保存" }, // SaveReplayTitle
        { "录像保存失败。", "Could not save the replay.", "Die Aufzeichnung konnte nicht gespeichert werden.", "Nie udało się zapisać nagrania.", "リプレイを保存できませんでした。" }, // ReplaySaveError
        { "未能打开录像目录。", "Could not open the replay folder.", "Der Aufzeichnungsordner konnte nicht geöffnet werden.", "Nie udało się otworzyć folderu nagrań.", "リプレイフォルダーを開けませんでした。" }, // ReplayFolderError
        { "未能保存游戏设置。", "Could not save the game settings.", "Die Spieleinstellungen konnten nicht gespeichert werden.", "Nie udało się zapisać ustawień gry.", "ゲーム設定を保存できませんでした。" }, // SettingsSaveError
        { "未能保存计数器设置。", "Could not save the counter settings.", "Die Zählereinstellungen konnten nicht gespeichert werden.", "Nie udało się zapisać ustawień licznika.", "カウンター設定を保存できませんでした。" }, // CounterSaveError
        { "未能保存玩家标识栏设置。", "Could not save the player name bar setting.", "Die Einstellung für die Spielernamensleiste konnte nicht gespeichert werden.", "Nie udało się zapisać ustawienia paska nazwy gracza.", "プレイヤー名欄の設定を保存できませんでした。" }, // IdentitySaveError
        { "未能保存计数器位置。", "Could not save the counter position.", "Die Zählerposition konnte nicht gespeichert werden.", "Nie udało się zapisać pozycji licznika.", "カウンターの位置を保存できませんでした。" }, // CounterPositionError
        { "玩家标识", "Player identifier", "Spielerkennung", "Identyfikator gracza", "プレイヤー ID" }, // Player
        { "比赛标识", "Competition identifier", "Wettkampfkennung", "Identyfikator zawodów", "大会 ID" }, // Race
        { "国家或地区", "Country or region", "Land oder Region", "Kraj lub region", "国または地域" }, // Country
        { "自动保存录像", "Auto-save replays", "Aufzeichnungen automatisch speichern", "Automatyczny zapis nagrań", "リプレイの自動保存" }, // AutoSave
        { "胜利和踩雷", "Wins and losses", "Siege und Niederlagen", "Wygrane i przegrane", "勝利と敗北" }, // AllResults
        { "仅胜利", "Wins only", "Nur Siege", "Tylko wygrane", "勝利のみ" }, // WinsOnly
        { "关闭", "Off", "Aus", "Wyłączony", "オフ" }, // Off
        { "格子大小", "Cell size", "Feldgröße", "Rozmiar pola", "マスのサイズ" }, // TileSize
        { "鼠标", "Mouse", "Maus", "Mysz", "マウス" }, // Mouse
        { "开局后锁定在棋盘内（Esc 解锁）", "Lock to board during play (Esc to release)", "Im Spiel ans Feld binden (Esc zum Freigeben)", "Blokuj na planszy podczas gry (Esc zwalnia)", "プレイ中は盤面内に固定（Esc で解除）" }, // LockCursor
        { "结束处理", "End of game", "Spielende", "Koniec gry", "ゲーム終了時" }, // GameEnd
        { "获胜后自动标出剩余地雷", "Flag remaining mines on a win", "Bei einem Sieg übrige Minen markieren", "Oflaguj pozostałe miny po wygranej", "勝利時に残りの地雷に旗を立てる" }, // FlagOnWin
        { "显示计数器", "Show counter", "Zähler anzeigen", "Pokaż licznik", "カウンターを表示" }, // ShowCounter
        { "计数器缩放", "Counter scale", "Zählerskalierung", "Skala licznika", "カウンターの拡大率" }, // CounterScale
        { "显示底部玩家标识", "Show player name at the bottom", "Spielernamen unten anzeigen", "Pokaż nazwę gracza na dole", "下部にプレイヤー名を表示" }, // ShowIdentity
        { "界面语言", "Interface language", "Oberflächensprache", "Język interfejsu", "表示言語" }, // Language
        { "确定", "OK", "OK", "OK", "OK" }, // Ok
        { "取消", "Cancel", "Abbrechen", "Anuluj", "キャンセル" }, // Cancel
        { "请选择国家或地区，或输入两位字母代码。", "Choose a country or region, or enter a two-letter code.", "Wähle ein Land oder eine Region oder gib einen zweistelligen Buchstabencode ein.", "Wybierz kraj lub region albo wpisz dwuliterowy kod.", "国または地域を選ぶか、英字2文字のコードを入力してください。" }, // InvalidCountry
        { "游戏模式", "Game mode", "Spielmodus", "Tryb gry", "ゲームモード" }, // GameMode
        { "标准", "Standard", "Standard", "Standardowy", "標準" }, // Standard
        { "扫雷棋盘", "Minesweeper board", "Minesweeper-Spielfeld", "Plansza Sapera", "マインスイーパーの盤面" }, // Board
        { "剩雷 {0}，用时 {1} 秒", "Mines remaining: {0}, elapsed: {1} seconds", "Verbleibende Minen: {0}, Spielzeit: {1} Sekunden", "Pozostałe miny: {0}, czas: {1} s", "残り地雷 {0}、経過 {1} 秒" }, // DisplayStatus
        { "无法启动扫雷。", "Could not start Minesweeper.", "Minesweeper konnte nicht gestartet werden.", "Nie udało się uruchomić Sapera.", "マインスイーパーを起動できませんでした。" }, // StartupError
        { "请结束这一局后再保存录像。", "Finish this game before saving its replay.", "Beende das Spiel, bevor du die Aufzeichnung speicherst.", "Zakończ grę przed zapisaniem nagrania.", "ゲームを終了してからリプレイを保存してください。" }, // ReplayTooEarly
        { "录像已包含校验码，不能重复签名。", "This replay already contains a checksum.", "Diese Aufzeichnung enthält bereits eine Prüfsumme.", "Nagranie zawiera już sumę kontrolną.", "このリプレイにはすでにチェックサムがあります。" }, // ReplaySigned
        { "EVF 校验码字段格式不正确。", "The EVF checksum field has an invalid format.", "Das EVF-Prüfsummenfeld hat ein ungültiges Format.", "Pole sumy kontrolnej EVF ma nieprawidłowy format.", "EVF チェックサムフィールドの形式が正しくありません。" }, // InvalidChecksum
        { "内嵌扫雷库的大小不正确。", "The embedded Minesweeper library has an invalid size.", "Die eingebettete Minesweeper-Bibliothek hat eine ungültige Größe.", "Osadzona biblioteka Sapera ma nieprawidłowy rozmiar.", "内蔵マインスイーパーライブラリのサイズが正しくありません。" }, // InvalidCoreSize
        { "这一局的录像数据不可用。", "Replay data for this game is unavailable.", "Für dieses Spiel sind keine Aufzeichnungsdaten verfügbar.", "Dane nagrania tej gry są niedostępne.", "このゲームのリプレイデータを利用できません。" }, // ReplayUnavailable
    };

    private static int language;

    internal static string NormalizeLanguage(string code)
    {
        return Codes[LanguageIndex(code)];
    }

    internal static int LanguageIndex(string code)
    {
        int index = Array.FindIndex(Codes, value => string.Equals(value, code, StringComparison.OrdinalIgnoreCase));
        return Math.Max(0, index);
    }

    internal static string LanguageCode(int index)
    {
        return Codes[index];
    }

    internal static void SetLanguage(string code)
    {
        language = LanguageIndex(code);
    }

    internal static string Get(TextId id)
    {
        return Translations[(int)id, language];
    }
}
