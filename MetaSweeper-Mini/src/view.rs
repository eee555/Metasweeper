use crate::{
    config::{Settings, Text},
    core::Round,
    layout::{Box2, CounterLayout, FullscreenMode, Layout, COUNTER_ROWS, FOOTER, MENU, PRESETS},
    paint::{Align, Art, Painter, CANVAS, INK, WHITE},
};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Action {
    Restart,
    Level(usize),
    Save,
    Open,
    Quit,
    Settings,
    Shortcuts,
    CursorLock,
    Counter,
    Identity,
    Fullscreen,
    Instructions,
    License,
}

pub const MENUS: [Text; 4] = [
    Text::GameMenu,
    Text::SettingsMenu,
    Text::ViewMenu,
    Text::HelpMenu,
];
pub const ENTRIES: [&[(Action, Text, &str)]; 4] = [
    &[
        (Action::Restart, Text::Restart, "F2 / N"),
        (Action::Level(0), Text::Beginner, "1 / B"),
        (Action::Level(1), Text::Intermediate, "2 / I"),
        (Action::Level(2), Text::Expert, "3 / E"),
        (Action::Save, Text::SaveReplayMenu, "Ctrl+S"),
        (Action::Open, Text::OpenReplayFolder, "W"),
        (Action::Quit, Text::Quit, "Ctrl+X"),
    ],
    &[
        (Action::Settings, Text::GameSettings, "S"),
        (Action::Shortcuts, Text::Shortcuts, "Z"),
        (Action::CursorLock, Text::LockCursor, "F4"),
    ],
    &[
        (Action::Counter, Text::Counter, "/"),
        (Action::Identity, Text::IdentityBar, "Ctrl+I"),
        (Action::Fullscreen, Text::Fullscreen, "F11"),
    ],
    &[
        (Action::Instructions, Text::Instructions, ""),
        (Action::License, Text::License, ""),
    ],
];

#[derive(Default)]
pub struct Menu {
    pub open: Option<usize>,
    pub top: Vec<(Box2, usize)>,
    pub options: Vec<(Box2, Choice)>,
}

#[derive(Clone, Copy)]
pub enum Choice {
    Command(Action),
    Menu(usize),
}

pub fn game(
    p: &Painter,
    art: &mut Art,
    settings: &Settings,
    round: &Round,
    layout: Layout,
    menu: &mut Menu,
    pointer: (i32, i32),
    face_pressed: bool,
    size: (i32, i32),
) {
    let (width, height) = size;
    let grid = layout.grid(settings.level, size, settings.identity);
    let status = layout.status(width);
    art.board_background(p, size, layout, settings.level, settings.identity);
    board_cells(p, art, round, layout.tile, grid, pointer);
    draw_status(p, art, settings, round, layout, status, face_pressed);
    if settings.identity {
        let name_width = width - if round.country.is_empty() { 0 } else { 57 };
        p.text(
            Box2(6, height - FOOTER, name_width - 12, FOOTER),
            &round.player,
            16,
            Align::Center,
            0x242424,
        );
        if !round.country.is_empty() {
            p.text(
                Box2(width - 57, height - 36, 51, 31),
                &round.country,
                16,
                Align::Center,
                INK,
            );
        }
    }
    draw_menu(p, settings, round, menu, size, pointer);
}

pub fn fullscreen(
    p: &Painter,
    art: &mut Art,
    settings: &Settings,
    round: &Round,
    layout: Layout,
    pointer: (i32, i32),
    face_pressed: bool,
    size: (i32, i32),
    mode: FullscreenMode,
    counter: &mut FullscreenCounter,
    full: bool,
) -> Option<Vec<Box2>> {
    let regions = layout.fullscreen_regions(settings.level, size, mode);
    let mut areas = Vec::new();
    if full {
        p.fill(Box2(0, 0, size.0, size.1), INK);
        p.fill(regions.frame, CANVAS);
        p.bevel(regions.frame, layout.outer_edge, true);
        p.bevel(
            regions.grid.inset(-layout.inner_edge),
            layout.inner_edge,
            false,
        );
        areas.push(Box2(0, 0, size.0, size.1));
        board_cells(p, art, round, layout.tile, regions.grid, pointer);
        if let Some(status) = regions.status {
            p.bevel(status, layout.inner_edge, false);
            draw_status(p, art, settings, round, layout, status, face_pressed);
        }
    }
    if let Some(area) = regions.counter {
        let values = round.counter_rows(settings.text(Text::Standard));
        if let Some(changed) = counter.draw(p, settings, &values, area, regions.counter_scale, full)
        {
            areas.extend(changed);
        }
    }
    (!areas.is_empty()).then_some(areas)
}

