use crate::{config::{Settings, Text, LANGUAGES}, core::Round, layout::{Box2, Layout, FOOTER, MENU, PRESETS},
            paint::{Align, Art, Painter, CANVAS, INK, WHITE}};

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Action { Restart, Level(usize), Save, Open, Quit, Settings, Shortcuts, Counter, Identity, Instructions, License }

pub const MENUS: [Text; 4] = [Text::GameMenu, Text::SettingsMenu, Text::ViewMenu, Text::HelpMenu];
pub const ENTRIES: [&[(Action, Text, &str)]; 4] = [
    &[(Action::Restart, Text::Restart, "F2 / N"), (Action::Level(0), Text::Beginner, "1 / B"),
      (Action::Level(1), Text::Intermediate, "2 / I"), (Action::Level(2), Text::Expert, "3 / E"),
      (Action::Save, Text::SaveReplayMenu, "Ctrl+S"), (Action::Open, Text::OpenReplayFolder, "W"),
      (Action::Quit, Text::Quit, "Ctrl+X")],
    &[(Action::Settings, Text::GameSettings, "S"), (Action::Shortcuts, Text::Shortcuts, "Z")],
    &[(Action::Counter, Text::Counter, "/"), (Action::Identity, Text::IdentityBar, "Ctrl+I")],
    &[(Action::Instructions, Text::Instructions, ""), (Action::License, Text::License, "")],
];

#[derive(Default)]
pub struct Menu {
    pub open: Option<usize>,
    pub top: Vec<(Box2, usize)>,
    pub options: Vec<(Box2, Choice)>,
}

#[derive(Clone, Copy)]
pub enum Choice { Command(Action), Menu(usize) }

pub fn game(p: &Painter, art: &mut Art, settings: &Settings, round: &Round, layout: Layout,
            menu: &mut Menu, pointer: (i32, i32), face_pressed: bool, size: (i32, i32)) {
    let (width, height) = size;
    let (rows, cols, mines) = PRESETS[settings.level];
    let grid = layout.grid(settings.level, size, settings.identity);
    let status = layout.status(width);
    p.fill(Box2(0, 0, width, height), CANVAS);
    p.bevel(Box2(0, MENU, width, height - MENU - if settings.identity { FOOTER } else { 0 }),
            layout.outer_edge, true);
    p.bevel(status, layout.inner_edge, false);
    p.bevel(grid.inset(-layout.inner_edge), layout.inner_edge, false);
    let visual = round.mouse_visual();
    let active = (visual != 0 && grid.contains(pointer.0, pointer.1))
        .then(|| ((pointer.0 - grid.0) / layout.tile, (pointer.1 - grid.1) / layout.tile));
    for row in 0..rows {
        for col in 0..cols {
            let mut tile = round.cells[(row * cols + col) as usize] as usize;
            if tile == 10 && active.is_some_and(|(x, y)| {
                let radius = i32::from(visual == 2);
                (x - col).abs() <= radius && (y - row).abs() <= radius
            }) { tile = 0; }
            art.sprite(p, grid.0 + col * layout.tile, grid.1 + row * layout.tile, layout.tile, tile);
        }
    }
    let y = status.1 + layout.status_inset;
    art.number(p, status.0 + layout.status_inset, y, layout.digit, layout.sprite, round.remaining(mines, settings.flag_win));
    art.number(p, status.0 + status.2 - layout.status_inset - 3 * layout.digit, y,
               layout.digit, layout.sprite, round.seconds() as u32);
    let face = match round.phase() { 2 => 3, 3 => 2, _ if face_pressed => 4, _ if visual != 0 => 1, _ => 0 };
    art.sprite(p, (width - layout.sprite) / 2, y, layout.sprite, 17 + face);
    if settings.identity {
        let name_width = width - if round.country.is_empty() { 0 } else { 57 };
        p.text(Box2(6, height - FOOTER, name_width - 12, FOOTER), &round.player, 16, Align::Center, 0x242424);
        if !round.country.is_empty() {
            p.text(Box2(width - 57, height - 36, 51, 31), &round.country, 16, Align::Center, INK);
        }
    }
    draw_menu(p, settings, round, menu, size, pointer);
}

