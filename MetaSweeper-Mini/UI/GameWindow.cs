using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows.Forms;

internal sealed class GameWindow : Form
{
    private static readonly string[] LevelNames = { "初级", "中级", "高级" };

    private readonly NativeCore core;
    private readonly GameSettings settings;
    private readonly GameShortcuts shortcuts;
    private readonly MenuStrip menu = new MenuStrip();
    private readonly ToolStripMenuItem save = new ToolStripMenuItem("保存录像…");
    private readonly ToolStripMenuItem counterItem = new ToolStripMenuItem("计数器");
    private readonly ToolStripMenuItem[] levelItems = new ToolStripMenuItem[LevelNames.Length];
    private readonly ClassicFrame frame = new ClassicFrame();
    private readonly DisplayPanel display = new DisplayPanel();
    private readonly BoardView board = new BoardView();
    private readonly IdentityFooter identity = new IdentityFooter();
    private readonly CounterWindow counter = new CounterWindow();
    private readonly UiPulse timer;
    private Game game;
    private int level;
    private bool finished;
    private string refreshDevice;
    private int lastRefreshCheck;
    private readonly CursorLock cursorLock = new CursorLock();
    private bool cursorReleased, resizing;
    private float windowScale = 1f;

    internal GameWindow(NativeCore core) : this(core, GameSettings.Load()) { }

