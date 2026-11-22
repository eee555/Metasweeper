using System;
using System.Drawing;
using System.Windows.Forms;

internal sealed class SettingsDialog : Form
{
    private readonly int selectedLevel;
    private readonly TextBox player = new TextBox { MaxLength = 128, Dock = DockStyle.Fill };
    private readonly TextBox race = new TextBox { MaxLength = 128, Dock = DockStyle.Fill };
    private readonly ComboBox country = new ComboBox { Dock = DockStyle.Fill, AutoCompleteMode = AutoCompleteMode.SuggestAppend,
        AutoCompleteSource = AutoCompleteSource.ListItems, MaxLength = 128 };
    private readonly ComboBox autoSave = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Dock = DockStyle.Fill };
    private readonly ComboBox language = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Dock = DockStyle.Fill };
    private readonly CheckBox cursorLimit = new CheckBox { AutoSize = true, Anchor = AnchorStyles.Left };
    private readonly CheckBox flagOnWin = new CheckBox { AutoSize = true, Anchor = AnchorStyles.Left };
    private readonly CheckBox showCounter = new CheckBox { AutoSize = true, Anchor = AnchorStyles.Left };
    private readonly CheckBox showIdentity = new CheckBox { AutoSize = true, Anchor = AnchorStyles.Left };
    private readonly NumericUpDown counterPixels = new NumericUpDown {
        Minimum = 12, Maximum = 48, Increment = 1, Dock = DockStyle.Left, Width = 92
    };
    private readonly NumericUpDown gridPixels = new NumericUpDown {
        Minimum = BoardPixels.Minimum,
        Maximum = BoardPixels.Maximum,
        Increment = 1,
        Dock = DockStyle.Left,
        Width = 92
    };

    internal SettingsDialog(GameSettings settings, int currentLevel)
    {
        selectedLevel = currentLevel;
        Text = UiText.Get(TextId.GameSettings);
        AutoScaleMode = AutoScaleMode.Dpi;
        AutoScaleDimensions = new SizeF(96, 96);
        Font = SystemFonts.MenuFont;
        ShowInTaskbar = false;
        MaximizeBox = false;
        MinimizeBox = false;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        StartPosition = FormStartPosition.CenterParent;
        ClientSize = new Size(640, 430);

        player.Text = settings.Player;
        race.Text = settings.Race;
        country.Items.AddRange(Countries.Names);
        country.Text = settings.Country;
        autoSave.Items.AddRange(new object[] {
            UiText.Get(TextId.AllResults), UiText.Get(TextId.WinsOnly), UiText.Get(TextId.Off)
        });
        autoSave.SelectedIndex = (int)settings.AutoSave;
        language.Items.AddRange(UiText.LanguageNames);
        language.SelectedIndex = UiText.LanguageIndex(settings.Language);
        gridPixels.Value = settings.Preset(selectedLevel).Pixels;
        cursorLimit.Text = UiText.Get(TextId.LockCursor);
        cursorLimit.Checked = settings.CursorLimit;
        flagOnWin.Text = UiText.Get(TextId.FlagOnWin);
        flagOnWin.Checked = settings.FlagOnWin;
        showCounter.Text = UiText.Get(TextId.ShowCounter);
        showCounter.Checked = settings.ShowCounter;
        showIdentity.Text = UiText.Get(TextId.ShowIdentity);
        showIdentity.Checked = settings.ShowIdentity;
        counterPixels.Value = settings.CounterPixels;

        var layout = new TableLayoutPanel {
            Dock = DockStyle.Fill,
            ColumnCount = 2,
            RowCount = 11,
            Padding = new Padding(12)
        };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        for (int i = 0; i < layout.RowCount; i++)
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));

        AddRow(layout, 0, TextId.Language, language);
        AddRow(layout, 1, TextId.Player, player);
        AddRow(layout, 2, TextId.Race, race);
        AddRow(layout, 3, TextId.Country, country);
        layout.Controls.Add(showIdentity, 1, 4);
        AddRow(layout, 5, TextId.TileSize, gridPixels);
        AddRow(layout, 6, TextId.AutoSave, autoSave);
        AddRow(layout, 7, TextId.Mouse, cursorLimit);
        AddRow(layout, 8, TextId.GameEnd, flagOnWin);
        AddRow(layout, 9, TextId.Counter, showCounter);
        AddRow(layout, 10, TextId.CounterScale, counterPixels);

        var ok = new Button { Text = UiText.Get(TextId.Ok), DialogResult = DialogResult.OK, AutoSize = true };
        var cancel = new Button { Text = UiText.Get(TextId.Cancel), DialogResult = DialogResult.Cancel, AutoSize = true };
        var buttons = new FlowLayoutPanel {
            Dock = DockStyle.Bottom,
            Height = 44,
            Padding = new Padding(8, 7, 8, 0),
            FlowDirection = FlowDirection.RightToLeft,
            WrapContents = false
        };
        buttons.Controls.AddRange(new Control[] { cancel, ok });

        Controls.Add(layout);
        Controls.Add(buttons);
        AcceptButton = ok;
        CancelButton = cancel;
    }

    private static void AddRow(TableLayoutPanel layout, int row, TextId label, Control entry)
    {
        string name = UiText.Get(label);
        layout.Controls.Add(new Label { Text = name, AutoSize = true, Anchor = AnchorStyles.Left }, 0, row);
        if (!(entry is CheckBox))
            entry.AccessibleName = name;
        layout.Controls.Add(entry, 1, row);
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        string value = country.Text.Trim();
        if (DialogResult == DialogResult.OK && value.Length != 0 &&
            !string.Equals(value, "XX", StringComparison.OrdinalIgnoreCase) && Countries.Code(value).Length == 0)
        {
            MessageBox.Show(this, UiText.Get(TextId.InvalidCountry), Text, MessageBoxButtons.OK);
            country.Focus();
            e.Cancel = true;
        }
        base.OnFormClosing(e);
    }

    internal void Store(GameSettings settings)
    {
        settings.Store(player.Text, race.Text, country.Text, (AutoSaveMode)autoSave.SelectedIndex,
            showCounter.Checked, cursorLimit.Checked, flagOnWin.Checked, (int)counterPixels.Value,
            showIdentity.Checked, UiText.LanguageCode(language.SelectedIndex));
        if (settings.Preset(selectedLevel).Pixels != (int)gridPixels.Value)
            settings.StorePresetSize(selectedLevel, (int)gridPixels.Value);
    }
}
