mod config;
mod core;
mod layout;
mod paint;
mod view;

use config::{Settings, Text};
use core::{Replay, Round};
use layout::{Box2, Layout, MENU};
use paint::{Align, Art, Buffer, INK, WHITE};
use sdl3::{
    event::{Event, WindowEvent},
    keyboard::{Keycode, Mod},
    mouse::MouseButton,
    rect::Rect,
    video::{HitTestResult, Window},
    EventPump, Sdl, VideoSubsystem,
};
use std::{
    env, fs,
    path::{Path, PathBuf},
    process::Command,
    sync::mpsc::{self, Receiver, Sender},
    thread,
    time::{Duration, Instant},
};
use view::{Action, Choice, Menu};

struct Display {
    window: Window,
    buffer: Buffer,
    dirty: bool,
}

impl Display {
    fn new(window: Window) -> Self {
        Self { window, buffer: Buffer::default(), dirty: true }
    }

    fn pixels(&self) -> (i32, i32) {
        let (w, h) = self.window.size_in_pixels();
        (w as i32, h as i32)
    }

    fn point(&self, x: f32, y: f32) -> (i32, i32) {
        let (w, h) = self.window.size();
        let (pw, ph) = self.pixels();
        ((x * pw as f32 / w.max(1) as f32).floor() as i32,
         (y * ph as f32 / h.max(1) as f32).floor() as i32)
    }

    fn logical(&self, x: i32, y: i32) -> (i32, i32) {
        let (w, h) = self.window.size();
        let (pw, ph) = self.pixels();
        ((x as f64 * w as f64 / pw.max(1) as f64).round() as i32,
         (y as f64 * h as f64 / ph.max(1) as f64).round() as i32)
    }

    fn draw(&mut self, events: &EventPump, draw: impl FnOnce(&paint::Painter, i32, i32)) -> Result<(), String> {
        if !self.dirty { return Ok(()); }
        self.dirty = false;
        self.buffer.present(&self.window, events, draw)
    }
}

enum Panel {
    Settings { draft: Box<Settings>, inputs: [String; 3], focus: usize, select: bool, drop: Option<usize> },
    Save { path: String, replay: Replay, overwrite: bool, select: bool },
    Message { text: String },
}

struct Dialog {
    display: Display,
    panel: Panel,
}

struct Job {
    replay: Replay,
    path: Option<PathBuf>,
}

struct App {
    sdl: Sdl,
    video: VideoSubsystem,
    main: Display,
    counter: Option<Display>,
    dialog: Option<Dialog>,
    wayland: bool,
    settings: Settings,
    root: PathBuf,
    round: Round,
    last_saved_round: bool,
    jobs: Sender<Job>,
    replies: Receiver<Result<(), String>>,
    errors: Vec<String>,
    reference: i32,
    layout: Layout,
    window_size_request: Option<(i32, i32)>,
    resized_at: Option<Instant>,
    pointer: (i32, i32),
    held: u8,
    restart_pressed: bool,
    cursor_released: bool,
    confinement: bool,
    menu: Menu,
    art: Art,
    quit: bool,
    refresh_every: Duration,
    next_update: Instant,
}

impl App {
    fn new(root: PathBuf, mut settings: Settings, jobs: Sender<Job>, replies: Receiver<Result<(), String>>) -> Result<Self, String> {
        sdl3::hint::set("SDL_APP_ID", "org.metasweeper.Mini");
        let sdl = sdl3::init().map_err(|e| e.to_string())?;
        let video = sdl.video().map_err(|e| e.to_string())?;
        let wayland = video.current_video_driver() == "wayland";
        let available = video.displays().ok().and_then(|ds| ds.first().copied())
            .and_then(|display| display.get_usable_bounds().ok())
            .map(|b| (b.width() as i32 - 20, b.height() as i32 - 55)).unwrap_or((1920, 1020));
        let requested = settings.pixels[settings.level];
        let reference = requested.min(Layout::fit(requested, settings.level, settings.identity, available).tile);
        settings.pixels[settings.level] = reference;
        let layout = Layout::new(reference, reference);
        let size = layout.size(settings.level, settings.identity);
        let mut builder = video.window(settings.text(Text::Title), size.0 as u32, size.1 as u32);
        builder.resizable().high_pixel_density();
        if let Some((x, y)) = settings.position.filter(|_| !wayland) { builder.position(x, y); }
        else { builder.position_centered(); }
        let window = builder.build().map_err(|e| e.to_string())?;
        let round = Round::new(&settings);
        let mut app = Self {
            sdl, video, main: Display::new(window), counter: None, dialog: None, wayland,
            root, settings, round, last_saved_round: false, jobs, replies, errors: Vec::new(),
            layout, reference, window_size_request: None, resized_at: None,
            pointer: (-1,-1), held: 0, restart_pressed: false, cursor_released: false,
            confinement: false, menu: Menu::default(), art: Art::new(), quit: false,
            refresh_every: Duration::from_millis(16), next_update: Instant::now(),
        };
        app.resize_main(reference);
        if app.settings.counter { app.show_counter()?; }
        app.update_refresh_rate();
        Ok(app)
    }