    internal GameWindow(NativeCore core, GameSettings settings)
    {
        this.core = core;
        this.settings = settings;
        shortcuts = new GameShortcuts();
        timer = new UiPulse(this, UpdateStatus);
        Text = "元扫雷迷你版";
        AccessibleName = Program.Name;
        AutoScaleMode = AutoScaleMode.Dpi;
        AutoScaleDimensions = new SizeF(96, 96);
        Font = SystemFonts.MenuFont;
        Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        StartPosition = settings.MainPosition.HasValue ? FormStartPosition.Manual : FormStartPosition.CenterScreen;
        if (settings.MainPosition.HasValue)
            Location = settings.MainPosition.Value;
        BackColor = ClassicFrame.Canvas;
        FormBorderStyle = FormBorderStyle.Sizable;

        var gameMenu = new ToolStripMenuItem("游戏");
        var restart = new ToolStripMenuItem("新一局", null, (s, e) => StartGame(level));
        gameMenu.DropDownItems.Add(restart);
        shortcuts.Bind(restart, "restart", "menu_new_game");
        gameMenu.DropDownItems.Add(new ToolStripSeparator());
        string[] levelIds = { "beginner", "intermediate", "expert" };
        for (int index = 0; index < LevelNames.Length; index++)
        {
            int selected = index;
            var item = new ToolStripMenuItem(LevelNames[index], null, (s, e) => StartGame(selected));
            levelItems[index] = item;
            gameMenu.DropDownItems.Add(item);
            shortcuts.Bind(item, "preset_" + levelIds[index], "menu_" + levelIds[index]);
        }
        gameMenu.DropDownItems.Add(new ToolStripSeparator());
        save.Click += (s, e) => SaveReplay();
        gameMenu.DropDownItems.Add(save);
        shortcuts.Bind(save, "menu_save");
        var replays = new ToolStripMenuItem("打开录像目录", null, (s, e) => OpenReplayDirectory());
        gameMenu.DropDownItems.Add(replays);
        shortcuts.Bind(replays, "menu_open_replay");
        var quit = new ToolStripMenuItem("退出", null, (s, e) => Close());
        gameMenu.DropDownItems.Add(quit);
        shortcuts.Bind(quit, "menu_quit");

        var setup = new ToolStripMenuItem("设置");
        var gameSettings = new ToolStripMenuItem("游戏设置…", null, (s, e) => EditSettings());
        var helpKeys = new ToolStripMenuItem("快捷键…", null, (s, e) => shortcuts.Show(this));
        setup.DropDownItems.AddRange(new ToolStripItem[] { gameSettings, helpKeys });
        shortcuts.Bind(gameSettings, "menu_settings");
        shortcuts.Bind(helpKeys, "menu_keybindings");
        var view = new ToolStripMenuItem("查看");
        counterItem.Click += (s, e) => ToggleCounter();
        view.DropDownItems.Add(counterItem);
        shortcuts.Bind(counterItem, "toggle_counter");
        var help = new ToolStripMenuItem("帮助");
        help.DropDownItems.Add(new ToolStripMenuItem("操作说明", null, (s, e) =>
            MessageBox.Show(this,
                "左键开格，右键标雷。旗数与数字相符时，点数字格或同时按左右键可快速开格。\n\n"
                + "点击顶部任意位置或按 F2 开新一局。拖动窗口边缘或角落可按比例缩放棋盘。对局结束后可用 Ctrl+S 保存录像。"
                + "玩家标识、比赛标识、国家和自动保存选项在「设置」中。",
                "操作说明", MessageBoxButtons.OK)));
        help.DropDownItems.Add(new ToolStripMenuItem("开源许可", null, (s, e) =>
        {
            using (var resource = typeof(GameWindow).Assembly.GetManifestResourceStream("ms_toollib-LICENSE"))
            using (var reader = new StreamReader(resource))
                MessageBox.Show(this, reader.ReadToEnd(), "ms_toollib", MessageBoxButtons.OK);
        }));
        menu.Font = new Font(SystemFonts.MenuFont.FontFamily, 15, GraphicsUnit.Pixel);
        menu.BackColor = ClassicFrame.Surface;
        menu.ForeColor = ClassicFrame.Ink;
        menu.Padding = new Padding(2, 2, 0, 2);
        identity.Font = menu.Font;
        menu.Items.AddRange(new ToolStripItem[] { gameMenu, setup, view, help });
        MainMenuStrip = menu;
        frame.Dock = DockStyle.Fill;
        display.Dock = DockStyle.Top;
        board.Dock = DockStyle.Fill;
        frame.Controls.Add(board);
        frame.Controls.Add(display);
        Controls.Add(frame);
        Controls.Add(identity);
        Controls.Add(menu);

        display.Restart += (s, e) => StartGame(level);
        board.Changed += (s, e) => UpdateStatus();
        board.PressChanged += (s, e) => display.UpdatePress(game.State, board.Pressing);
        counter.PositionCommitted += (s, e) => CommitCounterPosition();
        counter.LocationChanged += (s, e) => SyncRefreshRate();
        counter.VisibleChanged += (s, e) => SyncRefreshRate();
        counter.HandleShortcut = shortcuts.Invoke;
        Shown += (s, e) =>
        {
            if (settings.MainPosition.HasValue)
                Location = FitOnScreen(settings.MainPosition.Value, Size);
            ShowCounter();
            SyncRefreshRate();
        };
        Activated += (s, e) => SyncCursorLock();
        Deactivate += (s, e) => cursorLock.Release();
        LocationChanged += (s, e) =>
        {
            PositionCounter();
            SyncCursorLock();
            SyncRefreshRate();
        };
        SizeChanged += (s, e) =>
        {
            UpdateScaledLayout();
            PositionCounter();
            SyncCursorLock();
            SyncRefreshRate();
        };
        ResizeBegin += (s, e) => { resizing = true; cursorLock.Release(); };
        ResizeEnd += (s, e) =>
        {
            resizing = false;
            RememberBoardSize();
            SyncCursorLock();
        };
        StartGame(settings.InitialLevel);
    }

    protected override bool ProcessCmdKey(ref Message message, Keys key)
    {
        if (key == Keys.Escape && game != null && game.State == Game.Phase.Playing && settings.CursorLimit)
        {
            cursorReleased = true;
            cursorLock.Release();
            return true;
        }
        return shortcuts.Invoke(key) || base.ProcessCmdKey(ref message, key);
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        cursorLock.Release();
        try
        {
            Point position = WindowState == FormWindowState.Normal ? Location : RestoreBounds.Location;
            settings.StoreWindow(position, settings.Preset(level));
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
        base.OnFormClosed(e);
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            cursorLock.Release();
            if (timer != null)
                timer.Dispose();
            counter.Dispose();
            if (game != null)
                game.Dispose();
        }
        base.Dispose(disposing);
    }