fn draw_counter(p: &Painter, settings: &Settings, values: &[String], area: Box2, scale: i32) {
    let layout = CounterLayout::new(scale);
    let title = settings.text(Text::Counter);
    let title_line = layout.title_line();
    p.fill(area, 0xf2f2f2);
    p.text(
        Box2(area.0 + 16, area.1 + 12, (area.2 - 32).max(1), title_line),
        title,
        layout.title_px,
        Align::Center,
        INK,
    );
    let table = Box2(
        area.0 + 16,
        area.1 + layout.table_top(),
        (area.2 - 32).max(1),
        layout.row * COUNTER_ROWS as i32 + 2,
    );
    p.fill(table, WHITE);
    p.border(table, 0x888888);
    let divider = 1 + (table.2 - 2) * layout.columns.0 / (layout.columns.0 + layout.columns.1);
    let labels = [
        settings.text(Text::GameMode),
        "rtime",
        "Est Rtime",
        "3bv",
        "3bv/s",
        "zini",
        "ops",
        "isls",
        "left",
        "right",
        "double",
        "stnb",
        "ioe",
        "thrp",
        "corr",
        "path",
        "pluck",
    ];
    for (i, (label, value)) in labels.into_iter().zip(values).enumerate() {
        let (label_area, value_area) = counter_cells(table, divider, i);
        if i + 1 < COUNTER_ROWS {
            let y = label_area.1 + label_area.3;
            let right = table.0 + table.2 - 1;
            for x in (table.0 + 1..right).step_by(6) {
                p.fill(Box2(x, y, (right - x).min(4), 1), 0xc0c0c0);
            }
        }
        p.counter_text(counter_text_cell(label_area), label, layout.table_px, INK);
        p.counter_text(counter_text_cell(value_area), value, layout.table_px, INK);
    }
}

fn counter_text_cell(area: Box2) -> Box2 {
    Box2(area.0 + 3, area.1, (area.2 - 6).max(1), area.3)
}

#[derive(Default)]
pub struct FullscreenCounter {
    painted: Option<FullscreenCounterContents>,
}

struct FullscreenCounterContents {
    area: Box2,
    scale: i32,
    values: Vec<String>,
}

impl FullscreenCounter {
    pub fn invalidate(&mut self) {
        self.painted = None;
    }

    fn draw(
        &mut self,
        p: &Painter,
        settings: &Settings,
        values: &[String],
        area: Box2,
        scale: i32,
        full: bool,
    ) -> Option<Vec<Box2>> {
        let layout = CounterLayout::new(scale);
        let table = Box2(
            area.0 + 16,
            area.1 + layout.table_top(),
            (area.2 - 32).max(1),
            layout.row * COUNTER_ROWS as i32 + 2,
        );
        let divider = 1 + (table.2 - 2) * layout.columns.0 / (layout.columns.0 + layout.columns.1);
        if !full {
            if let Some(painted) = self
                .painted
                .as_mut()
                .filter(|painted| painted.area == area && painted.scale == scale)
            {
                let mut regions = Vec::new();
                for (index, (previous, value)) in painted.values.iter().zip(values).enumerate() {
                    if previous == value {
                        continue;
                    }
                    let (_, value_area) = counter_cells(table, divider, index);
                    p.fill(value_area, WHITE);
                    p.counter_text(counter_text_cell(value_area), value, layout.table_px, INK);
                    regions.push(value_area);
                }
                painted.values = values.to_vec();
                return (!regions.is_empty()).then_some(regions);
            }
        }
        draw_counter(p, settings, values, area, scale);
        self.painted = Some(FullscreenCounterContents {
            area,
            scale,
            values: values.to_vec(),
        });
        None
    }
}

fn draw_status(
    p: &Painter,
    art: &mut Art,
    settings: &Settings,
    round: &Round,
    layout: Layout,
    status: Box2,
    face_pressed: bool,
) {
    let mines = PRESETS[settings.level].2;
    let y = status.1 + layout.status_inset;
    art.number(
        p,
        status.0 + layout.status_inset,
        y,
        layout.digit,
        layout.sprite,
        round.remaining(mines, settings.flag_win),
    );
    art.number(
        p,
        status.0 + status.2 - layout.status_inset - 3 * layout.digit,
        y,
        layout.digit,
        layout.sprite,
        round.seconds() as u32,
    );
    let face = match round.phase() {
        2 => 3,
        3 => 2,
        _ if face_pressed => 4,
        _ if round.mouse_visual() != 0 => 1,
        _ => 0,
    };
    art.sprite(
        p,
        status.0 + (status.2 - layout.sprite) / 2,
        y,
        layout.sprite,
        17 + face,
    );
}

