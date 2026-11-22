using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Windows.Forms;

internal sealed class GameWindow : Form
{
    private static readonly TextId[] LevelNames = { TextId.Beginner, TextId.Intermediate, TextId.Expert };

    private readonly NativeCore core;
    private readonly GameSettings settings;
    private readonly GameShortcuts shortcuts;
    private readonly MenuStrip menu = new MenuStrip();
    private readonly ToolStripMenuItem save, counterItem, identityItem;
    private readonly Dictionary<ToolStripMenuItem, TextId> menuText = new Dictionary<ToolStripMenuItem, TextId>();
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
    private bool readingRefreshRate;
    private Task lastReplaySave = Task.FromResult(0);
    private bool closingAfterReplay, savingManually;
    private readonly CursorLock cursorLock = new CursorLock();
    private bool cursorReleased, resizing;
    private int bevelReferenceTile;

    internal GameWindow(NativeCore core, GameSettings settings)
    {
        this.core = core;
        this.settings = settings;
        shortcuts = new GameShortcuts();
        timer = new UiPulse(this, PollStatus);
        AccessibleName = Program.Name;
        AutoScaleMode = AutoScaleMode.None;
        Font = SystemFonts.MenuFont;
        Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        StartPosition = settings.MainPosition.HasValue ? FormStartPosition.Manual : FormStartPosition.CenterScreen;
        if (settings.MainPosition.HasValue)
            Location = settings.MainPosition.Value;
        BackColor = ClassicFrame.Canvas;
        FormBorderStyle = FormBorderStyle.Sizable;

        var gameMenu = MenuItem(TextId.GameMenu);
        var restart = MenuItem(TextId.Restart, (s, e) => StartGame(level));
        gameMenu.DropDownItems.Add(restart);
        shortcuts.Bind(restart, "restart", "menu_new_game");
        gameMenu.DropDownItems.Add(new ToolStripSeparator());
        string[] levelIds = { "beginner", "intermediate", "expert" };
        for (int index = 0; index < LevelNames.Length; index++)
        {
            int selected = index;
            var item = MenuItem(LevelNames[index], (s, e) => StartGame(selected));
            levelItems[index] = item;
            gameMenu.DropDownItems.Add(item);
            shortcuts.Bind(item, "preset_" + levelIds[index], "menu_" + levelIds[index]);
        }
        gameMenu.DropDownItems.Add(new ToolStripSeparator());
        save = MenuItem(TextId.SaveReplayMenu, (s, e) => SaveReplay());
        gameMenu.DropDownItems.Add(save);
        shortcuts.Bind(save, "menu_save");
        var replays = MenuItem(TextId.OpenReplayFolder, (s, e) => OpenReplayDirectory());
        gameMenu.DropDownItems.Add(replays);
        shortcuts.Bind(replays, "menu_open_replay");
        var quit = MenuItem(TextId.Quit, (s, e) => Close());
        gameMenu.DropDownItems.Add(quit);
        shortcuts.Bind(quit, "menu_quit");

        var setup = MenuItem(TextId.SettingsMenu);
        var gameSettings = MenuItem(TextId.GameSettings, (s, e) => EditSettings());
        var helpKeys = MenuItem(TextId.Shortcuts, (s, e) => shortcuts.Show(this));
        setup.DropDownItems.AddRange(new ToolStripItem[] { gameSettings, helpKeys });
        shortcuts.Bind(gameSettings, "menu_settings");
        shortcuts.Bind(helpKeys, "menu_keybindings");
        var view = MenuItem(TextId.ViewMenu);
        counterItem = MenuItem(TextId.Counter, (s, e) => ToggleCounter());
        identityItem = MenuItem(TextId.IdentityBar, (s, e) => ToggleIdentity());
        view.DropDownItems.AddRange(new ToolStripItem[] { counterItem, identityItem });
        shortcuts.Bind(counterItem, "toggle_counter");
        shortcuts.Bind(identityItem, "toggle_identity");
        var help = MenuItem(TextId.HelpMenu);
        help.DropDownItems.Add(MenuItem(TextId.Instructions, (s, e) =>
            MessageBox.Show(this,
                UiText.Get(TextId.ClickHelp) + "\n\n" + UiText.Get(TextId.WindowHelp),
                UiText.Get(TextId.Instructions), MessageBoxButtons.OK)));
        help.DropDownItems.Add(MenuItem(TextId.License, (s, e) =>
        {
            using (var resource = typeof(GameWindow).Assembly.GetManifestResourceStream("ms_toollib-LICENSE"))
            using (var reader = new StreamReader(resource))
                MessageBox.Show(this, reader.ReadToEnd(), "ms_toollib", MessageBoxButtons.OK);
        }));
        menu.AutoSize = false;
        menu.CanOverflow = true;
        menu.Height = BoardLayout.MenuHeight;
        menu.Font = new Font(SystemFonts.MenuFont.FontFamily, 16, GraphicsUnit.Pixel);
        menu.BackColor = ClassicFrame.Surface;
        menu.ForeColor = ClassicFrame.Ink;
        menu.Padding = new Padding(2, 2, 0, 2);
        identity.Font = menu.Font;
        menu.Items.AddRange(new ToolStripItem[] { gameMenu, setup, view, help });
        foreach (ToolStripItem item in menu.Items)
            item.Overflow = ToolStripItemOverflow.AsNeeded;
        MainMenuStrip = menu;
        frame.Dock = DockStyle.Fill;
        display.Dock = DockStyle.Top;
        board.Dock = DockStyle.Fill;
        frame.Controls.Add(board);
        frame.Controls.Add(display);
        Controls.Add(frame);
        Controls.Add(identity);
        Controls.Add(menu);
        identityItem.Checked = identity.Visible = settings.ShowIdentity;
        ApplyLanguage();

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

    private ToolStripMenuItem MenuItem(TextId label, EventHandler click = null)
    {
        var item = new ToolStripMenuItem("", null, click);
        menuText.Add(item, label);
        return item;
    }

    private void ApplyLanguage()
    {
        UiText.SetLanguage(settings.Language);
        Text = UiText.Get(TextId.Title);
        menu.SuspendLayout();
        foreach (var entry in menuText)
            entry.Key.Text = UiText.Get(entry.Value);
        menu.ResumeLayout(true);
        board.AccessibleName = UiText.Get(TextId.Board);
        display.ApplyLanguage();
        counter.ApplyLanguage();
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

    protected override void OnDpiChanged(DpiChangedEventArgs e)
    {
        // Client geometry is measured in screen pixels, while Windows sizes its own title bar.
        e.Cancel = true;
        base.OnDpiChanged(e);
        if (game != null && WindowState == FormWindowState.Normal)
        {
            int tile = board.TilePixels;
            MinimumSize = SizeFromClientSize(ClientSizeForTile(BoardPixels.Minimum));
            ClientSize = ClientSizeForTile(tile);
        }
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

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);
        if (e.Cancel || e.CloseReason != CloseReason.UserClosing || lastReplaySave.IsCompleted)
            return;
        e.Cancel = true;
        if (!closingAfterReplay)
            CloseAfterReplay();
    }

    private async void CloseAfterReplay()
    {
        closingAfterReplay = true;
        Enabled = false;
        await lastReplaySave;
        if (!IsDisposed)
            Close();
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
        int preservedPixels = game == null ? settings.Preset(selected).Pixels : board.TilePixels;
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

        Rectangle work = Screen.FromControl(this).WorkingArea;
        Size chrome = Size - ClientSize;
        int preferred = Math.Min(preservedPixels, FittingTile(work.Width - chrome.Width, work.Height - chrome.Height));
        if (bevelReferenceTile == 0)
            bevelReferenceTile = preferred;
        MinimumSize = SizeFromClientSize(ClientSizeForTile(BoardPixels.Minimum));
        if (!sameLevel && WindowState == FormWindowState.Normal)
        {
            ClientSize = ClientSizeForTile(preferred);
            if (Visible)
                Location = FitOnScreen(Location, Size);
        }
        UpdateScaledLayout();
        settings.RememberPresetSize(level, board.TilePixels);
        AdaptCounter();
        PositionCounter();
        UpdateIdentity();
        UpdateStatus();
    }

    private const int SizingMessage = 0x0214;

    [StructLayout(LayoutKind.Sequential)]
    private struct SizingRectangle
    {
        internal int Left, Top, Right, Bottom;
    }

    private Size ClientSizeForTile(int tile)
    {
        return new BoardLayout(tile, bevelReferenceTile).ClientSize(game.Rows, game.Columns, settings.ShowIdentity);
    }

    private int FooterHeight
    {
        get { return settings.ShowIdentity ? BoardLayout.IdentityHeight : 0; }
    }

    private int FittingTile(int width, int height)
    {
        int low = BoardPixels.Minimum;
        int high = BoardPixels.Clamp(Math.Min(width / game.Columns, height / game.Rows));
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
        Size chrome = Size - ClientSize;
        int wantedWidth = rectangle.Right - rectangle.Left - chrome.Width;
        int wantedHeight = rectangle.Bottom - rectangle.Top - chrome.Height;

        Rectangle proposed = Rectangle.FromLTRB(rectangle.Left, rectangle.Top, rectangle.Right, rectangle.Bottom);
        Rectangle work = Screen.FromRectangle(proposed).WorkingArea;
        int low = BoardPixels.Minimum;
        int high = FittingTile(work.Width - chrome.Width, work.Height - chrome.Height);
        // Side drags follow that axis. Corner drags project onto the board's resize direction.
        int weightX = edge == top || edge == bottom ? 0 : game.Columns;
        int weightY = edge == left || edge == right ? 0 : game.Rows + 2;
        int wanted = wantedWidth * weightX + wantedHeight * weightY;
        while (low < high)
        {
            int tile = (low + high) / 2;
            Size current = ClientSizeForTile(tile);
            Size next = ClientSizeForTile(tile + 1);
            int doubledMidpoint = (current.Width + next.Width) * weightX + (current.Height + next.Height) * weightY;
            if (wanted * 2 >= doubledMidpoint)
                low = tile + 1;
            else
                high = tile;
        }
        Size fitted = ClientSizeForTile(low) + chrome;

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
        var layout = new BoardLayout(FittingTile(ClientSize.Width, ClientSize.Height), bevelReferenceTile);
        frame.SuspendLayout();
        frame.Edge = layout.OuterEdge;
        frame.Padding = new Padding(layout.OuterInset);
        board.TilePixels = layout.Tile;
        board.Inset = layout.InnerEdge;
        identity.Height = FooterHeight;
        display.ApplyLayout(layout);
        frame.ResumeLayout();
        board.Invalidate();
    }

    private void ApplyCurrentPresetSize()
    {
        if (WindowState == FormWindowState.Minimized)
            return;
        Rectangle work = Screen.FromControl(this).WorkingArea;
        Size chrome = Size - ClientSize;
        int target = settings.Preset(level).Pixels;
        int fitted = FittingTile(work.Width - chrome.Width, work.Height - chrome.Height);
        ClientSize = ClientSizeForTile(Math.Min(target, fitted));
        Location = FitOnScreen(Location, Size);
        UpdateScaledLayout();
    }

    private void RememberBoardSize()
    {
        if (game != null && WindowState == FormWindowState.Normal)
            settings.RememberPresetSize(level, board.TilePixels);
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

    private string RefreshDevice()
    {
        return Screen.FromControl(counter.Visible ? (Control)counter : this).DeviceName;
    }

    private async void SyncRefreshRate(bool recheck = false)
    {
        if (timer == null || !Visible || IsDisposed || Disposing || readingRefreshRate)
            return;

        string device = RefreshDevice();
        if (!recheck && device == refreshDevice)
            return;
        readingRefreshRate = true;
        refreshDevice = device;
        lastRefreshCheck = Environment.TickCount;
        int refresh = await Task.Run(() => DisplayRefresh.Read(device));
        readingRefreshRate = false;
        if (!Visible || IsDisposed || Disposing)
            return;
        if (RefreshDevice() == device)
            timer.UpdateRefreshRate(refresh);
        else
            SyncRefreshRate();
    }

    private void PollStatus()
    {
        if (game == null)
            return;
        game.RefreshStatus();
        // Some drivers change frequency without broadcasting WM_DISPLAYCHANGE.
        if (unchecked(Environment.TickCount - lastRefreshCheck) >= 2000)
            SyncRefreshRate(true);
        UpdateStatus();
    }

    private void UpdateStatus()
    {
        if (game == null)
            return;
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
                MessageBox.Show(this, UiText.Get(TextId.TimingWarning), Text, MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }

    private void FinishGame(Game ended)
    {
        if (settings.AutoSave != AutoSaveMode.All &&
            (settings.AutoSave != AutoSaveMode.Wins || ended.State != Game.Phase.Won))
            return;

        byte[] replay;
        try
        {
            replay = ended.GetReplay();
        }
        catch (InvalidDataException error)
        {
            ReportError(TextId.ReplayGenerationError, error);
            return;
        }
        lastReplaySave = WriteAutomaticReplay(lastReplaySave, ReplayBaseName(ended), replay);
    }

    private async Task WriteAutomaticReplay(Task previous, string name, byte[] replay)
    {
        await previous;
        string directory = settings.ReplayDirectory;
        try
        {
            await Task.Run(() =>
            {
                Directory.CreateDirectory(directory);
                string path;
                do { path = ReplayFilename.UniquePath(directory, name); }
                while (!LocalFiles.TryWriteNew(path, replay));
            });
        }
        catch (Exception error)
        {
            if (!IsDisposed && !Disposing)
                ReportError(TextId.ReplayAutoSaveError, error);
        }
    }

    private async void SaveReplay()
    {
        if (!game.CanSaveReplay || savingManually)
            return;
        Game ended = game;
        savingManually = true;
        try
        {
            await lastReplaySave;
            if (!IsDisposed && !Disposing && !closingAfterReplay && ended == game)
                SaveReplayToFile(ended);
        }
        finally
        {
            savingManually = false;
        }
    }

    private void SaveReplayToFile(Game ended)
    {
        using (var dialog = new SaveFileDialog
        {
            Filter = UiText.Get(TextId.ReplayFiles) + " (*.evf)|*.evf",
            DefaultExt = "evf",
            AddExtension = true,
            OverwritePrompt = true,
            FileName = ReplayBaseName(ended) + ".evf",
            Title = UiText.Get(TextId.SaveReplayTitle)
        })
        {
            if (dialog.ShowDialog(this) != DialogResult.OK)
                return;
            try
            {
                LocalFiles.Write(dialog.FileName, ended.GetReplay());
            }
            catch (Exception error)
            {
                ReportError(TextId.ReplaySaveError, error);
            }
        }
    }

    private string ReplayBaseName(Game source)
    {
        ReplayMetrics metrics = source.Metrics ?? new ReplayMetrics();
        return ReplayFilename.Create(level, source.ElapsedSeconds, (int)metrics.Total,
            metrics.Speed, source.PlayerIdentifier, source.State == Game.Phase.Lost);
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
            ReportError(TextId.ReplayFolderError, error);
        }
    }

    private void EditSettings()
    {
        using (var dialog = new SettingsDialog(settings, level))
        {
            if (dialog.ShowDialog(this) != DialogResult.OK)
                return;
            try
            {
                int oldPixels = settings.Preset(level).Pixels;
                string oldLanguage = settings.Language;
                dialog.Store(settings);
                if (oldLanguage != settings.Language)
                    ApplyLanguage();
                ApplyIdentityVisibility();
                if (oldPixels != settings.Preset(level).Pixels)
                    ApplyCurrentPresetSize();
                game.SetIdentity(settings.Player, settings.Race, Countries.Code(settings.Country));
                game.SetFlagOnWin(settings.FlagOnWin);
                UpdateIdentity();
                AdaptCounter();
                ShowCounter();
                counter.Refresh();
                UpdateStatus();
                SyncCursorLock();
            }
            catch (Exception error)
            {
                ReportError(TextId.SettingsSaveError, error);
            }
        }
    }

    private void ToggleIdentity()
    {
        try
        {
            settings.StoreIdentityVisibility(!settings.ShowIdentity);
            ApplyIdentityVisibility();
        }
        catch (Exception error)
        {
            ReportError(TextId.IdentitySaveError, error);
        }
    }

    private void AdaptCounter()
    {
        using (var graphics = CreateGraphics())
            counter.Adapt(graphics.DpiX / 96 * settings.CounterPixels / 27f,
                Screen.FromControl(this).WorkingArea.Height);
    }

    private void ApplyIdentityVisibility()
    {
        if (identityItem.Checked == settings.ShowIdentity)
            return;

        int heightChange = FooterHeight - identity.Height;
        Size client = ClientSize;
        SuspendLayout();
        identityItem.Checked = settings.ShowIdentity;
        identity.Height = FooterHeight;
        identity.Visible = settings.ShowIdentity;
        MinimumSize = SizeFromClientSize(ClientSizeForTile(BoardPixels.Minimum));
        if (WindowState == FormWindowState.Normal)
        {
            ClientSize = new Size(client.Width, client.Height + heightChange);
            Location = FitOnScreen(Location, Size);
        }
        ResumeLayout(true);
        UpdateScaledLayout();
        SyncCursorLock();
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
            ReportError(TextId.CounterSaveError, error);
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
            ReportError(TextId.CounterPositionError, error);
        }
    }

    private static Point FitOnScreen(Point location, Size size)
    {
        Rectangle work = Screen.FromRectangle(new Rectangle(location, size)).WorkingArea;
        return new Point(Math.Max(work.Left, Math.Min(location.X, work.Right - size.Width)),
            Math.Max(work.Top, Math.Min(location.Y, work.Bottom - size.Height)));
    }

    private void ReportError(TextId description, Exception error)
    {
        MessageBox.Show(this, UiText.Get(description) + "\n" + error.Message, Text,
            MessageBoxButtons.OK, MessageBoxIcon.Error);
    }
}