fn draw_menu(p: &Painter, settings: &Settings, round: &Round, menu: &mut Menu, size: (i32, i32), pointer: (i32, i32)) {
    let (width, height) = size;
    p.fill(Box2(0, 0, width, MENU), WHITE);
    menu.top.clear();
    menu.options.clear();
    let widths = MENUS.map(|label| p.measure(settings.text(label), 16) + 20);
    let mut overflow = None;
    let mut x = 0;
    for (i, w) in widths.into_iter().enumerate() {
        let area = Box2(x, 0, w, MENU);
        let reserve = if i < 3 && widths[i+1..].iter().sum::<i32>() + w + x > width { 24 } else { 0 };
        if x + w + reserve > width {
            overflow = Some(i);
            break;
        }
        menu.top.push((area, i));
        if menu.open == Some(i) || area.contains(pointer.0, pointer.1) {
            p.fill(area, 0xdce9f4);
        }
        p.text(area, settings.text(MENUS[i]), 16, Align::Center, INK);
        x += w;
    }
    if overflow.is_some() {
        let area = Box2(width - 23, 0, 23, MENU);
        if menu.open == Some(4) { p.fill(area, 0xdce9f4); }
        p.text(area, "»", 16, Align::Center, INK);
        menu.top.push((area, 4));
    }
    let Some(section) = menu.open else { return };
    let origin = menu.top.iter().find(|(_, i)| *i == section).map(|(area, _)| area.0).unwrap_or(width - 23);
    let choices: Vec<_> = if section < MENUS.len() {
        ENTRIES[section].iter().map(|(action, text, key)| (Choice::Command(*action), settings.text(*text), *key)).collect()
    } else {
        (overflow.unwrap_or(0)..MENUS.len()).map(|i| (Choice::Menu(i), settings.text(MENUS[i]), "›")).collect()
    };
    let panel_width = choices.iter().map(|(_, text, key)| p.measure(text, 15) + p.measure(key, 14) + 58)
        .max().unwrap_or(75).min(width);
    let x = origin.min(width - panel_width).max(0);
    let step = 26.min((height - MENU - 4) / choices.len().max(1) as i32).max(1);
    p.fill(Box2(x, MENU, panel_width, choices.len() as i32 * step + 4), WHITE);
    p.border(Box2(x, MENU, panel_width, choices.len() as i32 * step + 4), 0x888888);
    for (index, (choice, title, keys)) in choices.into_iter().enumerate() {
        let r = Box2(x + 2, MENU + 2 + index as i32 * step, panel_width - 4, step);
        menu.options.push((r, choice));
        if r.contains(pointer.0, pointer.1) { p.fill(r, 0xdce9f4); }
        let (checked, available) = match choice {
            Choice::Command(Action::Level(level)) => (level == settings.level, true),
            Choice::Command(Action::Counter) => (settings.counter, true),
            Choice::Command(Action::Identity) => (settings.identity, true),
            Choice::Command(Action::Save) => (false, round.ended() && round.timing_valid),
            _ => (false, true),
        };
        if checked { p.text(Box2(r.0 + 2, r.1, 18, step), "✓", 14, Align::Center, INK); }
        let key_width = p.measure(keys, 14);
        let color = if available { INK } else { 0x777777 };
        p.text(Box2(r.0 + 22, r.1, (r.2 - key_width - 32).max(5), step), title, 15, Align::Left, color);
        p.text(Box2(r.0 + r.2 - key_width - 5, r.1, key_width, step), keys, 14, Align::Right, color);
    }
}

pub fn counter(p: &Painter, settings: &Settings, round: &Round, width: i32, height: i32) {
    let size = (15 * settings.counter_pixels / 27).max(12);
    let labels = [settings.text(Text::GameMode), "rtime", "Est Rtime", "3bv", "3bv/s", "zini", "ops", "isls",
                  "left", "right", "double", "stnb", "ioe", "thrp", "corr", "path", "pluck"];
    let values = round.counter_rows(settings.text(Text::Standard));
    p.fill(Box2(0, 0, width, height), 0xf5f5f5);
    p.text(Box2(0, 0, width - 22, 37), settings.text(Text::Counter), size, Align::Center, INK);
    p.text(Box2(width - 24, 0, 24, 37), "×", 16, Align::Center, INK);
    let table = Box2(8, 37, width - 17, height - 45);
    let divider = (table.2 * 35 / 100).max(p.measure(labels[0], size) + 9).min(table.2 / 2);
    p.fill(table, WHITE);
    p.border(table, 0x808080);
    p.fill(Box2(table.0 + divider, table.1, 1, table.3), 0xd3d3d3);
    for (i, (label, value)) in labels.into_iter().zip(values).enumerate() {
        let y = table.1 + i as i32 * table.3 / 17;
        let row = table.1 + (i as i32 + 1) * table.3 / 17 - y;
        if i > 0 { p.fill(Box2(table.0 + 1, y, table.2 - 2, 1), 0xe0e0e0); }
        p.text(Box2(table.0 + 4, y, divider - 5, row), label, size, Align::Left, 0x242424);
        p.text(Box2(table.0 + divider + 6, y, table.2 - divider - 8, row), &value, size, Align::Left, INK);
    }
}

pub const ROW: i32 = 32;
const FIELD_LEFT: i32 = 250;