fn board_cells(
    p: &Painter,
    art: &mut Art,
    round: &Round,
    tile: i32,
    grid: Box2,
    pointer: (i32, i32),
) {
    let visual = round.mouse_visual();
    let cols = grid.2 / tile;
    let rows = grid.3 / tile;
    let active = (visual != 0 && grid.contains(pointer.0, pointer.1))
        .then(|| ((pointer.0 - grid.0) / tile, (pointer.1 - grid.1) / tile));
    for row in 0..rows {
        for col in 0..cols {
            let mut sprite = round.cells[(row * cols + col) as usize] as usize;
            if sprite == 10
                && active.is_some_and(|(x, y)| {
                    let radius = i32::from(visual == 2);
                    (x - col).abs() <= radius && (y - row).abs() <= radius
                })
            {
                sprite = 0;
            }
            art.sprite(p, grid.0 + col * tile, grid.1 + row * tile, tile, sprite);
        }
    }
}

fn draw_menu(
    p: &Painter,
    settings: &Settings,
    round: &Round,
    menu: &mut Menu,
    size: (i32, i32),
    pointer: (i32, i32),
) {
    let (width, height) = size;
    p.fill(Box2(0, 0, width, MENU), WHITE);
    menu.top.clear();
    menu.options.clear();
    let widths = MENUS.map(|label| p.measure(settings.text(label), 16) + 20);
    let mut overflow = None;
    let mut x = 0;
    for (i, w) in widths.into_iter().enumerate() {
        let area = Box2(x, 0, w, MENU);
        let reserve = if i < 3 && widths[i + 1..].iter().sum::<i32>() + w + x > width {
            24
        } else {
            0
        };
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
        if menu.open == Some(4) {
            p.fill(area, 0xdce9f4);
        }
        let y = area.1 + (area.3 - 8) / 2;
        p.chevron(area.0 + 6, y);
        p.chevron(area.0 + 12, y);
        menu.top.push((area, 4));
    }
    let Some(section) = menu.open else { return };
    let origin = menu
        .top
        .iter()
        .find(|(_, i)| *i == section)
        .map(|(area, _)| area.0)
        .unwrap_or(width - 23);
    let choices: Vec<_> = if section < MENUS.len() {
        ENTRIES[section]
            .iter()
            .map(|(action, text, key)| (Choice::Command(*action), settings.text(*text), *key))
            .collect()
    } else {
        (overflow.unwrap_or(0)..MENUS.len())
            .map(|i| (Choice::Menu(i), settings.text(MENUS[i]), ""))
            .collect()
    };
    let key_width = |choice, keys: &str| {
        if matches!(choice, Choice::Menu(_)) {
            5
        } else {
            p.measure(keys, 14)
        }
    };
    let panel_width = choices
        .iter()
        .map(|(choice, text, key)| p.measure(text, 15) + key_width(*choice, key) + 58)
        .max()
        .unwrap_or(75)
        .min(width);
    let x = origin.min(width - panel_width).max(0);
    let step = 26
        .min((height - MENU - 4) / choices.len().max(1) as i32)
        .max(1);
    p.fill(
        Box2(x, MENU, panel_width, choices.len() as i32 * step + 4),
        WHITE,
    );
    p.border(
        Box2(x, MENU, panel_width, choices.len() as i32 * step + 4),
        0x888888,
    );
    for (index, (choice, title, keys)) in choices.into_iter().enumerate() {
        let r = Box2(x + 2, MENU + 2 + index as i32 * step, panel_width - 4, step);
        menu.options.push((r, choice));
        if r.contains(pointer.0, pointer.1) {
            p.fill(r, 0xdce9f4);
        }
        let (checked, available) = match choice {
            Choice::Command(Action::Level(level)) => (level == settings.level, true),
            Choice::Command(Action::Counter) => (settings.counter, true),
            Choice::Command(Action::CursorLock) => (settings.cursor_lock, true),
            Choice::Command(Action::Identity) => (settings.identity, true),
            Choice::Command(Action::Save) => (false, round.ended() && round.timing_valid),
            _ => (false, true),
        };
        if checked {
            p.checkmark(Box2(r.0 + 2, r.1, 18, step));
        }
        let key_width = key_width(choice, keys);
        let color = if available { INK } else { 0x777777 };
        p.text(
            Box2(r.0 + 22, r.1, (r.2 - key_width - 32).max(5), step),
            title,
            15,
            Align::Left,
            color,
        );
        let key_x = r.0 + r.2 - key_width - 5;
        if matches!(choice, Choice::Menu(_)) {
            if step >= 8 {
                p.chevron(key_x, r.1 + (step - 8) / 2);
            }
        } else {
            p.text(
                Box2(key_x, r.1, key_width, step),
                keys,
                14,
                Align::Right,
                color,
            );
        }
    }
}

#[derive(Default)]
pub struct Counter {
    painted: Option<CounterContents>,
}

struct CounterContents {
    geometry: (i32, i32, i32),
    values: Vec<String>,
}

