use crate::{
    config::{self, Settings, Text, LANGUAGES},
    dropdown::{self, Dropdown, ARROW_WIDTH},
    layout::{Box2, COUNTER_MAX, COUNTER_MIN},
    paint::{Align, Painter, INK, WHITE},
    view::{control_button, dialog_button, ButtonPointer},
};
use sdl3::{
    keyboard::{Keycode, Mod},
    VideoSubsystem,
};
use std::{collections::HashSet, ops::Range};
use unicode_segmentation::UnicodeSegmentation;

pub const SIZE: (u32, u32) = (680, 470);
const ROW_HEIGHT: i32 = 32;
const FIELD_LEFT: i32 = 250;
pub const FONT: i32 = 15;
const COUNTRY: usize = 3;
const AUTO_REPLAY: usize = 11;
const REPLAY_THRESHOLD: usize = 12;
const EDIT_ROWS: [usize; 6] = [1, 2, COUNTRY, 5, 10, REPLAY_THRESHOLD];
const OK: usize = 13;
const CANCEL: usize = 14;

#[derive(PartialEq, Eq)]
pub enum Outcome {
    Stay,
    Apply,
    Cancel,
}

#[derive(Default)]
struct Edit {
    value: String,
    anchor: usize,
    caret: usize,
    offset: i32,
    composition: Option<Composition>,
}

struct Composition {
    text: String,
    cursor: usize,
    end: usize,
}

fn text_byte(text: &str, index: i32) -> usize {
    text.char_indices()
        .nth(index.max(0) as usize)
        .map_or(text.len(), |(byte, _)| byte)
}

impl Edit {
    fn new(value: String) -> Self {
        Self {
            value,
            ..Self::default()
        }
    }

    fn selection(&self) -> Range<usize> {
        self.anchor.min(self.caret)..self.anchor.max(self.caret)
    }

    fn select_all(&mut self) {
        self.anchor = 0;
        self.caret = self.value.len();
    }

    fn move_to(&mut self, at: usize, extend: bool) {
        self.caret = at;
        if !extend {
            self.anchor = at;
        }
    }

    fn previous(&self, word: bool) -> usize {
        if word {
            self.value
                .unicode_word_indices()
                .take_while(|(start, _)| *start < self.caret)
                .last()
                .map_or(0, |(start, _)| start)
        } else {
            self.value
                .grapheme_indices(true)
                .take_while(|(start, _)| *start < self.caret)
                .last()
                .map_or(0, |(start, _)| start)
        }
    }

    fn next(&self, word: bool) -> usize {
        if word {
            self.value
                .unicode_word_indices()
                .find(|(start, _)| *start > self.caret)
                .map_or(self.value.len(), |(start, _)| start)
        } else {
            self.value
                .grapheme_indices(true)
                .find(|(start, _)| *start > self.caret)
                .map_or(self.value.len(), |(start, _)| start)
        }
    }

    fn replace(&mut self, range: Range<usize>, text: &str) {
        let mut caret = range.start + text.len();
        self.value.replace_range(range, text);
        if caret < self.value.len()
            && !self
                .value
                .grapheme_indices(true)
                .any(|(start, _)| start == caret)
        {
            caret = self
                .value
                .grapheme_indices(true)
                .find(|(start, _)| *start > caret)
                .map_or(self.value.len(), |(start, _)| start);
        }
        self.move_to(caret, false);
    }

    fn insert(&mut self, text: &str, numeric: bool) {
        self.composition = None;
        let range = self.selection();
        let units = crate::platform::text_units;
        let limit: usize = if numeric { 10 } else { 128 };
        let mut remaining =
            limit.saturating_sub(units(&self.value) - units(&self.value[range.clone()]));
        let accepted: String = text
            .graphemes(true)
            .filter(|part| {
                part.chars().all(|ch| {
                    if numeric {
                        ch.is_ascii_digit()
                    } else {
                        !ch.is_control()
                    }
                })
            })
            .take_while(|part| {
                let count = units(part);
                if count > remaining {
                    return false;
                }
                remaining -= count;
                true
            })
            .collect();
        if !accepted.is_empty() {
            self.replace(range, &accepted);
        }
    }

    fn set_composition(&mut self, text: String, start: i32, length: i32) {
        self.composition = (!text.is_empty()).then(|| {
            let cursor = if start < 0 {
                text.len()
            } else {
                text_byte(&text, start)
            };
            let end = if start < 0 {
                cursor
            } else {
                text_byte(&text, start.saturating_add(length.max(0)))
            };
            Composition { text, cursor, end }
        });
    }