    private void StartGame(int selected)
    {
        cursorLock.Release();
        cursorReleased = false;
        bool sameLevel = game != null && selected == level;
        if (game != null)
            game.Dispose();
        level = selected;
        finished = false;
        BoardPreset preset = settings.Preset(level);
        game = new Game(core, preset.Rows, preset.Columns, preset.Mines, settings.FlagOnWin);
        game.SetIdentity(settings.Player, settings.Race, Countries.Code(settings.Country));
        board.SetGame(game);
        for (int i = 0; i < levelItems.Length; i++)
            levelItems[i].Checked = i == level;

        using (var graphics = CreateGraphics())
            windowScale = graphics.DpiX / 96;
        MinimumSize = SizeFromClientSize(ClientSizeForTile(MinimumTile));

        Rectangle work = Screen.FromControl(this).WorkingArea;
        if (!sameLevel && WindowState == FormWindowState.Normal)
        {
            Size chrome = Size - ClientSize;
            int width = work.Width - chrome.Width;
            int height = work.Height - chrome.Height;
            int preferred = (int)Math.Round(preset.Pixels * windowScale);
            ClientSize = ClientSizeForTile(Math.Max(MinimumTile, Math.Min(preferred, FittingTile(width, height))));
            if (Visible)
                Location = FitOnScreen(Location, Size);
        }
        UpdateScaledLayout();
        counter.Adapt(windowScale * settings.CounterPixels / 27f, work.Height);
        PositionCounter();
        UpdateIdentity();
        UpdateStatus();
    }

    private const int ReferenceTile = 27;
    private const int SizingMessage = 0x0214;

    [StructLayout(LayoutKind.Sequential)]
    private struct SizingRectangle
    {
        internal int Left, Top, Right, Bottom;
    }

    private int MinimumTile { get { return Math.Max(9, (int)Math.Round(12 * windowScale)); } }

    private static int ScalePart(int pixels, int tile)
    {
        return Math.Max(1, (pixels * tile + ReferenceTile / 2) / ReferenceTile);
    }

    private Size ClientSizeForTile(int tile)
    {
        int sides = 2 * (ScalePart(16, tile) + ScalePart(4, tile));
        int height = game.Rows * tile + tile * 3 / 2 + ScalePart(18, tile)
            + ScalePart(38, tile) + ScalePart(7, tile) + menu.PreferredSize.Height + sides;
        return new Size(game.Columns * tile + sides, height);
    }

    private int FittingTile(int width, int height)
    {
        int low = 1;
        int high = Math.Max(low, Math.Min(width / game.Columns, height / game.Rows));
        while (low < high)
        {
            int candidate = low + (high - low + 1) / 2;
            Size requested = ClientSizeForTile(candidate);
            if (requested.Width <= width && requested.Height <= height)
                low = candidate;
            else
                high = candidate - 1;
        }
        return low;
    }

    protected override void WndProc(ref Message message)
    {
        if (message.Msg == SizingMessage && game != null && message.LParam != IntPtr.Zero)
        {
            var proposed = (SizingRectangle)Marshal.PtrToStructure(message.LParam, typeof(SizingRectangle));
            ConstrainDrag(ref proposed, message.WParam.ToInt32());
            Marshal.StructureToPtr(proposed, message.LParam, false);
            message.Result = new IntPtr(1);
            return;
        }
        base.WndProc(ref message);
        if (message.Msg == 0x007E) // WM_DISPLAYCHANGE
            SyncRefreshRate(true);
    }

    private void ConstrainDrag(ref SizingRectangle rectangle, int edge)
    {
        const int left = 1, right = 2, top = 3, topLeft = 4, topRight = 5, bottom = 6, bottomLeft = 7;
        int menuHeight = menu.PreferredSize.Height;
        Size chrome = Size - ClientSize;
        Size reference = ClientSizeForTile(ReferenceTile);
        int height = reference.Height - menuHeight;
        int wantedWidth = rectangle.Right - rectangle.Left - chrome.Width;
        int wantedHeight = rectangle.Bottom - rectangle.Top - chrome.Height - menuHeight;

        double ratio;
        if (edge == left || edge == right)
            ratio = (double)wantedWidth / reference.Width;
        else if (edge == top || edge == bottom)
            ratio = (double)wantedHeight / height;
        else
            ratio = ((double)wantedWidth * reference.Width + (double)wantedHeight * height)
                / ((double)reference.Width * reference.Width + (double)height * height);

        Rectangle proposed = Rectangle.FromLTRB(rectangle.Left, rectangle.Top, rectangle.Right, rectangle.Bottom);
        Rectangle work = Screen.FromRectangle(proposed).WorkingArea;
        int largest = FittingTile(work.Width - chrome.Width, work.Height - chrome.Height);
        int tile = Math.Max(MinimumTile, Math.Min(largest, (int)Math.Round(ratio * ReferenceTile)));
        Size fitted = ClientSizeForTile(tile) + chrome;

        if (edge == left || edge == topLeft || edge == bottomLeft)
            rectangle.Left = rectangle.Right - fitted.Width;
        else
            rectangle.Right = rectangle.Left + fitted.Width;
        if (edge == top || edge == topLeft || edge == topRight)
            rectangle.Top = rectangle.Bottom - fitted.Height;
        else
            rectangle.Bottom = rectangle.Top + fitted.Height;
    }