pub fn settings(p: &Painter, cfg: &Settings, focus: usize, select_all: bool, drop: Option<usize>, inputs: &[String; 3], width: i32, height: i32) {
    p.fill(Box2(0, 0, width, height), 0xf5f5f5);
    let labels = [Text::Language, Text::Player, Text::Race, Text::Country, Text::IdentityBar, Text::TileSize,
                  Text::AutoSave, Text::Mouse, Text::GameEnd, Text::Counter, Text::CounterScale];
    for (i, label) in labels.into_iter().enumerate() {
        p.text(Box2(12, 12 + i as i32 * ROW, FIELD_LEFT - 20, ROW), cfg.text(label), 15, Align::Left, INK);
    }
    let options = [cfg.text(Text::AllResults), cfg.text(Text::WinsOnly), cfg.text(Text::Off)];
    for (row, value) in [(0, LANGUAGES[cfg.lang]), (1, &inputs[0]), (2, &inputs[1]), (3, &inputs[2]), (6, options[cfg.autosave])] {
        let area = field(row, width);
        p.fill(area, if focus == row && select_all { 0xd5e9ff } else { WHITE });
        p.border(area, if row == focus { 0x467eac } else { 0xb0b0b0 });
        p.text(area.inset(5), value, 15, Align::Left, INK);
        if row == 0 || row == 6 {
            p.text(Box2(area.0 + area.2 - 24, area.1, 22, area.3), "▾", 15, Align::Center, INK);
        }
        if row == focus && (1..=3).contains(&row) && !select_all {
            let caret_x = (area.0 + 5 + p.measure(value, 15)).min(area.0 + area.2 - 4);
            p.fill(Box2(caret_x, area.1 + 5, 1, area.3 - 10), INK);
        }
    }
    for (row, checked, title) in [
        (4, cfg.identity, Text::ShowIdentity), (7, cfg.cursor_lock, Text::LockCursor),
        (8, cfg.flag_win, Text::FlagOnWin), (9, cfg.counter, Text::ShowCounter),
    ] {
        let y = 12 + row * ROW;
        let rect = Box2(FIELD_LEFT, y + 8, 15, 15);
        p.fill(rect, WHITE);
        p.border(rect, if focus == row as usize { 0x467eac } else { 0x888888 });
        if checked { p.text(rect, "✓", 13, Align::Center, INK); }
        p.text(Box2(FIELD_LEFT + 21, y, width - FIELD_LEFT - 33, ROW), cfg.text(title), 15, Align::Left, INK);
    }
    for (row, value) in [(5, cfg.pixels[cfg.level]), (10, cfg.counter_pixels)] {
        let rect = field(row, width);
        let r = Box2(rect.0, rect.1, 120, rect.3);
        p.fill(r, WHITE);
        p.border(r, if row == focus { 0x467eac } else { 0xb0b0b0 });
        p.text(Box2(r.0, r.1, 26, r.3), "−", 17, Align::Center, INK);
        p.text(Box2(r.0 + 25, r.1, 70, r.3), &value.to_string(), 15, Align::Center, INK);
        p.text(Box2(r.0 + 94, r.1, 26, r.3), "+", 17, Align::Center, INK);
    }
    for (ok, key) in [(true, Text::Ok), (false, Text::Cancel)] {
        button(p, dialog_button(width, height, ok), cfg.text(key));
    }
    if let Some(row) = drop {
        let titles = if row == 0 { &LANGUAGES[..] } else { &options[..] };
        let rect = field(row, width);
        for (i, title) in titles.iter().enumerate() {
            let r = Box2(rect.0, rect.1 + rect.3 + i as i32 * 25, rect.2, 25);
            p.fill(r, if (row == 0 && i == cfg.lang) || (row == 6 && i == cfg.autosave) { 0xdce9f4 } else { WHITE });
            p.border(r, 0xcccccc);
            p.text(r.inset(4), title, 15, Align::Left, INK);
        }
    }
}

pub fn field(row: usize, width: i32) -> Box2 {
    Box2(FIELD_LEFT, 15 + row as i32 * ROW, width - FIELD_LEFT - 12, 26)
}

pub fn dialog_button(width: i32, height: i32, ok: bool) -> Box2 {
    Box2(width - if ok { 202 } else { 104 }, height - 42, 92, 29)
}

pub fn button(p: &Painter, area: Box2, title: &str) {
    p.fill(area, 0xebebeb);
    p.border(area, 0x999999);
    p.text(area, title, 15, Align::Center, INK);
}

pub fn message(p: &Painter, text: &str, confirm: &str, width: i32, height: i32) {
    p.fill(Box2(0, 0, width, height), 0xf5f5f5);
    p.paragraph(Box2(14, 12, width - 28, height - 62), text, 15, INK);
    button(p, dialog_button(width, height, false), confirm);
}