    fn presentation(&self) -> (String, usize, Range<usize>, Option<Range<usize>>) {
        let range = self.selection();
        if let Some(composition) = &self.composition {
            let begin = range.start;
            let mut text = self.value.clone();
            text.replace_range(range, &composition.text);
            (
                text,
                begin + composition.cursor,
                begin + composition.cursor..begin + composition.end,
                Some(begin..begin + composition.text.len()),
            )
        } else {
            (self.value.clone(), self.caret, range, None)
        }
    }

    fn click(&mut self, x: i32, extend: bool, double_click: bool, measure: impl Fn(&str) -> i32) {
        let x = x + self.offset;
        let at = self
            .value
            .grapheme_indices(true)
            .find_map(|(start, grapheme)| {
                let before = measure(&self.value[..start]);
                let after = measure(&self.value[..start + grapheme.len()]);
                (x < (before + after + 1) / 2).then_some(start)
            })
            .unwrap_or(self.value.len());
        if double_click {
            if let Some((start, word)) = self
                .value
                .unicode_word_indices()
                .find(|(start, word)| (*start..=*start + word.len()).contains(&at))
            {
                self.anchor = start;
                self.caret = start + word.len();
                return;
            }
        }
        self.move_to(at, extend);
    }

    fn key(
        &mut self,
        key: Keycode,
        shift: bool,
        control: bool,
        numeric: bool,
        video: &VideoSubsystem,
    ) {
        let range = self.selection();
        match key {
            Keycode::A if control => self.select_all(),
            Keycode::C | Keycode::X if control && !range.is_empty() => {
                if video
                    .clipboard()
                    .set_clipboard_text(&self.value[range.clone()])
                    .is_ok()
                    && key == Keycode::X
                {
                    self.replace(range, "");
                }
            }
            Keycode::V if control => {
                if let Ok(text) = video.clipboard().clipboard_text() {
                    self.insert(&text, numeric);
                }
            }
            Keycode::Left | Keycode::Right => {
                let right = key == Keycode::Right;
                let target = if !range.is_empty() && !shift && !control {
                    if right {
                        range.end
                    } else {
                        range.start
                    }
                } else if right {
                    self.next(control)
                } else {
                    self.previous(control)
                };
                self.move_to(target, shift);
            }
            Keycode::Home => self.move_to(0, shift),
            Keycode::End => self.move_to(self.value.len(), shift),
            Keycode::Backspace | Keycode::Delete => {
                let range = if !range.is_empty() {
                    range
                } else if key == Keycode::Backspace {
                    self.previous(control)..self.caret
                } else {
                    self.caret..self.next(control)
                };
                self.replace(range, "");
            }
            _ => {}
        }
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Control {
    Confirm,
    Cancel,
    Step { row: usize, step: i32 },
    Checkbox(usize),
    Dropdown(usize),
    Option(usize),
}

pub struct Form {
    pub draft: Settings,
    auto_replay_checked: bool,
    edits: [Edit; 6],
    focus: usize,
    dropdown: Option<Dropdown>,
    pub dragging: bool,
    invalid_country: bool,
    pointer: ButtonPointer<Control>,
}

impl Form {
    pub fn new(draft: Settings) -> Self {
        let mut edits = [
            draft.player.clone(),
            draft.race.clone(),
            draft.country.clone(),
            draft.pixels[draft.level].to_string(),
            draft.counter_pixels.to_string(),
            draft.auto_replay.abs().to_string(),
        ]
        .map(Edit::new);
        edits[0].select_all();
        Self {
            auto_replay_checked: draft.auto_replay >= 0,
            draft,
            edits,
            focus: 1,
            dropdown: None,
            dragging: false,
            invalid_country: false,
            pointer: ButtonPointer::default(),
        }
    }

    pub fn edit_row(&self) -> Option<usize> {
        EDIT_ROWS.iter().position(|row| *row == self.focus)
    }

    pub fn composing(&self) -> bool {
        self.edit_row()
            .is_some_and(|index| self.edits[index].composition.is_some())
    }

    pub fn clear_composition(&mut self) {
        if let Some(index) = self.edit_row() {
            self.edits[index].composition = None;
        }
    }

    fn focus(&mut self, row: usize, select_all: bool) {
        self.clear_composition();
        self.focus = row;
        self.dropdown = None;
        if select_all {
            if let Some(index) = self.edit_row() {
                self.edits[index].select_all();
            }
        }
    }

    fn auto_save_options(&self) -> [&'static str; 3] {
        [
            self.draft.text(Text::AllResults),
            self.draft.text(Text::WinsOnly),
            self.draft.text(Text::Off),
        ]
    }

    fn open_dropdown(&mut self, browse: bool) {
        let (choices, selected) = match self.focus {
            0 => (LANGUAGES.to_vec(), Some(self.draft.lang)),
            6 => (self.auto_save_options().to_vec(), Some(self.draft.autosave)),
            COUNTRY => (
                country_matches(if browse { "" } else { &self.edits[2].value }),
                None,
            ),
            _ => return,
        };
        self.dropdown = Dropdown::new(choices, selected);
    }

    fn choose(&mut self, index: usize) {
        let Some(dropdown) = self.dropdown.take() else {
            return;
        };
        match self.focus {
            0 => self.draft.lang = index,
            6 => self.draft.autosave = index,
            COUNTRY => {
                let edit = &mut self.edits[2];
                edit.value = dropdown.label(index).into();
                edit.move_to(edit.value.len(), false);
                self.invalid_country = false;
            }
            _ => {}
        }
    }

    pub fn text(&mut self, text: &str) {
        let Some(index) = self.edit_row() else {
            return;
        };
        self.edits[index].insert(text, index >= 3);
        if self.focus == COUNTRY {
            self.country_changed();
        }
    }

    pub fn composition(&mut self, text: String, start: i32, length: i32) {
        if let Some(index) = self.edit_row() {
            if !text.is_empty() {
                self.dropdown = None;
            }
            self.edits[index].set_composition(text, start, length);
        }
    }

    fn country_changed(&mut self) {
        self.invalid_country = false;
        self.open_dropdown(false);
    }

    fn enter(&mut self) -> Outcome {
        if let Some(dropdown) = self.dropdown.as_ref() {
            let choice = dropdown.selected().or_else(|| {
                (self.focus == COUNTRY
                    && config::country_code(self.edits[2].value.trim()).is_none())
                .then_some(dropdown.first_visible())
            });
            if let Some(index) = choice {
                self.choose(index);
            } else {
                self.dropdown = None;
            }
            return Outcome::Stay;
        }
        match self.focus {
            0 | COUNTRY | 6 => {
                self.open_dropdown(true);
                Outcome::Stay
            }
            CANCEL => Outcome::Cancel,
            _ => Outcome::Apply,
        }
    }

    pub fn key(&mut self, key: Keycode, mods: Mod, video: &VideoSubsystem) -> Outcome {
        let shift = mods.intersects(Mod::LSHIFTMOD | Mod::RSHIFTMOD);
        let control = mods.intersects(Mod::LCTRLMOD | Mod::RCTRLMOD);
        if self.composing() {
            return Outcome::Stay;
        }
        match key {
            Keycode::Escape => {
                return if self.dropdown.take().is_some() {
                    Outcome::Stay
                } else {
                    Outcome::Cancel
                };
            }
            Keycode::Return | Keycode::KpEnter => {
                return self.enter();
            }
            Keycode::Tab => {
                if let Some(index) = self.dropdown.as_ref().and_then(Dropdown::selected) {
                    self.choose(index);
                }
                let step = if shift { CANCEL } else { 1 };
                let mut next = (self.focus + step) % (CANCEL + 1);
                if next == REPLAY_THRESHOLD && !self.auto_replay_checked {
                    next = (next + step) % (CANCEL + 1);
                }
                self.focus(next, true);
                return Outcome::Stay;
            }
            Keycode::Down | Keycode::Up | Keycode::PageDown | Keycode::PageUp => {
                let step = match key {
                    Keycode::Up => -1,
                    Keycode::PageUp => -6,
                    Keycode::PageDown => 6,
                    _ => 1,
                };
                if matches!(self.focus, 0 | COUNTRY | 6) {
                    if self.dropdown.is_none() {
                        self.open_dropdown(true);
                    }
                    if let Some(dropdown) = &mut self.dropdown {
                        dropdown.step(step);
                    }
                } else if matches!(self.focus, 5 | 10 | REPLAY_THRESHOLD) {
                    self.adjust_number(step.signum());
                }
                return Outcome::Stay;
            }
            Keycode::F4 if matches!(self.focus, 0 | COUNTRY | 6) => {
                if self.dropdown.take().is_none() {
                    self.open_dropdown(true);
                }
                return Outcome::Stay;
            }
            Keycode::Space if self.edit_row().is_none() => {
                match self.focus {
                    OK => return Outcome::Apply,
                    CANCEL => return Outcome::Cancel,
                    0 | 6 => self.open_dropdown(true),
                    _ => self.toggle(),
                }
                return Outcome::Stay;
            }
            _ => {}
        }
        if let Some(index) = self.edit_row() {
            let previous = (self.focus == COUNTRY).then(|| self.edits[index].value.clone());
            self.edits[index].key(key, shift, control, index >= 3, video);
            if previous.is_some_and(|value| value != self.edits[index].value) {
                self.country_changed();
            }
        }
        Outcome::Stay
    }

    fn toggle(&mut self) {
        let flag = match self.focus {
            4 => &mut self.draft.identity,
            7 => &mut self.draft.cursor_lock,
            8 => &mut self.draft.flag_win,
            9 => &mut self.draft.counter,
            AUTO_REPLAY => &mut self.auto_replay_checked,
            _ => return,
        };
        *flag = !*flag;
    }

    fn number(&self, index: usize) -> (i32, i32, i32) {
        let (fallback, min, max) = match index {
            3 => (self.draft.pixels[self.draft.level], 5, 255),
            4 => (self.draft.counter_pixels, COUNTER_MIN, COUNTER_MAX),
            _ => (self.draft.auto_replay.abs(), 0, 100),
        };
        let number = self.edits[index]
            .value
            .parse::<i64>()
            .unwrap_or(fallback as i64);
        (number.clamp(min as i64, max as i64) as i32, min, max)
    }

    fn adjust_number(&mut self, step: i32) {
        let Some(index) = self.edit_row() else {
            return;
        };
        let (value, min, max) = self.number(index);
        let edit = &mut self.edits[index];
        edit.value = (value + step).clamp(min, max).to_string();
        edit.select_all();
    }

    fn can_step(&self, row: usize, step: i32) -> bool {
        let (value, min, max) = self.number(if row == 5 { 3 } else { 4 });
        (min..=max).contains(&(value + step))
    }

    fn control_at(&self, point: (i32, i32), (width, height): (i32, i32)) -> Option<Control> {
        let (x, y) = point;
        if let Some(index) = self
            .dropdown
            .as_ref()
            .and_then(|drop| drop.item_at(field(self.focus, width), point))
        {
            return Some(Control::Option(index));
        }
        for (ok, control) in [(true, Control::Confirm), (false, Control::Cancel)] {
            if dialog_button(width, height, ok).contains(x, y) {
                return Some(control);
            }
        }
        for row in [5, 10] {
            for step in [-1, 1] {
                if step_button(row, width, step).contains(x, y) {
                    return Some(Control::Step { row, step });
                }
            }
        }
        for row in [4, 7, 8, 9, AUTO_REPLAY] {
            if checkbox_area(row, width).contains(x, y) {
                return Some(Control::Checkbox(row));
            }
        }
        for row in [0, COUNTRY, 6] {
            if dropdown::trigger_area(field(row, width), row == COUNTRY).contains(x, y) {
                return Some(Control::Dropdown(row));
            }
        }
        None
    }

    pub fn motion(&mut self, point: (i32, i32), size: (i32, i32)) -> bool {
        self.pointer.motion(self.control_at(point, size))
    }

    pub fn mouse_leave(&mut self) {
        self.pointer.motion(None);
    }

    pub fn cancel_pointer(&mut self) {
        self.pointer = ButtonPointer::default();
        self.dragging = false;
    }

    pub fn capturing(&self) -> bool {
        self.dragging || self.pointer.pressed.is_some()
    }

    pub fn release(&mut self, point: (i32, i32), size: (i32, i32)) -> Outcome {
        self.dragging = false;
        match self.pointer.release(self.control_at(point, size)) {
            Some(Control::Confirm) => Outcome::Apply,
            Some(Control::Cancel) => Outcome::Cancel,
            Some(Control::Step { row, step }) if self.can_step(row, step) => {
                self.focus(row, false);
                self.adjust_number(step);
                Outcome::Stay
            }
            _ => Outcome::Stay,
        }
    }

    pub fn click(
        &mut self,
        point: (i32, i32),
        size: (i32, i32),
        clicks: u8,
        shift: bool,
        measure: impl Fn(&str) -> i32,
    ) {
        let (x, y) = point;
        let (width, _) = size;
        let target = self.control_at(point, size);
        self.pointer.motion(target);
        match target {
            Some(Control::Option(index)) => {
                self.choose(index);
                self.motion(point, size);
                return;
            }
            Some(Control::Confirm | Control::Cancel) => {
                self.pointer.pressed = target;
                return;
            }
            Some(Control::Step { row, step }) => {
                self.dropdown = None;
                if self.can_step(row, step) {
                    self.pointer.pressed = target;
                }
                return;
            }
            Some(Control::Checkbox(row)) => {
                self.focus(row, false);
                self.toggle();
                return;
            }
            _ => {}
        }
        let mut row = y.saturating_sub(12) as usize / ROW_HEIGHT as usize;
        let was_open = self.dropdown.is_some() && self.focus == row;
        let prior_focus = self.focus;
        self.dropdown = None;
        if y < 12 || row > AUTO_REPLAY {
            return;
        }
        if row == AUTO_REPLAY {
            if !self.auto_replay_checked || !input_area(REPLAY_THRESHOLD, width).contains(x, y) {
                return;
            }
            row = REPLAY_THRESHOLD;
        } else if x < FIELD_LEFT {
            return;
        }
        if row != self.focus {
            self.focus(row, false);
        }
        match target {
            Some(Control::Dropdown(_)) => {
                if !was_open {
                    self.open_dropdown(true);
                }
            }
            _ => {
                if let Some(index) = self.edit_row() {
                    let inner = input_area(row, width).inset(4);
                    if input_area(row, width).contains(x, y) {
                        let edit = &mut self.edits[index];
                        let padding = edit_padding(inner.2, measure(&edit.value), index >= 3);
                        edit.click(
                            x - inner.0 - padding,
                            shift && prior_focus == row,
                            clicks > 1,
                            measure,
                        );
                        self.dragging = clicks <= 1;
                    }
                }
            }
        }
    }

    pub fn drag(&mut self, x: i32, width: i32, measure: impl Fn(&str) -> i32) {
        if self.dragging {
            if let Some(index) = self.edit_row() {
                let inner = input_area(self.focus, width).inset(4);
                let edit = &mut self.edits[index];
                let padding = edit_padding(inner.2, measure(&edit.value), index >= 3);
                edit.click(x - inner.0 - padding, true, false, measure);
            }
        }
    }

    pub fn wheel(&mut self, direction: i32) {
        if let Some(drop) = &mut self.dropdown {
            drop.scroll(direction);
        }
    }

    pub fn prepare(&mut self) -> bool {
        if config::country_code(&self.edits[2].value).is_none() {
            self.focus(COUNTRY, true);
            self.invalid_country = true;
            return false;
        }
        self.draft.player = config::clean_player(&self.edits[0].value);
        self.draft.race = config::clean(&self.edits[1].value);
        self.draft.country = config::clean(&self.edits[2].value);
        self.draft.pixels[self.draft.level] = self.number(3).0;
        self.draft.counter_pixels = self.number(4).0;
        let threshold = self.number(5).0;
        self.draft.auto_replay = if self.auto_replay_checked {
            threshold
        } else {
            -threshold
        };
        true
    }

    pub fn input_position(
        &mut self,
        width: i32,
        measure: impl Fn(&str) -> i32,
    ) -> Option<(Box2, i32)> {
        let index = self.edit_row()?;
        let inner = input_area(self.focus, width).inset(4);
        let edit = &mut self.edits[index];
        let (text, caret, _, _) = edit.presentation();
        let caret = measure(&text[..caret]);
        let text_width = measure(&text);
        let visible = (inner.2 - 1).max(0);
        edit.offset = edit
            .offset
            .clamp(0, (text_width - visible).max(0))
            .max(caret - visible)
            .min(caret);
        let padding = edit_padding(inner.2, text_width, index >= 3);
        Some((inner, padding + caret - edit.offset))
    }

    pub fn draw(&self, p: &Painter, width: i32, height: i32) {
        let cfg = &self.draft;
        p.fill(Box2(0, 0, width, height), 0xf5f5f5);
        let labels = [
            Text::Language,
            Text::Player,
            Text::Race,
            Text::Country,
            Text::IdentityBar,
            Text::TileSize,
            Text::AutoSave,
            Text::Mouse,
            Text::GameEnd,
            Text::Counter,
            Text::CounterScale,
        ];
        for (row, label) in labels.into_iter().enumerate() {
            p.text(
                Box2(
                    12,
                    12 + row as i32 * ROW_HEIGHT,
                    FIELD_LEFT - 20,
                    ROW_HEIGHT,
                ),
                cfg.text(label),
                FONT,
                Align::Left,
                INK,
            );
        }
        for (row, value) in [
            (0, LANGUAGES[cfg.lang]),
            (6, self.auto_save_options()[cfg.autosave]),
        ] {
            let rect = field(row, width);
            field_frame(p, rect, self.focus == row);
            self.draw_dropdown_arrow(p, rect, row);
            p.text(
                input_area(row, width).inset(4),
                value,
                FONT,
                Align::Left,
                INK,
            );
        }
        for (index, row) in EDIT_ROWS.into_iter().enumerate() {
            let rect = field(row, width);
            let input = input_area(row, width);
            let active = self.focus == row;
            if row == REPLAY_THRESHOLD && !self.auto_replay_checked {
                p.fill(input, 0xeeeeee);
                p.border(input, 0xb0b0b0);
                p.text(
                    input.inset(4),
                    &self.edits[index].value,
                    FONT,
                    Align::Center,
                    0x777777,
                );
                continue;
            }
            field_frame(p, if index >= 3 { input } else { rect }, active);
            draw_edit(p, input.inset(4), &self.edits[index], active, index >= 3);
            if row == COUNTRY {
                self.draw_dropdown_arrow(p, rect, row);
            }
            if matches!(row, 5 | 10) {
                for (step, title) in [(-1, "−"), (1, "+")] {
                    control_button(
                        p,
                        step_button(row, width, step),
                        title,
                        self.pointer
                            .state(Control::Step { row, step }, self.can_step(row, step)),
                        false,
                    );
                }
            }
        }
        for (row, checked, title) in [
            (4, cfg.identity, Text::ShowIdentity),
            (7, cfg.cursor_lock, Text::LockCursor),
            (8, cfg.flag_win, Text::FlagOnWin),
            (9, cfg.counter, Text::ShowCounter),
        ] {
            let y = 12 + row as i32 * ROW_HEIGHT;
            let rect = Box2(FIELD_LEFT, y + 8, 15, 15);
            self.draw_checkbox_hover(p, row, width);
            field_frame(p, rect, self.focus == row);
            if checked {
                p.checkmark(rect);
            }
            p.text(
                Box2(FIELD_LEFT + 21, y, width - FIELD_LEFT - 33, ROW_HEIGHT),
                cfg.text(title),
                FONT,
                Align::Left,
                INK,
            );
        }
        let replay_y = 12 + AUTO_REPLAY as i32 * ROW_HEIGHT;
        let checkbox = Box2(12, replay_y + 8, 15, 15);
        self.draw_checkbox_hover(p, AUTO_REPLAY, width);
        field_frame(p, checkbox, self.focus == AUTO_REPLAY);
        if self.auto_replay_checked {
            p.checkmark(checkbox);
        }
        p.text(
            Box2(33, replay_y, FIELD_LEFT - 43, ROW_HEIGHT),
            cfg.text(Text::AutoReplay),
            FONT,
            Align::Left,
            INK,
        );
        let threshold = input_area(REPLAY_THRESHOLD, width);
        p.text(
            Box2(threshold.0 + threshold.2 + 6, replay_y, 30, ROW_HEIGHT),
            "%",
            FONT,
            Align::Left,
            if self.auto_replay_checked {
                INK
            } else {
                0x777777
            },
        );
        if self.invalid_country {
            p.text(
                Box2(12, height - 74, width - 24, 23),
                cfg.text(Text::InvalidCountry),
                FONT,
                Align::Left,
                0x9a251d,
            );
        }
        for (ok, key, control) in [
            (true, Text::Ok, Control::Confirm),
            (false, Text::Cancel, Control::Cancel),
        ] {
            control_button(
                p,
                dialog_button(width, height, ok),
                cfg.text(key),
                self.pointer.state(control, true),
                ok != (self.focus == CANCEL),
            );
        }
        if let Some(drop) = &self.dropdown {
            let hovered = match self.pointer.hovered {
                Some(Control::Option(index)) => Some(index),
                _ => None,
            };
            drop.draw(
                p,
                field(self.focus, width),
                FONT,
                hovered,
                |index, choice| match self.focus {
                    0 => index == cfg.lang,
                    6 => index == cfg.autosave,
                    _ => choice.eq_ignore_ascii_case(self.edits[2].value.trim()),
                },
            );
        }
    }

    fn draw_dropdown_arrow(&self, p: &Painter, rect: Box2, row: usize) {
        dropdown::draw_trigger(
            p,
            rect,
            row == COUNTRY,
            self.dropdown.is_some() && self.focus == row,
            self.pointer.hovered == Some(Control::Dropdown(row)),
        );
    }

    fn draw_checkbox_hover(&self, p: &Painter, row: usize, width: i32) {
        if self.pointer.hovered == Some(Control::Checkbox(row)) {
            p.fill(checkbox_area(row, width).inset(2), 0xe4eef8);
        }
    }
}

fn country_matches(query: &str) -> Vec<&'static str> {
    let query = query.trim().to_lowercase();
    let mut seen = HashSet::new();
    let mut matches = Vec::new();
    if query.is_empty() {
        for (code, name) in config::countries() {
            if seen.insert(code) {
                matches.push((0, name));
            }
        }
    } else {
        for (code, name) in config::countries() {
            let normalized = name.to_lowercase();
            let order = if code.eq_ignore_ascii_case(&query) || normalized == query {
                0
            } else if normalized.starts_with(&query) {
                1
            } else if normalized.contains(&query) {
                2
            } else {
                continue;
            };
            matches.push((order, name));
        }
    }
    matches.sort_unstable();
    matches.into_iter().map(|(_, name)| name).collect()
}

fn field(row: usize, width: i32) -> Box2 {
    let row = if row == REPLAY_THRESHOLD {
        AUTO_REPLAY
    } else {
        row
    };
    Box2(
        FIELD_LEFT,
        15 + row as i32 * ROW_HEIGHT,
        width - FIELD_LEFT - 12,
        26,
    )
}

fn input_area(row: usize, width: i32) -> Box2 {
    let Box2(x, y, w, h) = field(row, width);
    match row {
        0 | COUNTRY | 6 => Box2(x, y, w - ARROW_WIDTH, h),
        5 | 10 => Box2(x + 26, y, 68, h),
        REPLAY_THRESHOLD => Box2(x, y, 130, h),
        _ => Box2(x, y, w, h),
    }
}

fn step_button(row: usize, width: i32, step: i32) -> Box2 {
    let Box2(x, y, _, height) = field(row, width);
    Box2(x + if step < 0 { 0 } else { 94 }, y, 26, height)
}

fn checkbox_area(row: usize, width: i32) -> Box2 {
    let y = 12 + row as i32 * ROW_HEIGHT;
    if row == AUTO_REPLAY {
        Box2(12, y, FIELD_LEFT - 12, ROW_HEIGHT)
    } else {
        Box2(FIELD_LEFT, y, width - FIELD_LEFT - 12, ROW_HEIGHT)
    }
}

fn field_frame(p: &Painter, area: Box2, active: bool) {
    p.fill(area, WHITE);
    p.border(area, if active { 0x467eac } else { 0xb0b0b0 });
}

fn edit_padding(field_width: i32, text_width: i32, centered: bool) -> i32 {
    if centered {
        (field_width - text_width).max(0) / 2
    } else {
        0
    }
}

fn draw_edit(p: &Painter, inner: Box2, edit: &Edit, active: bool, centered: bool) {
    let (text, caret, selection, composition) = edit.presentation();
    let origin = inner.0 + edit_padding(inner.2, p.measure(&text, FONT), centered) - edit.offset;
    let position = |at| origin + p.measure(&text[..at], FONT);
    let highlight = |range: Range<usize>| {
        let start = position(range.start).clamp(inner.0, inner.0 + inner.2);
        let end = position(range.end).clamp(inner.0, inner.0 + inner.2);
        (start, end - start)
    };
    if active && !selection.is_empty() {
        let (x, width) = highlight(selection);
        p.fill(Box2(x, inner.1, width, inner.3), 0xd5e9ff);
    }
    p.text_at(inner, &text, FONT, origin, INK);
    if let Some(range) = composition {
        let (x, width) = highlight(range);
        p.fill(Box2(x, inner.1 + inner.3 - 1, width, 1), 0x467eac);
    }
    if active {
        let x = position(caret).clamp(inner.0, inner.0 + inner.2 - 1);
        p.fill(Box2(x, inner.1 + 2, 1, inner.3 - 4), INK);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn enter_opens_and_confirms_settings_dropdowns() {
        let root =
            std::env::temp_dir().join(format!("metasweeper-mini-test-{}", std::process::id()));
        let mut form = Form::new(Settings::read(&root).unwrap());
        form.draft.lang = 0;
        form.draft.autosave = 0;

        for row in [0, 6] {
            form.focus(row, true);
            assert!(form.enter() == Outcome::Stay);
            let dropdown = form.dropdown.as_mut().unwrap();
            dropdown.step(1);
            assert!(form.enter() == Outcome::Stay);
            assert!(form.dropdown.is_none());
        }
        assert_eq!(form.draft.lang, 1);
        assert_eq!(form.draft.autosave, 1);

        form.edits[2].value = "中国".into();
        form.focus(COUNTRY, true);
        assert!(form.enter() == Outcome::Stay);
        let dropdown = form.dropdown.as_mut().unwrap();
        dropdown.step(1);
        let selected = dropdown.label(dropdown.selected().unwrap());
        assert_ne!(selected, "中国");
        assert!(form.enter() == Outcome::Stay);
        assert_eq!(form.edits[2].value, selected);
        assert!(form.dropdown.is_none());

        form.focus(OK, false);
        assert!(form.enter() == Outcome::Apply);
    }

    #[test]
    fn settings_buttons_require_release_over_the_pressed_control() {
        let root =
            std::env::temp_dir().join(format!("metasweeper-mini-test-{}", std::process::id()));
        let mut form = Form::new(Settings::read(&root).unwrap());
        let size = (SIZE.0 as i32, SIZE.1 as i32);
        let button_point = |Box2(x, y, _, _)| (x + 1, y + 1);
        let confirm = button_point(dialog_button(size.0, size.1, true));
        let cancel = button_point(dialog_button(size.0, size.1, false));
        form.click(confirm, size, 1, false, |_| 0);
        assert!(form.capturing());
        assert!(form.release(cancel, size) == Outcome::Stay);
        assert!(!form.capturing());
        form.click(confirm, size, 1, false, |_| 0);
        assert!(form.release(confirm, size) == Outcome::Apply);

        form.edits[3].value = "5".into();
        let decrease = button_point(step_button(5, size.0, -1));
        let increase = button_point(step_button(5, size.0, 1));
        form.click(decrease, size, 1, false, |_| 0);
        assert!(!form.capturing());
        form.click(increase, size, 1, false, |_| 0);
        assert_eq!(form.number(3).0, 5);
        form.release(increase, size);
        assert_eq!(form.number(3).0, 6);
    }

    #[test]
    fn auto_restart_form_preserves_signed_thresholds_including_zero() {
        let root =
            std::env::temp_dir().join(format!("metasweeper-mini-test-{}", std::process::id()));
        let mut settings = Settings::read(&root).unwrap();
        settings.country.clear();
        for value in [-30, 0, 30, 100] {
            settings.auto_replay = value;
            let mut form = Form::new(settings.clone());
            assert_eq!(form.auto_replay_checked, value >= 0);
            assert_eq!(form.number(5).0, value.abs());
            assert!(form.prepare());
            assert_eq!(form.draft.auto_replay, value);
            form.focus(AUTO_REPLAY, false);
            form.toggle();
            assert!(form.prepare());
            assert_eq!(form.draft.auto_replay, -value);
        }
    }

    #[test]
    fn replaces_a_selected_grapheme_and_renders_composition_in_place() {
        let mut edit = Edit::new("Aか\u{3099}B".into());
        edit.move_to(edit.value.len(), false);
        edit.move_to(edit.previous(false), false);
        edit.move_to(edit.previous(false), true);
        assert_eq!(&edit.value[edit.selection()], "か\u{3099}");
        edit.set_composition("中国".into(), 1, 1);
        let (preview, cursor, selection, underline) = edit.presentation();
        assert_eq!(preview, "A中国B");
        assert_eq!(&preview[cursor..selection.end], "国");
        assert_eq!(&preview[underline.unwrap()], "中国");
        edit.insert("日本", false);
        assert_eq!(edit.value, "A日本B");
        assert!(edit.composition.is_none());
    }

    #[test]
    fn finds_country_names_and_codes_from_shared_table() {
        assert!(country_matches("中国").contains(&"中国"));
        assert!(country_matches("jp").contains(&"Japan"));
        assert!(country_matches("öster").contains(&"Österreich"));
        assert!(country_matches("unknown country").is_empty());
    }

    #[test]
    fn filters_numeric_paste_without_discarding_a_selection_on_invalid_input() {
        let mut edit = Edit::new("20".into());
        edit.select_all();
        edit.insert("abc", true);
        assert_eq!(edit.value, "20");
        assert_eq!(edit.selection(), 0..2);
        edit.insert("3a5", true);
        assert_eq!(edit.value, "35");
        assert_eq!(edit.selection(), 2..2);
    }
}
