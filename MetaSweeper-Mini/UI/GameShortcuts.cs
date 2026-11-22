using System;
using System.Collections.Generic;
using System.Windows.Forms;

internal sealed class GameShortcuts
{
    private readonly Dictionary<Keys, ToolStripMenuItem> commands = new Dictionary<Keys, ToolStripMenuItem>();
    private readonly List<ToolStripMenuItem> menuItems = new List<ToolStripMenuItem>();

    internal void Bind(ToolStripMenuItem menu, params string[] ids)
    {
        var active = new List<string>(ids.Length);
        foreach (string id in ids)
        {
            string name = ShortcutCatalog.Key(id);
            Keys key = Parse(name);
            if (key == Keys.None || commands.ContainsKey(key))
                continue;
            commands.Add(key, menu);
            active.Add(name);
        }
        menu.ShortcutKeyDisplayString = string.Join(" / ", active);
        if (active.Count != 0)
            menuItems.Add(menu);
    }

    internal bool Invoke(Keys key)
    {
        ToolStripMenuItem menu;
        if (!commands.TryGetValue(key, out menu) || !menu.Enabled)
            return false;
        menu.PerformClick();
        return true;
    }

    internal void Show(IWin32Window owner)
    {
        var lines = new List<string>(menuItems.Count);
        foreach (ToolStripMenuItem item in menuItems)
            lines.Add(item.Text.TrimEnd('…') + "　" + item.ShortcutKeyDisplayString);
        MessageBox.Show(owner, string.Join(Environment.NewLine, lines), "快捷键", MessageBoxButtons.OK);
    }

    internal static Keys Parse(string sequence)
    {
        if (string.IsNullOrWhiteSpace(sequence))
            return Keys.None;
        string[] parts = sequence.Split('+');
        Keys modifier = Keys.None;
        for (int i = 0; i < parts.Length - 1; i++)
        {
            switch (parts[i].Trim().ToLowerInvariant())
            {
                case "ctrl": case "control": modifier |= Keys.Control; break;
                case "alt": modifier |= Keys.Alt; break;
                case "shift": modifier |= Keys.Shift; break;
                default: return Keys.None;
            }
        }
        string code = parts[parts.Length - 1].Trim();
        if (code.Length == 1 && code[0] >= '0' && code[0] <= '9')
            return modifier | (Keys)((int)Keys.D0 + code[0] - '0');
        switch (code.ToLowerInvariant())
        {
            case "/": return modifier | Keys.OemQuestion;
            case "-": return modifier | Keys.OemMinus;
            case "=": return modifier | Keys.Oemplus;
            case "pgup": return modifier | Keys.PageUp;
            case "pgdown": return modifier | Keys.PageDown;
            case "esc": return modifier | Keys.Escape;
            case "del": return modifier | Keys.Delete;
            case "ins": return modifier | Keys.Insert;
        }
        if (code.Length == 0 || code.IndexOf(',') >= 0)
            return Keys.None;
        try
        {
            Keys key = (Keys)new KeysConverter().ConvertFromInvariantString(code);
            return key == Keys.None || (key & Keys.Modifiers) != 0 ? Keys.None : modifier | key;
        }
        catch (NotSupportedException) { return Keys.None; }
        catch (FormatException) { return Keys.None; }
        catch (ArgumentException) { return Keys.None; }
    }
}
