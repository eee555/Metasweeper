using System;
using System.Drawing;
using System.Windows.Forms;

internal sealed class SettingsDialog : Form
{
    private readonly TextBox player = new TextBox { MaxLength = 128, Dock = DockStyle.Fill };
    private readonly TextBox race = new TextBox { MaxLength = 128, Dock = DockStyle.Fill };
    private readonly ComboBox country = new ComboBox { Dock = DockStyle.Fill, AutoCompleteMode = AutoCompleteMode.SuggestAppend,
        AutoCompleteSource = AutoCompleteSource.ListItems, MaxLength = 128 };
    private readonly ComboBox autoSave = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Dock = DockStyle.Fill };
    private readonly CheckBox cursorLimit = new CheckBox { Text = "开局后锁定在棋盘内（Esc 解锁）", AutoSize = true };
    private readonly CheckBox flagOnWin = new CheckBox { Text = "获胜后自动标出剩余地雷", AutoSize = true };
    private readonly CheckBox showCounter = new CheckBox { Text = "显示计数器", AutoSize = true };
    private readonly NumericUpDown counterPixels = new NumericUpDown {
        Minimum = 12, Maximum = 48, Increment = 1, Dock = DockStyle.Left, Width = 92
    };

    internal SettingsDialog(GameSettings settings)
    {
        Text = "游戏设置";
        AutoScaleMode = AutoScaleMode.Dpi;
        AutoScaleDimensions = new SizeF(96, 96);
        Font = SystemFonts.MenuFont;
        ShowInTaskbar = false;
        MaximizeBox = false;
        MinimizeBox = false;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        StartPosition = FormStartPosition.CenterParent;
        ClientSize = new Size(510, 430);

        player.Text = settings.Player;
        player.AccessibleName = "玩家标识";
        race.Text = settings.Race;
        race.AccessibleName = "比赛标识";
        country.AccessibleName = "国家或地区";
        country.Items.AddRange(Countries.Names);
        country.Text = settings.Country;
        autoSave.Items.AddRange(new object[] { "胜利和踩雷", "仅胜利", "关闭" });
        autoSave.SelectedIndex = (int)settings.AutoSave;
        autoSave.AccessibleName = "自动保存录像";
        cursorLimit.Checked = settings.CursorLimit;
        flagOnWin.Checked = settings.FlagOnWin;
        showCounter.Checked = settings.ShowCounter;
        counterPixels.Value = settings.CounterPixels;

        var layout = new TableLayoutPanel {
            Dock = DockStyle.Fill,
            ColumnCount = 2,
            RowCount = 9,
            Padding = new Padding(12)
        };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 132));
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        for (int i = 0; i < 8; i++)
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 42));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));

        AddRow(layout, 0, "玩家标识", player);
        AddRow(layout, 1, "比赛标识", race);
        AddRow(layout, 2, "国家或地区", country);
        AddRow(layout, 3, "自动保存录像", autoSave);
        AddRow(layout, 4, "鼠标", cursorLimit);
        AddRow(layout, 5, "结束处理", flagOnWin);
        AddRow(layout, 6, "计数器", showCounter);
        AddRow(layout, 7, "计数器缩放", counterPixels);
        layout.Controls.Add(new Label {
            Text = "快捷键固定在“设置 → 快捷键”中查看。窗口、棋盘和计数器位置会自动保存。",
            AutoSize = true,
            ForeColor = SystemColors.GrayText,
            Anchor = AnchorStyles.Left
        }, 1, 8);

        var ok = new Button { Text = "确定", DialogResult = DialogResult.OK, AutoSize = true };
        var cancel = new Button { Text = "取消", DialogResult = DialogResult.Cancel, AutoSize = true };
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

    private static void AddRow(TableLayoutPanel layout, int row, string name, Control entry)
    {
        layout.Controls.Add(new Label { Text = name, AutoSize = true, Anchor = AnchorStyles.Left }, 0, row);
        entry.Anchor = AnchorStyles.Left | AnchorStyles.Right;
        layout.Controls.Add(entry, 1, row);
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        string value = country.Text.Trim();
        if (DialogResult == DialogResult.OK && value.Length != 0 &&
            !string.Equals(value, "XX", StringComparison.OrdinalIgnoreCase) && Countries.Code(value).Length == 0)
        {
            MessageBox.Show(this, "请选择国家或地区，或输入两位字母代码。", "游戏设置", MessageBoxButtons.OK);
            country.Focus();
            e.Cancel = true;
        }
        base.OnFormClosing(e);
    }

    internal void Store(GameSettings settings)
    {
        settings.Store(player.Text, race.Text, country.Text, (AutoSaveMode)autoSave.SelectedIndex,
            showCounter.Checked, cursorLimit.Checked, flagOnWin.Checked, (int)counterPixels.Value);
    }
}