    fn resize_main(&mut self, tile: i32) {
        self.release_cursor();
        let (level, footer) = (self.settings.level, self.settings.identity);
        let (display_w, display_h) = self.main.window.get_display().ok()
            .and_then(|display| display.get_usable_bounds().ok())
            .map(|r| self.main.point(r.width() as f32, r.height() as f32))
            .unwrap_or((1920, 1020));
        let target = tile.min(Layout::fit(self.reference, level, footer,
            (display_w - 16, display_h - 48)).tile);
        self.layout = Layout::new(target, self.reference);
        self.settings.pixels[level] = target;
        let min = Layout::new(5, self.reference).size(level, footer);
        let (min_x, min_y) = self.main.logical(min.0, min.1);
        let _ = self.main.window.set_minimum_size(min_x.max(1) as u32, min_y.max(1) as u32);
        let desired = self.layout.size(level, footer);
        let logical = self.main.logical(desired.0, desired.1);
        self.resized_at = None;
        self.window_size_request = Some(logical);
        if self.main.window.size() != (logical.0 as u32, logical.1 as u32) {
            let _ = self.main.window.set_size(logical.0.max(1) as u32, logical.1.max(1) as u32);
        }
        self.main.dirty = true;
    }

    fn user_resize(&mut self) {
        self.release_cursor();
        let size = self.main.window.size();
        let size = (size.0 as i32, size.1 as i32);
        if self.window_size_request != Some(size) {
            self.window_size_request = None;
            self.layout = Layout::fit(self.reference, self.settings.level, self.settings.identity, self.main.pixels());
            self.settings.pixels[self.settings.level] = self.layout.tile;
            self.resized_at = Some(Instant::now());
        }
        self.main.dirty = true;
    }

    fn update_refresh_rate(&mut self) {
        let window = self.counter.as_ref().map(|s| &s.window).unwrap_or(&self.main.window);
        let rate = window.get_display().ok().and_then(|display| display.get_mode().ok())
            .map(|mode| mode.refresh_rate).filter(|rate| *rate >= 20.0).unwrap_or(60.0);
        self.refresh_every = Duration::from_secs_f32(1.0 / rate.clamp(20.0, 360.0));
    }

    fn show_counter(&mut self) -> Result<(), String> {
        if self.counter.is_some() { return Ok(()); }
        let scale = self.settings.counter_pixels as f64 / 27.0;
        let width = (256.0 * scale).round() as u32;
        let row = (33.0 * scale).round().max(19.0) as u32;
        let height = row * 17 + (48.0 * scale).round() as u32;
        let height = height.min(self.main.window.get_display().ok()
            .and_then(|d| d.get_usable_bounds().ok()).map(|b| b.height()).unwrap_or(1100));
        let mut builder = self.video.window(self.settings.text(Text::Counter), width, height);
        builder.borderless();
        builder.set_window_flags(builder.window_flags() | sdl3_sys::video::SDL_WINDOW_UTILITY.0 as u32);
        if !self.wayland {
            let (x, y) = self.main.window.position();
            let left = self.main.window.get_display().ok().and_then(|d| d.get_usable_bounds().ok()).map(|r| r.x).unwrap_or(0);
            let x = if x - width as i32 - 9 >= left { x - width as i32 - 9 }
                else { x + self.main.window.size().0 as i32 + 9 };
            let (x, y) = self.settings.counter_position.unwrap_or((x, y + 10));
            builder.position(x, y);
        }
        let mut window = builder.build().map_err(|e| e.to_string())?;
        unsafe { sdl3_sys::video::SDL_SetWindowParent(window.raw(), self.main.window.raw()); }
        let _ = window.set_hit_test(move |point| {
            if point.y < 37 && point.x < width as i32 - 24 { HitTestResult::Draggable }
            else { HitTestResult::Normal }
        });
        self.counter = Some(Display::new(window));
        self.update_refresh_rate();
        Ok(())
    }