    private void UpdateScaledLayout()
    {
        if (game == null || WindowState == FormWindowState.Minimized)
            return;
        int tile = FittingTile(ClientSize.Width, ClientSize.Height);
        frame.SuspendLayout();
        frame.Padding = new Padding(ScalePart(16, tile));
        board.Inset = ScalePart(4, tile);
        board.Gap = ScalePart(7, tile);
        identity.Height = ScalePart(38, tile);
        display.SpriteSize = Math.Max(1, tile * 3 / 2);
        display.Height = display.SpriteSize + ScalePart(18, tile);
        frame.ResumeLayout();
        board.Invalidate();
    }

    private void RememberBoardSize()
    {
        if (game != null && WindowState == FormWindowState.Normal)
            settings.RememberPresetSize(level, (int)Math.Round(board.TilePixels / windowScale));
    }

    private void UpdateIdentity()
    {
        identity.ShowIdentity(game.PlayerIdentifier, game.CountryCode);
    }

    private void SyncCursorLock()
    {
        if (game == null || game.State != Game.Phase.Playing || !settings.CursorLimit || cursorReleased
            || resizing || !IsHandleCreated || !Visible || WindowState == FormWindowState.Minimized
            || CursorLock.GetForegroundWindow() != Handle)
        {
            cursorLock.Release();
            return;
        }
        if (cursorLock.Apply(board.ScreenBoardBounds))
            game.UsedCursorLimit = true;
    }

    private void SyncRefreshRate(bool recheck = false)
    {
        if (timer == null || !Visible || IsDisposed || Disposing)
            return;

        string device = Screen.FromControl(counter.Visible ? (Control)counter : this).DeviceName;
        if (!recheck && device == refreshDevice)
            return;
        refreshDevice = device;
        lastRefreshCheck = Environment.TickCount;
        timer.UpdateRefreshRate(DisplayRefresh.Read(device));
    }