impl Counter {
    pub fn invalidate(&mut self) {
        self.painted = None;
    }

    pub fn draw(
        &mut self,
        p: &Painter,
        settings: &Settings,
        values: Vec<String>,
        width: i32,
        height: i32,
        close: bool,
    ) -> Option<Vec<Box2>> {
        let layout = CounterLayout::new(settings.counter_pixels);
        let table = Box2(
            16,
            layout.table_top(),
            width - 32,
            (height - layout.table_top() - 14 - layout.table_px).max(3),
        );
        let divider = 1 + (table.2 - 2) * layout.columns.0 / (layout.columns.0 + layout.columns.1);
        let geometry = (width, height, settings.counter_pixels);
        if let Some(painted) = self
            .painted
            .as_mut()
            .filter(|painted| painted.geometry == geometry)
        {
            let mut regions = Vec::new();
            for (index, (previous, value)) in painted.values.iter().zip(&values).enumerate() {
                if previous == value {
                    continue;
                }
                let (_, area) = counter_cells(table, divider, index);
                p.fill(area, WHITE);
                p.counter_text(text_cell(area), value, layout.table_px, INK);
                regions.push(area);
            }
            painted.values = values;
            return Some(regions);
        }

        draw_counter_table(
            p,
            settings,
            (width, height),
            close,
            table,
            divider,
            layout,
            &values,
        );
        self.painted = Some(CounterContents { geometry, values });
        None
    }
}

fn counter_cells(table: Box2, divider: i32, index: usize) -> (Box2, Box2) {
    let y = table.1 + 1 + index as i32 * (table.3 - 2) / COUNTER_ROWS as i32;
    let bottom = table.1 + 1 + (index as i32 + 1) * (table.3 - 2) / COUNTER_ROWS as i32;
    let height = (bottom - y - i32::from(index + 1 < COUNTER_ROWS)).max(0);
    (
        Box2(table.0 + 1, y, divider - 1, height),
        Box2(table.0 + divider + 1, y, table.2 - divider - 2, height),
    )
}

fn text_cell(Box2(x, y, width, height): Box2) -> Box2 {
    Box2(x + 3, y, width - 6, height)
}

fn draw_counter_table(
    p: &Painter,
    settings: &Settings,
    (width, height): (i32, i32),
    close: bool,
    table: Box2,
    divider: i32,
    layout: CounterLayout,
    values: &[String],
) {
    let labels = [
        settings.text(Text::GameMode),
        "rtime",
        "Est Rtime",
        "3bv",
        "3bv/s",
        "zini",
        "ops",
        "isls",
        "left",
        "right",
        "double",
        "stnb",
        "ioe",
        "thrp",
        "corr",
        "path",
        "pluck",
    ];
    p.fill(Box2(0, 0, width, height), 0xf2f2f2);
    let title_line = layout.title_line();
    p.text(
        Box2(16, 12 + layout.heading - title_line, width - 32, title_line),
        settings.text(Text::Counter),
        layout.title_px,
        Align::Center,
        INK,
    );
    if close {
        for offset in 0..8 {
            p.fill(Box2(width - 16 + offset, 14 + offset, 2, 2), INK);
            p.fill(Box2(width - 9 - offset, 14 + offset, 2, 2), INK);
        }
    }
    p.fill(table, WHITE);
    p.border(table, 0xa0a0a0);
    let bottom = table.1 + table.3 - 1;
    let right = table.0 + table.2 - 1;
    for y in (table.1 + 1..bottom).step_by(6) {
        p.fill(Box2(table.0 + divider, y, 1, (bottom - y).min(4)), 0xc0c0c0);
    }
    for (i, (label, value)) in labels.into_iter().zip(values).enumerate() {
        let (label_area, value_area) = counter_cells(table, divider, i);
        if i + 1 < COUNTER_ROWS {
            let y = label_area.1 + label_area.3;
            for x in (table.0 + 1..right).step_by(6) {
                p.fill(Box2(x, y, (right - x).min(4), 1), 0xc0c0c0);
            }
        }
        p.counter_text(text_cell(label_area), label, layout.table_px, INK);
        p.counter_text(text_cell(value_area), value, layout.table_px, INK);
    }
}

pub fn dialog_button(width: i32, height: i32, ok: bool) -> Box2 {
    Box2(width - if ok { 202 } else { 104 }, height - 42, 92, 29)
}

pub fn fullscreen_button(width: i32, height: i32, mode: FullscreenMode) -> Box2 {
    let index = match mode {
        FullscreenMode::Board => 0,
        FullscreenMode::Status => 1,
        FullscreenMode::Counter => 2,
    };
    let button_width = (width - 36) / 3;
    Box2(
        12 + index * (button_width + 6),
        (height - 34) / 2,
        button_width,
        34,
    )
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