    fn persist(&mut self) {
        if let Err(e) = self.settings.save(&self.root) {
            self.errors.push(format!("{}\n{e}", self.settings.text(Text::SettingsSaveError)));
        }
    }

    fn open_dialog(&mut self, title: &'static str, panel: Panel, size: (u32, u32)) -> Result<(), String> {
        self.cancel_input();
        let window = self.video.window(title, size.0, size.1).position_centered()
            .build().map_err(|e| e.to_string())?;
        unsafe {
            sdl3_sys::video::SDL_SetWindowParent(window.raw(), self.main.window.raw());
            sdl3_sys::video::SDL_SetWindowModal(window.raw(), true);
        }
        if !matches!(panel, Panel::Message { .. }) { self.video.text_input().start(&window); }
        self.dialog = Some(Dialog { display: Display::new(window), panel });
        Ok(())
    }

    fn close_dialog(&mut self) {
        if let Some(dialog) = self.dialog.take() {
            self.video.text_input().stop(&dialog.display.window);
        }
    }

    fn action(&mut self, action: Action) -> Result<(), String> {
        let settings = &self.settings;
        match action {
            Action::Restart | Action::Level(_) => {
                self.cancel_input();
                self.cursor_released = false;
                if let Action::Level(level) = action {
                    self.settings.level = level;
                    self.resize_main(self.layout.tile);
                }
                self.round = Round::new(&self.settings);
                self.last_saved_round = false;
            }
            Action::Save if self.round.ended() && self.round.timing_valid => {
                match self.round.replay(settings.level) {
                    Ok(replay) => {
                        let path = self.root.join("replay").join(format!("{}.evf", replay.name));
                        self.open_dialog(settings.text(Text::SaveReplayTitle),
                            Panel::Save { path: path.to_string_lossy().into_owned(), replay, overwrite: false, select: false }, (570, 120))?;
                    }
                    Err(e) => self.errors.push(format!("{}\n{e}", settings.text(Text::ReplayGenerationError))),
                }
            }
            Action::Save => {}
            Action::Open => {
                let root = self.root.join("replay");
                if let Err(e) = fs::create_dir_all(&root).and_then(|_| open_directory(&root)) {
                    self.errors.push(format!("{}\n{e}", settings.text(Text::ReplayFolderError)));
                }
            }
            Action::Quit => self.quit = true,
            Action::Settings => {
                let draft = Box::new(settings.clone());
                let inputs = [draft.player.clone(), draft.race.clone(), draft.country.clone()];
                self.open_dialog(settings.text(Text::GameSettings),
                    Panel::Settings { draft, inputs, focus: 1, select: true, drop: None }, (680, 430))?;
            }
            Action::Counter => {
                self.settings.counter = self.counter.is_none();
                if self.settings.counter { self.show_counter()?; }
                else { self.counter = None; self.update_refresh_rate(); }
                self.persist();
            }
            Action::Identity => {
                self.settings.identity = !self.settings.identity;
                self.resize_main(self.layout.tile);
                self.persist();
            }
            Action::Shortcuts | Action::Instructions | Action::License => {
                let text = match action {
                    Action::Shortcuts => view::ENTRIES.iter().flat_map(|group| group.iter())
                        .filter(|(_,_,key)| !key.is_empty())
                        .map(|(_, id, key)| format!("{}    {key}", settings.text(*id)))
                        .collect::<Vec<_>>().join("\n"),
                    Action::Instructions => format!("{}\n\n{}", settings.text(Text::ClickHelp), settings.text(Text::WindowHelp)),
                    _ => include_str!("../../obj/ms-toollib/LICENSE").into(),
                };
                let title = match action {
                    Action::Shortcuts => Text::Shortcuts, Action::Instructions => Text::Instructions, _ => Text::License,
                };
                self.open_dialog(settings.text(title), Panel::Message { text }, (515, 360))?;
            }
        }
        self.main.dirty = true;
        if let Some(counter) = &mut self.counter { counter.dirty = true; }
        Ok(())
    }