    private void UpdateStatus()
    {
        if (game == null)
            return;
        if (game.State == Game.Phase.Playing || (!game.CanPlay && !game.Metrics.HasValue))
            game.RefreshStatus();

        // Some drivers change frequency without broadcasting WM_DISPLAYCHANGE.
        if (unchecked(Environment.TickCount - lastRefreshCheck) >= 2000)
            SyncRefreshRate(true);
        SyncCursorLock();
        save.Enabled = game.CanSaveReplay;
        display.Update(game.Remaining, game.Seconds, game.State, board.Pressing);
        if (counter.Visible)
            counter.Display(game);
        timer.Enabled = game.State == Game.Phase.Playing || (!game.CanPlay && !game.Metrics.HasValue);
        if (!game.CanPlay && !finished)
        {
            finished = true;
            if (game.TimingValid)
                FinishGame(game);
            else
                MessageBox.Show(this, "本局计时异常，录像未保存。", Program.Name, MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }

    private void FinishGame(Game ended)
    {
        byte[] replay;
        try
        {
            replay = ended.GetReplay();
        }
        catch (InvalidDataException error)
        {
            ReportError("未能生成录像。", error);
            return;
        }
        if (settings.AutoSave == AutoSaveMode.All || (settings.AutoSave == AutoSaveMode.Wins && ended.State == Game.Phase.Won))
        {
            try
            {
                Directory.CreateDirectory(settings.ReplayDirectory);
                string filename = Program.Name + "-" + LevelNames[level] + "-" + DateTime.Now.ToString("yyyyMMdd-HHmmss-fff")
                    + "-" + Guid.NewGuid().ToString("N").Substring(0, 8) + ".evf";
                LocalFiles.Write(Path.Combine(settings.ReplayDirectory, filename), replay);
            }
            catch (Exception error)
            {
                ReportError("自动保存录像失败。仍可尝试使用 Ctrl+S 手动保存。", error);
            }
        }

    }

    private void SaveReplay()
    {
        if (!game.CanSaveReplay)
            return;
        using (var dialog = new SaveFileDialog
        {
            Filter = "EVF 扫雷录像 (*.evf)|*.evf",
            DefaultExt = "evf",
            AddExtension = true,
            OverwritePrompt = true,
            FileName = Program.Name + "-" + LevelNames[level] + "-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + ".evf",
            Title = "保存本局录像"
        })
        {
            if (dialog.ShowDialog(this) != DialogResult.OK)
                return;
            try
            {
                LocalFiles.Write(dialog.FileName, game.GetReplay());
            }
            catch (Exception error)
            {
                ReportError("录像保存失败。", error);
            }
        }
    }

    private void OpenReplayDirectory()
    {
        try
        {
            Directory.CreateDirectory(settings.ReplayDirectory);
            Process.Start(new ProcessStartInfo(settings.ReplayDirectory) { UseShellExecute = true });
        }
        catch (Exception error)
        {
            ReportError("未能打开录像目录。", error);
        }
    }

    private void EditSettings()
    {
        using (var dialog = new SettingsDialog(settings))
        {
            if (dialog.ShowDialog(this) != DialogResult.OK)
                return;
            try
            {
                dialog.Store(settings);
                game.SetIdentity(settings.Player, settings.Race, Countries.Code(settings.Country));
                game.SetFlagOnWin(settings.FlagOnWin);
                UpdateIdentity();
                using (var graphics = CreateGraphics())
                    windowScale = graphics.DpiX / 96;
                counter.Adapt(windowScale * settings.CounterPixels / 27f,
                    Screen.FromControl(this).WorkingArea.Height);
                ShowCounter();
                counter.Refresh();
                UpdateStatus();
                SyncCursorLock();
            }
            catch (Exception error)
            {
                ReportError("未能保存游戏设置。", error);
            }
        }
    }

    private void ToggleCounter()
    {
        try
        {
            settings.StoreCounterVisibility(!settings.ShowCounter);
            ShowCounter();
        }
        catch (Exception error)
        {
            ReportError("未能保存计数器设置。", error);
        }
    }

    private void ShowCounter()
    {
        counterItem.Checked = settings.ShowCounter;
        if (!settings.ShowCounter)
        {
            counter.Hide();
            return;
        }
        PositionCounter();
        if (!counter.Visible)
            counter.Show(this);
        counter.Display(game);
    }

    private void PositionCounter()
    {
        if (!Visible || WindowState != FormWindowState.Normal)
            return;
        if (settings.CounterPosition.HasValue)
        {
            counter.Location = FitOnScreen(settings.CounterPosition.Value, counter.Size);
            return;
        }
        const int gap = 9;
        Rectangle work = Screen.FromControl(this).WorkingArea;
        int left = Left - counter.Width - gap;
        if (left < work.Left && Right + gap + counter.Width <= work.Right)
            left = Right + gap;
        int top = Math.Min(Bounds.Top + 10, work.Bottom - counter.Height);
        counter.Location = new Point(Math.Max(work.Left, left), Math.Max(work.Top, top));
    }

    private void CommitCounterPosition()
    {
        try
        {
            settings.StoreCounterPosition(counter.Location);
        }
        catch (Exception error)
        {
            ReportError("未能保存计数器位置。", error);
        }
    }

    private static Point FitOnScreen(Point location, Size size)
    {
        Rectangle work = Screen.FromRectangle(new Rectangle(location, size)).WorkingArea;
        return new Point(Math.Max(work.Left, Math.Min(location.X, work.Right - size.Width)),
            Math.Max(work.Top, Math.Min(location.Y, work.Bottom - size.Height)));
    }

    private void ReportError(string description, Exception error)
    {
        MessageBox.Show(this, description + "\n" + error.Message, Program.Name,
            MessageBoxButtons.OK, MessageBoxIcon.Error);
    }
}