    fn commit_dialog(&mut self) -> Result<(), String> {
        let Some(dialog) = &mut self.dialog else { return Ok(()) };
        match &mut dialog.panel {
            Panel::Settings { draft, inputs, .. } => {
                if config::country_code(&inputs[2]).is_none() {
                    let title = draft.text(Text::GameSettings);
                    let text = draft.text(Text::InvalidCountry);
                    let _ = sdl3::messagebox::show_simple_message_box(
                        sdl3::messagebox::MessageBoxFlag::WARNING, title, text, &dialog.display.window);
                    return Ok(());
                }
                draft.player = config::clean_player(&inputs[0]);
                draft.race = config::clean(&inputs[1]);
                draft.country = config::clean(&inputs[2]);
            }
            Panel::Save { path, overwrite, .. } => {
                let target = save_path(&self.root, path);
                if target.is_file() && !*overwrite { *overwrite = true; dialog.display.dirty = true; return Ok(()); }
            }
            Panel::Message { .. } => {}
        }
        let dialog = self.dialog.take().unwrap();
        self.video.text_input().stop(&dialog.display.window);
        match dialog.panel {
            Panel::Settings { draft, .. } => {
                let pixels = self.settings.pixels[self.settings.level];
                let footer = self.settings.identity;
                let counter_pixels = self.settings.counter_pixels;
                self.settings = *draft;
                let next = self.settings.pixels[self.settings.level];
                if next != pixels || footer != self.settings.identity { self.resize_main(next); }
                let _ = self.main.window.set_title(self.settings.text(Text::Title));
                self.round.set_identity(&self.settings);
                self.cursor_released = false;
                if !self.settings.counter || counter_pixels != self.settings.counter_pixels { self.counter = None; }
                if self.settings.counter { self.show_counter()?; }
                if let Some(counter) = &mut self.counter {
                    let _ = counter.window.set_title(self.settings.text(Text::Counter));
                    counter.dirty = true;
                }
                self.update_refresh_rate();
                self.persist();
            }
            Panel::Save { path, replay, .. } => {
                if !path.trim().is_empty() {
                    let path = save_path(&self.root, &path);
                    let _ = self.jobs.send(Job { replay, path: Some(path) });
                }
            }
            Panel::Message { .. } => {}
        }
        self.main.dirty = true;
        self.sync_cursor();
        Ok(())
    }

    fn dialog_key(&mut self, key: Keycode, mods: Mod) -> Result<(), String> {
        if key == Keycode::Escape { self.close_dialog(); self.sync_cursor(); return Ok(()); }
        if key == Keycode::Return || key == Keycode::KpEnter { return self.commit_dialog(); }
        let control = ctrl(mods);
        let Some(dialog) = &mut self.dialog else { return Ok(()) };
        match &mut dialog.panel {
            Panel::Settings { draft, inputs, focus, select, drop } => {
                if key == Keycode::Tab {
                    *focus = (*focus + if mods.intersects(Mod::LSHIFTMOD | Mod::RSHIFTMOD) { 10 } else { 1 }) % 11;
                    *select = true;
                    *drop = None;
                } else if (1..=3).contains(focus) {
                    edit_text(&mut inputs[*focus - 1], select, key, control,
                        if control && key == Keycode::V { self.video.clipboard().clipboard_text().ok() } else { None }, 128);
                } else if matches!(key, Keycode::Left | Keycode::Right | Keycode::Up | Keycode::Down | Keycode::Space) {
                    adjust(draft, *focus, if matches!(key, Keycode::Left | Keycode::Up) { -1 } else { 1 });
                }
            }
            Panel::Save { path, select, overwrite, .. } => {
                edit_text(path, select, key, control,
                    if control && key == Keycode::V { self.video.clipboard().clipboard_text().ok() } else { None }, 2048);
                *overwrite = false;
            }
            Panel::Message { .. } => {}
        }
        dialog.display.dirty = true;
        Ok(())
    }

    fn dialog_click(&mut self, x: f32, y: f32) -> Result<(), String> {
        let Some(dialog) = &mut self.dialog else { return Ok(()) };
        let (x, y) = dialog.display.point(x, y);
        let (width, height) = dialog.display.pixels();
        if let Panel::Settings { draft, focus, select, drop, .. } = &mut dialog.panel {
            if let Some(row) = drop.take() {
                let Box2(left, y0, w, h) = view::field(row, width);
                let count = if row == 0 { 5 } else { 3 };
                if Box2(left, y0 + h, w, 25 * count).contains(x, y) {
                    let i = ((y - y0 - h) / 25) as usize;
                    if row == 0 { draft.lang = i; } else { draft.autosave = i; }
                    dialog.display.dirty = true;
                    return Ok(());
                }
            }
            let row = ((y - 12) / view::ROW) as usize;
            if y >= 12 && row < 11 {
                *select = row != *focus;
                *focus = row;
                let field = view::field(row, width);
                match row {
                    0 | 6 if x >= field.0 => *drop = Some(row),
                    4 | 7 | 8 | 9 if x >= field.0 => adjust(draft, row, 1),
                    5 | 10 if (field.0..field.0+120).contains(&x) => {
                        adjust(draft, row, if x < field.0 + 26 { -1 } else { 1 });
                    }
                    _ => {}
                }
                dialog.display.dirty = true;
                return Ok(());
            }
        }
        if matches!(dialog.panel, Panel::Message { .. }) {
            if view::dialog_button(width, height, false).contains(x, y) { self.close_dialog(); }
        } else if view::dialog_button(width, height, true).contains(x, y) {
            self.commit_dialog()?;
        } else if view::dialog_button(width, height, false).contains(x, y) {
            self.close_dialog();
        }
        Ok(())
    }

    fn release_cursor(&mut self) {
        if !self.confinement { return; }
        let _ = self.main.window.set_mouse_rect(None);
        self.main.window.set_mouse_grab(false);
        self.confinement = false;
    }

    fn sync_cursor(&mut self) {
        if self.round.phase() != 1 || !self.settings.cursor_lock || self.cursor_released
            || self.dialog.is_some() || self.resized_at.is_some()
            || unsafe { sdl3_sys::keyboard::SDL_GetKeyboardFocus() } != self.main.window.raw() {
            self.release_cursor();
            return;
        }
        if self.confinement { return; }
        let r = self.grid();
        let (x, y) = self.main.logical(r.0, r.1);
        let (w, h) = self.main.logical(r.2, r.3);
        if self.main.window.set_mouse_rect(Some(Rect::new(x, y, w as u32, h as u32))).is_ok()
            && self.main.window.set_mouse_grab(true) {
            self.confinement = true;
            // SDL can confirm an X11 grab. A Wayland constraint may still be pending.
            if !self.wayland && self.main.window.mouse_grab() { self.round.cursor_limited = true; }
        } else {
            let _ = self.main.window.set_mouse_rect(None);
        }
    }

    fn replay_point(&self, x: i32, y: i32) -> (usize, usize) {
        let grid = self.grid();
        let tile = self.layout.tile as usize;
        if grid.contains(x, y) {
            ((x - grid.0) as usize * 16 / tile, (y - grid.1) as usize * 16 / tile)
        } else {
            (grid.2 as usize * 16 / tile, grid.3 as usize * 16 / tile)
        }
    }

    fn grid(&self) -> Box2 {
        self.layout.grid(self.settings.level, self.main.pixels(), self.settings.identity)
    }

    fn cancel_input(&mut self) {
        if self.held != 0 {
            let (x, y) = self.replay_point(-1, -1);
            for (bit, command) in [(1, 1), (2, 3)] {
                if self.held & bit != 0 { self.round.play(command, x, y, self.settings.flag_win); }
            }
            self.held = 0;
        }
        self.restart_pressed = false;
        self.release_cursor();
        self.sdl.mouse().capture(false);
        self.main.dirty = true;
    }

    fn mouse(&mut self, btn: MouseButton, down: bool, x: f32, y: f32) -> Result<(), String> {
        let (x, y) = self.main.point(x, y);
        self.pointer = (x, y);
        self.main.dirty = true;
        if btn == MouseButton::Left && down && y < MENU && self.held == 0 {
            let choice = self.menu.top.iter().find(|(rect, _)| rect.contains(x, y)).map(|(_, i)| *i);
            self.menu.open = choice.filter(|choice| self.menu.open != Some(*choice));
            return Ok(());
        }
        if self.menu.open.is_some() {
            if !down || btn != MouseButton::Left { return Ok(()); }
            let choice = self.menu.options.iter().find(|(rect, _)| rect.contains(x, y)).map(|(_, c)| *c);
            self.menu.open = None;
            if let Some(Choice::Command(action)) = choice { self.action(action)?; }
            if let Some(Choice::Menu(index)) = choice { self.menu.open = Some(index); }
            return Ok(());
        }
        let status = self.layout.status(self.main.pixels().0);
        if btn == MouseButton::Left && self.held == 0 && (self.restart_pressed || status.contains(x, y)) {
            if !down && self.restart_pressed && status.contains(x, y) { self.action(Action::Restart)?; }
            self.restart_pressed = down && status.contains(x, y);
            self.sdl.mouse().capture(self.restart_pressed);
            return Ok(());
        }
        if self.round.ended() { return Ok(()); }
        let bit = match btn { MouseButton::Left => 1, MouseButton::Right => 2, _ => return Ok(()) };
        let inside = self.grid().contains(x, y);
        if down && (!inside || self.held & bit != 0) || !down && self.held & bit == 0 { return Ok(()); }
        if down { self.held |= bit; } else { self.held &= !bit; }
        let (x, y) = self.replay_point(x, y);
        self.round.play((bit - 1) as u32 * 2 + u32::from(!down), x, y, self.settings.flag_win);
        if self.round.ended() { self.held = 0; }
        self.sdl.mouse().capture(self.held != 0);
        self.sync_cursor();
        self.finish();
        if let Some(counter) = &mut self.counter { counter.dirty = true; }
        Ok(())
    }

    fn finish(&mut self) {
        if !self.round.ended() || self.last_saved_round { return; }
        self.last_saved_round = true;
        if !self.round.timing_valid {
            self.errors.push(self.settings.text(Text::TimingWarning).into());
        } else if self.settings.autosave == 0 || (self.settings.autosave == 1 && self.round.phase() == 2) {
            match self.round.replay(self.settings.level) {
                Ok(replay) => { let _ = self.jobs.send(Job { replay, path: None }); }
                Err(error) => self.errors.push(format!("{}\n{error}", self.settings.text(Text::ReplayGenerationError))),
            }
        }
    }

    fn event(&mut self, event: Event) -> Result<(), String> {
        match event {
            Event::Quit { .. } => self.quit = true,
            Event::Window { window_id, win_event, .. } => self.window_event(window_id, win_event)?,
            Event::KeyDown { keycode: Some(key), keymod, repeat: false, .. } => {
                if self.dialog.is_some() { return self.dialog_key(key, keymod); }
                if key == Keycode::Escape {
                    self.menu.open = None;
                    self.cursor_released = true;
                    self.release_cursor();
                    self.main.dirty = true;
                } else if let Some(action) = shortcut(key, ctrl(keymod)) { self.action(action)?; }
            }
            Event::TextInput { text, window_id, .. } => {
                if let Some(dialog) = &mut self.dialog {
                    if dialog.display.window.id() != window_id { return Ok(()); }
                    match &mut dialog.panel {
                        Panel::Settings { inputs, focus, select, .. } if (1..=3).contains(focus) =>
                            append_text(&mut inputs[*focus - 1], select, &text, 128),
                        Panel::Save { path, select, overwrite, .. } => {
                            append_text(path, select, &text, 2048);
                            *overwrite = false;
                        }
                        _ => {}
                    }
                    dialog.display.dirty = true;
                }
            }
            Event::MouseMotion { window_id, x, y, .. } if window_id == self.main.window.id() && self.dialog.is_none() => {
                let pos = self.main.point(x, y);
                if self.held != 0 || self.menu.open.is_some() || pos.1 < MENU || self.pointer.1 < MENU { self.main.dirty = true; }
                self.pointer = pos;
                if self.menu.open.is_none() {
                    let (x, y) = self.replay_point(pos.0, pos.1);
                    self.round.track(x, y);
                }
            }
            Event::MouseButtonDown { window_id, mouse_btn, x, y, .. } => {
                if let Some(dialog) = &mut self.dialog {
                    if dialog.display.window.id() == window_id && mouse_btn == MouseButton::Left {
                        self.dialog_click(x, y)?;
                    } else { dialog.display.window.raise(); }
                } else if window_id == self.main.window.id() { self.mouse(mouse_btn, true, x, y)?; }
                else if let Some(counter) = &self.counter {
                    let (px, py) = counter.point(x, y);
                    if window_id == counter.window.id() && (0..37).contains(&py) && px >= counter.pixels().0 - 24 {
                        self.action(Action::Counter)?;
                    }
                }
            }
            Event::MouseButtonUp { window_id, mouse_btn, x, y, .. } if window_id == self.main.window.id() && self.dialog.is_none() => {
                self.mouse(mouse_btn, false, x, y)?;
            }
            _ => {}
        }
        Ok(())
    }

    fn window_event(&mut self, id: u32, event: WindowEvent) -> Result<(), String> {
        if id == self.main.window.id() {
            match event {
                WindowEvent::CloseRequested => self.quit = true,
                WindowEvent::Resized(..) => self.user_resize(),
                WindowEvent::PixelSizeChanged(..) => {
                    let preferred = self.settings.pixels[self.settings.level];
                    if self.resized_at.is_none() && self.layout.size(self.settings.level, self.settings.identity) != self.main.pixels() {
                        self.resize_main(preferred);
                    }
                    self.main.dirty = true;
                }
                WindowEvent::Moved(x, y) if !self.wayland => self.settings.position = Some((x, y)),
                WindowEvent::FocusLost => { self.menu.open = None; self.cancel_input(); }
                WindowEvent::FocusGained => self.sync_cursor(),
                WindowEvent::MouseLeave if self.held == 0 => {
                    self.pointer = (-1, -1);
                    let (x, y) = self.replay_point(-1, -1);
                    self.round.track(x, y);
                    self.main.dirty = true;
                }
                WindowEvent::DisplayChanged(..) => { self.update_refresh_rate(); self.resize_main(self.layout.tile); }
                WindowEvent::Exposed | WindowEvent::Restored | WindowEvent::Shown => self.main.dirty = true,
                _ => {}
            }
        } else if self.dialog.as_ref().is_some_and(|d| d.display.window.id() == id) {
            if event == WindowEvent::CloseRequested { self.close_dialog(); }
            else if let Some(dialog) = self.dialog.as_mut() { dialog.display.dirty = true; }
        } else if self.counter.as_ref().is_some_and(|c| c.window.id() == id) {
            match event {
                WindowEvent::CloseRequested => self.action(Action::Counter)?,
                WindowEvent::Moved(x, y) if !self.wayland => self.settings.counter_position = Some((x, y)),
                WindowEvent::DisplayChanged(..) => self.update_refresh_rate(),
                WindowEvent::Exposed | WindowEvent::PixelSizeChanged(..) => {
                    if let Some(counter) = &mut self.counter { counter.dirty = true; }
                }
                _ => {}
            }
        }
        Ok(())
    }

    fn update(&mut self, now: Instant) -> Result<(), String> {
        if self.resized_at.is_some_and(|since| now.duration_since(since) >= Duration::from_millis(180)) {
            self.resize_main(self.layout.tile);
            self.persist();
            self.sync_cursor();
        }
        if now >= self.next_update {
            self.next_update = now + self.refresh_every;
            if self.round.phase() == 1 || (self.round.ended() && self.round.metrics.is_none()) {
                let old = self.round.seconds() as u32;
                self.round.refresh();
                self.main.dirty |= old != self.round.seconds() as u32;
                if let Some(counter) = &mut self.counter { counter.dirty = true; }
            }
            while let Ok(reply) = self.replies.try_recv() {
                if let Err(error) = reply { self.errors.push(error); }
            }
        }
        if self.dialog.is_none() && !self.errors.is_empty() {
            let error = self.errors.remove(0);
            self.open_dialog(self.settings.text(Text::Title), Panel::Message { text: error }, (490, 190))?;
        }
        Ok(())
    }

    fn draw(&mut self, events: &EventPump) -> Result<(), String> {
        let (art, menu) = (&mut self.art, &mut self.menu);
        let (settings, round, layout, pointer, restart) = (&self.settings, &self.round, self.layout, self.pointer, self.restart_pressed);
        self.main.draw(events, |p, w, h| view::game(p, art, settings, round, layout, menu, pointer, restart, (w, h)))?;
        if let Some(counter) = &mut self.counter {
            counter.draw(events, |p, w, h| view::counter(p, settings, round, w, h))?;
        }
        if let Some(Dialog { display, panel }) = &mut self.dialog {
            display.draw(events, |p, w, h| match panel {
                Panel::Settings { draft, inputs, focus, select, drop } => view::settings(p, draft, *focus, *select, *drop, inputs, w, h),
                Panel::Save { path, overwrite, select, .. } => {
                    p.fill(Box2(0, 0, w, h), 0xf5f5f5);
                    let area = Box2(12, 13, w - 24, 33);
                    p.fill(area, if *select { 0xd5e9ff } else { WHITE });
                    p.border(area, 0x467eac);
                    p.text(area.inset(5), path, 15, Align::Left, INK);
                    if *overwrite {
                        p.text(Box2(12, 48, w-24, 25), settings.text(Text::OverwriteReplay), 15, Align::Left, 0x8a3030);
                    }
                    view::button(p, view::dialog_button(w, h, true), settings.text(Text::Ok));
                    view::button(p, view::dialog_button(w, h, false), settings.text(Text::Cancel));
                }
                Panel::Message { text } => view::message(p, text, settings.text(Text::Ok), w, h),
            })?;
        }
        Ok(())
    }

    fn run(mut self) -> Result<(), String> {
        let mut events = self.sdl.event_pump().map_err(|e| e.to_string())?;
        while !self.quit {
            self.update(Instant::now())?;
            self.draw(&events)?;
            if let Some(event) = events.wait_event_timeout(self.next_update.saturating_duration_since(Instant::now())) {
                self.event(event)?;
                for event in events.poll_iter() { self.event(event)?; }
            }
        }
        self.release_cursor();
        self.settings.save(&self.root).map_err(|e| e.to_string())
    }
}

fn ctrl(mods: Mod) -> bool { mods.intersects(Mod::LCTRLMOD | Mod::RCTRLMOD) }

fn shortcut(key: Keycode, control: bool) -> Option<Action> {
    Some(match (key, control) {
        (Keycode::S, true) => Action::Save,
        (Keycode::I, true) => Action::Identity,
        (Keycode::X, true) => Action::Quit,
        (Keycode::F2 | Keycode::N, false) => Action::Restart,
        (Keycode::_1 | Keycode::B, false) => Action::Level(0),
        (Keycode::_2 | Keycode::I, false) => Action::Level(1),
        (Keycode::_3 | Keycode::E, false) => Action::Level(2),
        (Keycode::Slash, false) => Action::Counter,
        (Keycode::S, false) => Action::Settings,
        (Keycode::W, false) => Action::Open,
        (Keycode::Z, false) => Action::Shortcuts,
        _ => return None,
    })
}

fn adjust(draft: &mut Settings, row: usize, change: i32) {
    match row {
        0 => draft.lang = (draft.lang as i32 + change).rem_euclid(5) as usize,
        4 => draft.identity = !draft.identity,
        5 => draft.pixels[draft.level] = (draft.pixels[draft.level] + change).clamp(5, 255),
        6 => draft.autosave = (draft.autosave as i32 + change).rem_euclid(3) as usize,
        7 => draft.cursor_lock = !draft.cursor_lock,
        8 => draft.flag_win = !draft.flag_win,
        9 => draft.counter = !draft.counter,
        10 => draft.counter_pixels = (draft.counter_pixels + change).clamp(12, 48),
        _ => {}
    }
}

fn edit_text(value: &mut String, select: &mut bool, key: Keycode, control: bool, clipboard: Option<String>, max: usize) {
    match (key, control) {
        (Keycode::A, true) => *select = true,
        (Keycode::V, true) => if let Some(text) = clipboard { append_text(value, select, &text, max); },
        (Keycode::Backspace | Keycode::Delete, false) if *select => { value.clear(); *select = false; }
        (Keycode::Backspace, false) => { value.pop(); }
        (Keycode::Left | Keycode::Right, false) => *select = false,
        _ => {}
    }
}

fn append_text(value: &mut String, select: &mut bool, text: &str, max: usize) {
    if *select { value.clear(); *select = false; }
    value.extend(text.chars().filter(|ch| !ch.is_control()).take(max.saturating_sub(value.chars().count())));
}

fn save_path(root: &Path, name: &str) -> PathBuf {
    let mut path = root.join("replay").join(name.trim());
    if !path.extension().is_some_and(|ext| ext.eq_ignore_ascii_case("evf")) {
        path.as_mut_os_string().push(".evf");
    }
    path
}

fn open_directory(path: &Path) -> std::io::Result<()> {
    #[cfg(windows)]
    {
        Command::new("explorer").arg(path).spawn().map(|_| ())
    }
    #[cfg(not(windows))]
    {
        Command::new("xdg-open").arg(path).spawn().map(|_| ())
    }
}

fn run() -> Result<(), String> {
    let executable = env::current_exe().map_err(|e| e.to_string())?;
    let root = executable.parent().ok_or("Cannot locate the program directory")?.to_owned();
    let settings = Settings::read(&root).map_err(|e| e.to_string())?;
    if !root.join("gameSetting.ini").exists() { settings.save(&root).map_err(|e| e.to_string())?; }
    let directory = root.join("replay");
    fs::create_dir_all(&directory).map_err(|e| e.to_string())?;
    let (jobs, queue) = mpsc::channel::<Job>();
    let (reply, replies) = mpsc::channel();
    let writer = thread::Builder::new().name("Mini replay writer".into()).spawn(move || {
        while let Ok(job) = queue.recv() {
            let result = job.replay.save(&directory, job.path.as_deref()).map(|_| ()).map_err(|err| err.to_string());
            if let Err(error) = &result { eprintln!("{error}"); }
            let _ = reply.send(result);
        }
    }).map_err(|e| e.to_string())?;
    let result = App::new(root, settings, jobs, replies).and_then(App::run);
    let _ = writer.join();
    result
}

fn main() {
    if let Err(error) = run() {
        eprintln!("MetaSweeper-Mini: {error}");
        std::process::exit(1);
    }
}
