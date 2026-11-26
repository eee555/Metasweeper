#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod config;
mod core;
mod counter_formula;
mod csv_export;
mod dropdown;
mod folder_picker;
mod layout;
mod native;
mod paint;
mod platform;
mod replay_signature;
mod settings_ui;
mod stats;
mod text;
mod view;

use config::{Settings, Text};
use core::{Replay, Round};
use layout::{Box2, CounterLayout, FullscreenMode, Layout, COUNTER_MIN, MENU};
use native::CELL_PIXELS;
use paint::{Align, Art, Buffer, INK, WHITE};
use sdl3::{
    event::{DisplayEvent, Event, WindowEvent},
    keyboard::{Keycode, Mod, Scancode},
    mouse::{Cursor, MouseButton, SystemCursor},
    rect::Rect,
    video::Window,
    EventPump, Sdl, VideoSubsystem,
};
use settings_ui::Outcome;
use stats::{GameResult, Record};
use std::{
    fs,
    path::{Path, PathBuf},
    sync::mpsc::{self, Receiver, Sender},
    thread,
    time::{Duration, Instant},
};
use view::{Action, Choice, Menu};

const RESIZE_SETTLE: Duration = Duration::from_millis(180);
const REFRESH_RECHECK: Duration = Duration::from_secs(2);
const BACKGROUND_REFRESH_INTERVAL: Duration = Duration::from_millis(50);
const REFRESH_TICK: i32 = 1;
const CSV_PROGRESS_SIZE: (u32, u32) = (400, 108);
const ABOUT_SIZE: (u32, u32) = (320, 130);

fn restore_default_cursor() {
    unsafe { sdl3_sys::mouse::SDL_SetCursor(sdl3_sys::mouse::SDL_GetDefaultCursor()) };
}

#[derive(Default)]
struct RefreshTimer {
    active: Option<(sdl3_sys::timer::SDL_TimerID, Duration)>,
}

impl RefreshTimer {
    fn sync(&mut self, event_type: u32, interval: Option<Duration>) -> Result<(), String> {
        use sdl3_sys::timer::{SDL_AddTimerNS, SDL_RemoveTimer};
        if self.active.map(|(_, interval)| interval) == interval {
            return Ok(());
        }
        if let Some((timer, _)) = self.active.take() {
            unsafe {
                SDL_RemoveTimer(timer);
            }
        }
        if let Some(interval) = interval {
            let timer = unsafe {
                SDL_AddTimerNS(
                    interval.as_nanos() as u64,
                    Some(refresh_tick),
                    event_type as usize as *mut _,
                )
            };
            if timer.0 == 0 {
                return Err(sdl3::get_error().to_string());
            }
            self.active = Some((timer, interval));
        }
        Ok(())
    }
}

impl Drop for RefreshTimer {
    fn drop(&mut self) {
        let _ = self.sync(0, None);
    }
}

unsafe extern "C" fn refresh_tick(
    event_type: *mut std::ffi::c_void,
    _: sdl3_sys::timer::SDL_TimerID,
    interval: u64,
) -> u64 {
    let event_type = event_type as usize as u32;
    if !unsafe { sdl3_sys::events::SDL_HasEvent(event_type) } {
        platform::wake_event(event_type, REFRESH_TICK);
    }
    interval
}

fn refresh_interval(rate: Option<f64>) -> Duration {
    let rate = rate
        .filter(|rate| rate.is_finite() && *rate > 1.0)
        .unwrap_or(60.0);
    Duration::from_secs_f64(1.0 / rate).max(Duration::from_nanos(1))
}

fn input_delay(timestamp: u64) -> Duration {
    if timestamp == 0 {
        return Duration::ZERO;
    }
    let now = unsafe { sdl3_sys::timer::SDL_GetTicksNS() };
    Duration::from_nanos(now.saturating_sub(timestamp))
}

struct Display {
    hook: Option<platform::WindowHook>,
    window: Window,
    buffer: Buffer,
    dirty: bool,
    ui_scale: f64,
    shown: bool,
    reveal_position: Option<(i32, i32)>,
}

impl Display {
    fn new(window: Window) -> Self {
        Self {
            hook: None,
            window,
            buffer: Buffer::default(),
            dirty: true,
            ui_scale: 1.0,
            shown: false,
            reveal_position: None,
        }
    }

    fn pixels(&self) -> (i32, i32) {
        let (w, h) = self.window.size_in_pixels();
        (w as i32, h as i32)
    }

    fn point(&self, x: f32, y: f32) -> (i32, i32) {
        let (w, h) = self.window.size();
        let (pw, ph) = self.pixels();
        (
            (x * pw as f32 / w.max(1) as f32).floor() as i32,
            (y * ph as f32 / h.max(1) as f32).floor() as i32,
        )
    }

    fn logical(&self, x: i32, y: i32) -> (i32, i32) {
        let (w, h) = self.window.size();
        let (pw, ph) = self.pixels();
        (
            (x as f64 * w as f64 / pw.max(1) as f64).round() as i32,
            (y as f64 * h as f64 / ph.max(1) as f64).round() as i32,
        )
    }

    fn ui_pixels(&self) -> (i32, i32) {
        let (w, h) = self.pixels();
        (
            (w as f64 / self.ui_scale).round() as i32,
            (h as f64 / self.ui_scale).round() as i32,
        )
    }

    fn ui_point(&self, x: f32, y: f32) -> (i32, i32) {
        let (x, y) = self.point(x, y);
        (
            ((x as f64 + 0.5) / self.ui_scale).floor() as i32,
            ((y as f64 + 0.5) / self.ui_scale).floor() as i32,
        )
    }

    fn ui_to_window(&self, x: i32, y: i32) -> (i32, i32) {
        self.logical(
            (x as f64 * self.ui_scale).round() as i32,
            (y as f64 * self.ui_scale).round() as i32,
        )
    }

    fn measure_setting(&self, text: &str) -> i32 {
        self.buffer.measure(text, settings_ui::FONT, self.ui_scale)
    }

    fn draw(
        &mut self,
        events: &EventPump,
        draw: impl FnOnce(&paint::Painter, i32, i32),
    ) -> Result<(), String> {
        if !self.dirty {
            return Ok(());
        }
        self.dirty = false;
        self.buffer
            .present(&self.window, events, self.ui_scale, draw)
    }
}

enum Panel {
    Settings(Box<settings_ui::Form>),
    Fullscreen {
        mode: FullscreenMode,
        pointer: view::ButtonPointer<FullscreenMode>,
    },
    Save {
        path: String,
        replay: Replay,
        overwrite: bool,
        select: bool,
    },
    CsvFolder(folder_picker::Picker),
    CsvProgress(u8),
    About {
        version_clicks: u8,
    },
    Message {
        text: String,
    },
}

const FULLSCREEN_CHOICES: [(FullscreenMode, Text, &str); 3] = [
    (FullscreenMode::Board, Text::FullscreenBoardOnly, "1"),
    (FullscreenMode::Status, Text::FullscreenWithStatus, "2"),
    (FullscreenMode::Counter, Text::FullscreenWithCounter, "3"),
];

fn fullscreen_choice_at(size: (i32, i32), (x, y): (i32, i32)) -> Option<FullscreenMode> {
    FULLSCREEN_CHOICES
        .iter()
        .map(|&(mode, _, _)| mode)
        .find(|&mode| view::fullscreen_button(size.0, size.1, mode).contains(x, y))
}

struct Dialog {
    display: Display,
    panel: Panel,
}

enum Job {
    Replay(Replay, Option<PathBuf>),
    Stats(Record),
    ExportCsv {
        targets: [PathBuf; 2],
        overwrite: bool,
    },
}

impl Job {
    fn error_text(&self) -> Text {
        match self {
            Self::Replay(..) => Text::ReplaySaveError,
            Self::Stats(_) => Text::StatsSaveError,
            Self::ExportCsv { .. } => Text::CsvExportError,
        }
    }
}

enum WriteReply {
    ExportProgress(u8),
    Finished(Result<Option<[PathBuf; 2]>, (Text, String)>),
}

struct App {
    text_cursor: Option<Cursor>,
    sdl: Sdl,
    video: VideoSubsystem,
    main: Display,
    counter: Option<Display>,
    counter_view: view::Counter,
    fullscreen_counter: view::FullscreenCounter,
    counter_resize_at: Option<Instant>,
    dialog: Option<Dialog>,
    wayland: bool,
    fullscreen: bool,
    fullscreen_mode: FullscreenMode,
    windowed_level: usize,
    settings: Settings,
    root: PathBuf,
    round: Round,
    last_saved_round: bool,
    pending_writes: usize,
    save_requested: bool,
    jobs: Sender<Job>,
    replies: Receiver<WriteReply>,
    errors: Vec<String>,
    reference: i32,
    layout: Layout,
    window_size_request: Option<(i32, i32)>,
    resized_at: Option<Instant>,
    pointer: (i32, i32),
    held: u8,
    restart_pressed: bool,
    status_clicks: u8,
    timer_restart_at: Option<Instant>,
    confinement: bool,
    menu: Menu,
    art: Art,
    quit: bool,
    wake_type: u32,
    refresh_every: Duration,
    refresh_checked: Instant,
}

impl App {
    fn new(
        root: PathBuf,
        mut settings: Settings,
        jobs: Sender<Job>,
        replies: Receiver<WriteReply>,
    ) -> Result<Self, String> {
        sdl3::hint::set("SDL_APP_ID", "org.metasweeper.Mini");
        sdl3::hint::set("SDL_IME_IMPLEMENTED_UI", "composition");
        platform::configure_window_hints();
        platform::configure_dpi();
        let sdl = sdl3::init().map_err(|e| e.to_string())?;
        let video = sdl.video().map_err(|e| e.to_string())?;
        let wake_type = unsafe { sdl.event().map_err(|e| e.to_string())?.register_event() }
            .map_err(|e| e.to_string())?;
        let wayland = video.current_video_driver() == "wayland";
        let available = video
            .displays()
            .ok()
            .and_then(|ds| ds.first().copied())
            .and_then(|display| display.get_usable_bounds().ok())
            .map(|b| (b.width() as i32 - 20, b.height() as i32 - 55))
            .unwrap_or((1920, 1020));
        let requested = settings.pixels[settings.level];
        let reference = requested
            .min(Layout::fit(requested, settings.level, settings.identity, available).tile);
        settings.pixels[settings.level] = reference;
        let layout = Layout::new(reference, reference);
        let size = layout.size(settings.level, settings.identity);
        let mut builder = video.window(settings.text(Text::Title), size.0 as u32, size.1 as u32);
        builder.resizable().high_pixel_density();
        platform::place_main_window(&mut builder, settings.position, wayland);
        let window = builder.build().map_err(|e| e.to_string())?;
        let round = Round::new(&settings);
        let mut app = Self {
            text_cursor: Cursor::from_system(SystemCursor::IBeam).ok(),
            sdl,
            video,
            main: Display::new(window),
            counter: None,
            counter_view: view::Counter::default(),
            fullscreen_counter: view::FullscreenCounter::default(),
            counter_resize_at: None,
            dialog: None,
            wayland,
            fullscreen: false,
            fullscreen_mode: FullscreenMode::Status,
            windowed_level: settings.level,
            root,
            settings,
            round,
            last_saved_round: false,
            jobs,
            replies,
            errors: Vec::new(),
            pending_writes: 0,
            save_requested: false,
            layout,
            reference,
            window_size_request: None,
            resized_at: None,
            pointer: (-1, -1),
            held: 0,
            restart_pressed: false,
            status_clicks: 0,
            timer_restart_at: None,
            confinement: false,
            menu: Menu::default(),
            art: Art::new(),
            quit: false,
            wake_type,
            refresh_every: refresh_interval(None),
            refresh_checked: Instant::now(),
        };
        if let Some(position) = app.settings.position {
            platform::fit_to_screen(&app.main.window, position);
        }
        app.main.hook = platform::board_hook(&app.main.window, reference, &app.settings)?;
        app.resize_main(reference);
        if let Some(position) = app.settings.position {
            platform::fit_to_screen(&app.main.window, position);
        }
        if app.settings.counter {
            app.show_counter()?;
        }
        app.update_refresh_rate();
        Ok(app)
    }

    fn resize_main(&mut self, tile: i32) {
        self.release_cursor();
        let (level, footer) = (self.settings.level, self.settings.identity);
        let available = self
            .main
            .window
            .get_display()
            .ok()
            .and_then(|display| display.get_usable_bounds().ok())
            .map(|r| self.main.point(r.width() as f32, r.height() as f32))
            .map(|(width, height)| (width - 16, height - 48))
            .unwrap_or((1920, 1020));
        if let Some(hook) = &self.main.hook {
            hook.update_board(&self.settings);
        }
        if !platform::normal(&self.main.window) {
            self.user_resize();
            return;
        }
        let available = platform::client_capacity(&self.main.window).unwrap_or(available);
        let target = tile.min(Layout::fit(self.reference, level, footer, available).tile);
        self.layout = Layout::new(target, self.reference);
        self.settings.pixels[level] = target;
        let min = Layout::new(5, self.reference).size(level, footer);
        let (min_x, min_y) = self.main.logical(min.0, min.1);
        let _ = self
            .main
            .window
            .set_minimum_size(min_x.max(1) as u32, min_y.max(1) as u32);
        let desired = self.layout.size(level, footer);
        let logical = self.main.logical(desired.0, desired.1);
        self.resized_at = None;
        self.window_size_request = Some(logical);
        if self.main.window.size() != (logical.0 as u32, logical.1 as u32) {
            let _ = self
                .main
                .window
                .set_size(logical.0.max(1) as u32, logical.1.max(1) as u32);
        }
        self.main.dirty = true;
    }

    fn user_resize(&mut self) {
        self.release_cursor();
        let size = self.main.window.size();
        let size = (size.0 as i32, size.1 as i32);
        if self.window_size_request != Some(size) {
            self.window_size_request = None;
            self.layout = Layout::fit(
                self.reference,
                self.settings.level,
                self.settings.identity,
                self.main.pixels(),
            );
            self.settings.pixels[self.settings.level] = self.layout.tile;
            if self.main.hook.is_some() {
                self.main.dirty = true;
                return;
            }
            self.resized_at = Some(Instant::now());
        }
        self.main.dirty = true;
    }

    fn update_refresh_rate(&mut self) {
        let main_rate = platform::refresh_rate(&self.main.window);
        let counter_rate = self
            .counter
            .as_ref()
            .filter(|counter| counter.shown)
            .and_then(|counter| platform::refresh_rate(&counter.window));
        self.refresh_every =
            refresh_interval(main_rate.into_iter().chain(counter_rate).reduce(f64::max));
        self.refresh_checked = Instant::now();
    }

    fn refreshing(&self) -> bool {
        self.round.phase() == 1 || (self.round.ended() && self.round.metrics.is_none())
    }

    fn refresh_period(&self) -> Option<Duration> {
        self.refreshing().then(|| {
            let fullscreen_counter =
                self.fullscreen && self.fullscreen_mode == FullscreenMode::Counter;
            let separate_counter = self.counter.as_ref().is_some_and(|counter| counter.shown);
            if fullscreen_counter || separate_counter {
                self.refresh_every
            } else {
                self.refresh_every.max(BACKGROUND_REFRESH_INTERVAL)
            }
        })
    }

    fn show_counter(&mut self) -> Result<(), String> {
        if self.counter.is_some() {
            return Ok(());
        }
        self.counter_resize_at = None;
        let rows = self.settings.counter_config.len();
        let scale = CounterLayout::fit(
            self.settings.counter_pixels,
            counter_capacity(&self.main.window),
            rows,
        );
        self.settings.counter_pixels = scale;
        let (width, height) = CounterLayout::new(scale).size(rows);
        let mut builder = self.video.window(
            self.settings.text(Text::Counter),
            width as u32,
            height as u32,
        );
        builder.borderless().resizable();
        builder.hidden();
        builder.set_window_flags(
            builder.window_flags() | sdl3_sys::video::SDL_WINDOW_UTILITY.0 as u32,
        );
        if !self.wayland {
            let (x, y) = self.main.window.position();
            let left = self
                .main
                .window
                .get_display()
                .ok()
                .and_then(|d| d.get_usable_bounds().ok())
                .map(|r| r.x)
                .unwrap_or(0);
            let x = if x - width - 9 >= left {
                x - width - 9
            } else {
                x + self.main.window.size().0 as i32 + 9
            };
            let (x, y) = self.settings.counter_position.unwrap_or((x, y + 10));
            builder.position(x, y);
        }
        let mut window = builder.build().map_err(|e| e.to_string())?;
        platform::disable_maximize_button(&window);
        unsafe {
            sdl3_sys::video::SDL_SetWindowParent(window.raw(), self.main.window.raw());
        }
        let min = CounterLayout::new(COUNTER_MIN).size(rows);
        let _ = window.set_minimum_size(min.0 as u32, min.1 as u32);
        let mut display = Display::new(window);
        display.hook = platform::counter_hook(&display.window, self.wake_type, scale, rows)?;
        platform::set_counter_hit_test(&mut display.window, display.hook.is_none());
        platform::position_counter(
            &self.main.window,
            &display.window,
            self.settings.counter_position,
        );
        self.counter_view.invalidate();
        self.counter = Some(display);
        self.update_refresh_rate();
        Ok(())
    }

    fn settle_counter_resize(&mut self) {
        self.counter_resize_at = None;
        let Some(counter) = &mut self.counter else {
            return;
        };
        let current = self.settings.counter_pixels;
        let rows = self.settings.counter_config.len();
        let prior = CounterLayout::new(current).size(rows);
        let size = counter.ui_pixels();
        if size == prior {
            return;
        }
        let scale = CounterLayout::nearest(
            current,
            size,
            counter_capacity(&counter.window),
            (size.0 != prior.0, size.1 != prior.1),
            rows,
        );
        self.settings.counter_pixels = scale;
        if let Some(hook) = &counter.hook {
            hook.update_counter(scale);
        }
        let target = CounterLayout::new(scale).size(rows);
        if size != target {
            let (width, height) = counter.logical(target.0, target.1);
            let _ = counter
                .window
                .set_size(width.max(1) as u32, height.max(1) as u32);
        }
        self.counter_view.invalidate();
        counter.dirty = true;
        self.persist();
    }

    fn remember_main_position(&mut self) {
        if self.fullscreen {
            return;
        }
        if let Some(position) = platform::window_position(&self.main.window) {
            self.settings.position = Some(position);
        }
    }

    fn change_fullscreen(&mut self, requested_mode: Option<FullscreenMode>) -> bool {
        let enabled = requested_mode.is_some();
        if self.wayland {
            self.errors
                .push(self.settings.text(Text::FullscreenWayland).into());
            return false;
        }
        self.cancel_input();
        self.menu.open = None;
        self.pointer = (-1, -1);
        let mut hide_counter = false;
        let mode = requested_mode.unwrap_or(self.fullscreen_mode);
        if enabled {
            self.remember_main_position();
            if mode == FullscreenMode::Counter {
                hide_counter = true;
                if let Some(counter) = self.counter.as_mut() {
                    counter.dirty = false;
                    counter.shown = false;
                }
            } else if let Some(counter) = &self.counter {
                let displays = self
                    .main
                    .window
                    .get_display()
                    .ok()
                    .zip(counter.window.get_display().ok());
                hide_counter = displays.is_none_or(|(main, counter)| main == counter);
                if hide_counter {
                    if let Some(position) = platform::window_position(&counter.window) {
                        self.settings.counter_position = Some(position);
                    }
                }
            }
        }
        let result = if let Some(fullscreen_mode) = requested_mode {
            let (width, height, _) = self.layout.fullscreen_size(
                self.settings.level,
                fullscreen_mode,
                self.settings.counter_config.len(),
            );
            platform::enter_exclusive_fullscreen(&mut self.main.window, (width, height))
        } else {
            platform::leave_exclusive_fullscreen(&mut self.main.window)
        };
        if let Err(error) = result {
            self.errors.push(format!(
                "{}\n{error}",
                self.settings.text(Text::FullscreenError)
            ));
            return false;
        }
        self.fullscreen = enabled;
        self.fullscreen_mode = mode;
        self.fullscreen_counter.invalidate();
        self.resized_at = None;
        if enabled {
            self.windowed_level = self.settings.level;
            if let Some(counter) = self.counter.as_mut().filter(|_| hide_counter) {
                counter.window.hide();
                counter.shown = false;
                self.counter_resize_at = None;
            }
        } else {
            let (width, height) = self.main.window.size();
            self.window_size_request = Some((width as i32, height as i32));
            if self.settings.level != self.windowed_level {
                self.resize_main(self.settings.pixels[self.settings.level]);
                if let Some(position) = self
                    .settings
                    .position
                    .filter(|_| platform::normal(&self.main.window))
                {
                    platform::fit_to_screen(&self.main.window, position);
                }
            }
            if let Some(counter) = self.counter.as_mut().filter(|counter| !counter.shown) {
                if let Some(position) = self.settings.counter_position {
                    platform::fit_to_screen(&counter.window, position);
                }
                self.counter_view.invalidate();
                counter.dirty = true;
            }
        }
        self.update_refresh_rate();
        true
    }

    fn persist(&mut self) {
        if let Err(e) = self.settings.save(&self.root) {
            self.errors.push(format!(
                "{}\n{e}",
                self.settings.text(Text::SettingsSaveError)
            ));
        }
    }

    fn open_dialog(
        &mut self,
        title: &'static str,
        panel: Panel,
        size: (u32, u32),
    ) -> Result<(), String> {
        self.timer_restart_at = None;
        self.cancel_input();
        let mut builder = self.video.window(title, size.0, size.1);
        builder.position_centered();
        let scaled = matches!(
            panel,
            Panel::Settings(_)
                | Panel::Fullscreen { .. }
                | Panel::CsvFolder(_)
                | Panel::CsvProgress(_)
                | Panel::About { .. }
        );
        builder.hidden();
        if scaled {
            builder.high_pixel_density();
        }
        let mut window = builder.build().map_err(|e| e.to_string())?;
        unsafe {
            sdl3_sys::video::SDL_SetWindowParent(window.raw(), self.main.window.raw());
            sdl3_sys::video::SDL_SetWindowModal(window.raw(), true);
        }
        #[cfg(windows)]
        if scaled {
            platform::set_dialog_caption_buttons(&window, !matches!(panel, Panel::CsvProgress(_)));
        }
        let ui_scale = if scaled {
            platform::center_settings(&window, &self.main.window);
            let scale = platform::dpi_scale(&window);
            let window_scale = scale / window_pixel_density(&window);
            if window_scale != 1.0 {
                let (width, height) = scaled_size(size, window_scale);
                let _ = window.set_size(width, height);
                platform::center_settings(&window, &self.main.window);
            }
            scale
        } else {
            1.0
        };
        if matches!(panel, Panel::Settings(_) | Panel::Save { .. }) {
            self.video.text_input().start(&window);
        }
        let mut display = Display::new(window);
        display.ui_scale = ui_scale;
        self.dialog = Some(Dialog { display, panel });
        Ok(())
    }

    fn close_dialog(&mut self) {
        if let Some(dialog) = self.dialog.take() {
            self.video.text_input().stop(&dialog.display.window);
            let settings = matches!(dialog.panel, Panel::Settings(_));
            let refocus =
                settings || matches!(dialog.panel, Panel::CsvFolder(_) | Panel::CsvProgress(_));
            if matches!(dialog.panel, Panel::CsvFolder(_)) {
                restore_default_cursor();
                self.sdl.mouse().capture(false);
            }
            if settings || matches!(dialog.panel, Panel::Fullscreen { .. }) {
                self.sdl.mouse().capture(false);
            }
            drop(dialog);
            if refocus {
                self.main.window.raise();
                self.main.dirty = true;
            }
        }
    }

    fn action(&mut self, action: Action) -> Result<(), String> {
        if self.fullscreen
            && matches!(
                action,
                Action::Settings
                    | Action::Shortcuts
                    | Action::About
                    | Action::Open
                    | Action::ExportCsv
                    | Action::Instructions
                    | Action::License
                    | Action::Counter
                    | Action::Identity
                    | Action::Save
            )
            && (action != Action::Save || self.round.ended() && self.round.timing_valid)
            && !self.change_fullscreen(None)
        {
            return Ok(());
        }
        if matches!(
            action,
            Action::Shortcuts | Action::Instructions | Action::License
        ) || (action == Action::Save && self.round.ended() && self.round.timing_valid)
        {
            self.cancel_input();
        }
        let settings = &self.settings;
        match action {
            Action::Restart | Action::Level(_) => {
                self.timer_restart_at = None;
                self.cancel_input();
                if let Action::Level(level) = action {
                    if self.fullscreen {
                        if level != self.settings.level {
                            let (width, height, _) = self.layout.fullscreen_size(
                                level,
                                self.fullscreen_mode,
                                self.settings.counter_config.len(),
                            );
                            if let Err(error) = platform::resize_exclusive_fullscreen(
                                &self.main.window,
                                (width, height),
                            ) {
                                self.errors.push(format!(
                                    "{}\n{error}",
                                    self.settings.text(Text::FullscreenError)
                                ));
                                return Ok(());
                            }
                            self.pointer = (-1, -1);
                            self.update_refresh_rate();
                        }
                        self.settings.level = level;
                    } else {
                        self.settings.level = level;
                        self.resize_main(self.settings.pixels[level]);
                        if let Some(position) = self
                            .settings
                            .position
                            .filter(|_| platform::normal(&self.main.window))
                        {
                            platform::fit_to_screen(&self.main.window, position);
                        }
                    }
                }
                self.record_unfinished_round();
                self.save_requested = false;
                self.round = Round::new(&self.settings);
                self.last_saved_round = false;
            }
            Action::Save if self.round.ended() && self.round.timing_valid => {
                if self.pending_writes != 0 {
                    self.save_requested = true;
                    return Ok(());
                }
                match self.round.replay(settings) {
                    Ok(replay) => {
                        if let Some(result) =
                            platform::save_dialog(&self.main.window, settings, &replay.name)
                        {
                            match result {
                                Ok(Some(path)) => self.queue_replay(replay, Some(path)),
                                Ok(None) => (),
                                Err(error) => self.errors.push(format!(
                                    "{}\n{error}",
                                    settings.text(Text::ReplaySaveError)
                                )),
                            }
                            self.main.dirty = true;
                            return Ok(());
                        }
                        let path = self
                            .root
                            .join("replay")
                            .join(format!("{}.evf", replay.name));
                        self.open_dialog(
                            settings.text(Text::SaveReplayTitle),
                            Panel::Save {
                                path: path.to_string_lossy().into_owned(),
                                replay,
                                overwrite: false,
                                select: false,
                            },
                            (570, 120),
                        )?;
                    }
                    Err(e) => self.errors.push(format!(
                        "{}\n{e}",
                        settings.text(Text::ReplayGenerationError)
                    )),
                }
            }
            Action::Save => {}
            Action::ExportCsv => {
                self.menu.open = None;
                self.main.dirty = true;
                self.open_dialog(
                    settings.text(Text::CsvExportTitle),
                    Panel::CsvFolder(folder_picker::Picker::new(&self.root)),
                    folder_picker::SIZE,
                )?;
            }
            Action::Open => {
                let root = self.root.join("replay");
                if let Err(e) = fs::create_dir_all(&root).and_then(|_| open_directory(&root)) {
                    self.errors
                        .push(format!("{}\n{e}", settings.text(Text::ReplayFolderError)));
                }
            }
            Action::Quit => self.quit = true,
            Action::Fullscreen => {
                if self.fullscreen {
                    self.change_fullscreen(None);
                } else {
                    self.open_dialog(
                        settings.text(Text::Fullscreen),
                        Panel::Fullscreen {
                            mode: FullscreenMode::Board,
                            pointer: view::ButtonPointer::default(),
                        },
                        view::FULLSCREEN_DIALOG_SIZE,
                    )?;
                }
            }
            Action::Settings => {
                let form = Box::new(settings_ui::Form::new(settings.clone()));
                self.open_dialog(
                    settings.text(Text::GameSettings),
                    Panel::Settings(form),
                    settings_ui::SIZE,
                )?;
            }
            Action::CursorLock => {
                self.settings.cursor_lock = !self.settings.cursor_lock;
                self.round.record_cursor_lock(self.settings.cursor_lock);
                self.sync_cursor();
                self.persist();
            }
            Action::Counter => {
                self.settings.counter = self.counter.is_none();
                if self.settings.counter {
                    self.show_counter()?;
                } else {
                    self.counter = None;
                    self.counter_resize_at = None;
                    self.update_refresh_rate();
                }
                self.persist();
            }
            Action::Identity => {
                self.settings.identity = !self.settings.identity;
                self.resize_main(self.layout.tile);
                self.persist();
            }
            Action::About => {
                self.open_dialog(
                    settings.text(Text::About),
                    Panel::About { version_clicks: 0 },
                    ABOUT_SIZE,
                )?;
            }
            Action::Shortcuts | Action::Instructions | Action::License => {
                let text = match action {
                    Action::Shortcuts => view::ENTRIES
                        .iter()
                        .flat_map(|group| group.iter())
                        .filter(|(_, _, key)| !key.is_empty())
                        .map(|(_, id, key)| format!("{}    {key}", settings.text(*id)))
                        .collect::<Vec<_>>()
                        .join("\n"),
                    Action::Instructions => format!(
                        "{}\n\n{}",
                        settings.text(Text::ClickHelp),
                        settings.text(Text::WindowHelp)
                    ),
                    _ => include_str!("../obj/ms-toollib/LICENSE").into(),
                };
                let title = match action {
                    Action::Shortcuts => Text::Shortcuts,
                    Action::Instructions => Text::Instructions,
                    _ => Text::License,
                };
                let native_title = if action == Action::License {
                    "ms_toollib"
                } else {
                    settings.text(title)
                };
                if platform::message(&self.main.window, native_title, &text, false) {
                    self.sync_cursor();
                    self.main.dirty = true;
                    return Ok(());
                }
                self.open_dialog(settings.text(title), Panel::Message { text }, (515, 360))?;
            }
        }
        self.main.dirty = true;
        if !(self.fullscreen && self.fullscreen_mode == FullscreenMode::Counter) {
            if let Some(counter) = &mut self.counter {
                counter.dirty = true;
            }
        }
        Ok(())
    }

    fn queue_replay(&mut self, replay: Replay, path: Option<PathBuf>) {
        self.queue_write(Job::Replay(replay, path));
    }

    fn queue_write(&mut self, job: Job) -> bool {
        match self.jobs.send(job) {
            Ok(()) => {
                self.pending_writes += 1;
                true
            }
            Err(error) => {
                self.errors
                    .push(self.settings.text(error.0.error_text()).into());
                false
            }
        }
    }

    fn close_csv_progress(&mut self) {
        if matches!(
            self.dialog.as_ref().map(|dialog| &dialog.panel),
            Some(Panel::CsvProgress(_))
        ) {
            self.close_dialog();
        }
    }

    fn collect_write_replies(&mut self, wait: bool) {
        while self.pending_writes > 0 {
            let reply = if wait {
                self.replies
                    .recv()
                    .map_err(|_| mpsc::TryRecvError::Disconnected)
            } else {
                self.replies.try_recv()
            };
            match reply {
                Ok(WriteReply::ExportProgress(percent)) => {
                    if let Some(Dialog {
                        display,
                        panel: Panel::CsvProgress(current),
                    }) = &mut self.dialog
                    {
                        *current = percent;
                        display.dirty = true;
                    }
                }
                Ok(WriteReply::Finished(result)) => {
                    self.pending_writes -= 1;
                    if matches!(result, Ok(Some(_)) | Err((Text::CsvExportError, _))) {
                        self.close_csv_progress();
                    }
                    match result {
                        Err((text, error)) => self
                            .errors
                            .push(format!("{}\n{error}", self.settings.text(text))),
                        Ok(Some([stats, textstats])) if !wait => {
                            let title = self.settings.text(Text::CsvExportTitle);
                            let message = format!(
                                "{}\n{}\n{}",
                                self.settings.text(Text::CsvExportDone),
                                stats.display(),
                                textstats.display()
                            );
                            if !platform::message(&self.main.window, title, &message, false) {
                                let _ = sdl3::messagebox::show_simple_message_box(
                                    sdl3::messagebox::MessageBoxFlag::INFORMATION,
                                    title,
                                    &message,
                                    &self.main.window,
                                );
                            }
                        }
                        Ok(_) => {}
                    }
                }
                Err(mpsc::TryRecvError::Empty) => break,
                Err(mpsc::TryRecvError::Disconnected) => {
                    self.pending_writes = 0;
                    self.close_csv_progress();
                    self.errors
                        .push(self.settings.text(Text::ReplaySaveError).into());
                }
            }
        }
    }

    fn apply_settings(&mut self, draft: Settings) -> Result<(), String> {
        let pixels = self.settings.pixels[self.settings.level];
        let footer = self.settings.identity;
        let counter_pixels = self.settings.counter_pixels;
        self.settings = draft;
        self.round.record_cursor_lock(self.settings.cursor_lock);
        let next = self.settings.pixels[self.settings.level];
        if next != pixels || footer != self.settings.identity {
            self.resize_main(next);
            if let Some(position) = self
                .settings
                .position
                .filter(|_| platform::normal(&self.main.window))
            {
                platform::fit_to_screen(&self.main.window, position);
            }
        }
        let _ = self.main.window.set_title(self.settings.text(Text::Title));
        self.round.set_identity(&self.settings);
        if !self.settings.counter || counter_pixels != self.settings.counter_pixels {
            self.counter = None;
        }
        if self.settings.counter {
            self.show_counter()?;
        }
        if let Some(counter) = &mut self.counter {
            let _ = counter.window.set_title(self.settings.text(Text::Counter));
            self.counter_view.invalidate();
            counter.dirty = true;
        }
        self.update_refresh_rate();
        self.persist();
        self.main.dirty = true;
        self.sync_cursor();
        Ok(())
    }

    fn commit_dialog(&mut self) -> Result<(), String> {
        let Some(dialog) = &mut self.dialog else {
            return Ok(());
        };
        if let Panel::CsvFolder(picker) = &mut dialog.panel {
            dialog.display.dirty = true;
            let Some(directory) = picker.destination() else {
                return Ok(());
            };
            let targets = csv_export::targets(directory, &self.settings.player);
            let Some(overwrite) =
                picker.confirm_overwrite(targets.iter().any(|target| target.exists()))
            else {
                return Ok(());
            };
            self.close_dialog();
            self.open_dialog(
                self.settings.text(Text::CsvExportTitle),
                Panel::CsvProgress(0),
                CSV_PROGRESS_SIZE,
            )?;
            if !self.queue_write(Job::ExportCsv { targets, overwrite }) {
                self.close_csv_progress();
            }
            self.sync_cursor();
            return Ok(());
        }
        match &mut dialog.panel {
            Panel::Settings(form) => {
                if !form.prepare() {
                    dialog.display.dirty = true;
                    return Ok(());
                }
            }
            Panel::Save {
                path, overwrite, ..
            } => {
                if save_path(&self.root, path).is_file() && !*overwrite {
                    *overwrite = true;
                    dialog.display.dirty = true;
                    return Ok(());
                }
            }
            Panel::CsvProgress(_) => return Ok(()),
            Panel::Fullscreen { .. }
            | Panel::Message { .. }
            | Panel::About { .. }
            | Panel::CsvFolder(_) => {}
        }
        let dialog = self.dialog.take().unwrap();
        self.video.text_input().stop(&dialog.display.window);
        drop(dialog.display);
        match dialog.panel {
            Panel::Settings(form) => {
                self.sdl.mouse().capture(false);
                self.main.window.raise();
                self.apply_settings(form.draft)?;
            }
            Panel::Save { path, replay, .. } => {
                if !path.trim().is_empty() {
                    let path = save_path(&self.root, &path);
                    self.queue_replay(replay, Some(path));
                }
            }
            Panel::Fullscreen { mode, .. } => {
                self.sdl.mouse().capture(false);
                self.main.window.raise();
                self.change_fullscreen(Some(mode));
            }
            Panel::Message { .. }
            | Panel::About { .. }
            | Panel::CsvFolder(_)
            | Panel::CsvProgress(_) => {}
        }
        self.main.dirty = true;
        self.sync_cursor();
        Ok(())
    }

    fn dialog_key(&mut self, key: Keycode, mods: Mod) -> Result<(), String> {
        if matches!(
            self.dialog.as_ref().map(|dialog| &dialog.panel),
            Some(Panel::CsvProgress(_))
        ) {
            return Ok(());
        }
        if let Some(Dialog {
            display,
            panel: Panel::CsvFolder(picker),
        }) = &mut self.dialog
        {
            let outcome = picker.key(key, mods, &self.video, display.ui_pixels());
            display.dirty = true;
            return self.folder_picker_outcome(outcome);
        }
        if let Some(Dialog {
            display,
            panel: Panel::Settings(form),
        }) = &mut self.dialog
        {
            let outcome = form.key(key, mods, &self.video);
            display.dirty = true;
            return self.settings_outcome(outcome);
        }
        if key == Keycode::Escape {
            self.close_dialog();
            self.sync_cursor();
            return Ok(());
        }
        if key == Keycode::Return || key == Keycode::KpEnter {
            return self.commit_dialog();
        }
        let control = ctrl(mods);
        let Some(dialog) = &mut self.dialog else {
            return Ok(());
        };
        match &mut dialog.panel {
            Panel::Fullscreen { mode, .. } => {
                match key {
                    Keycode::_1 | Keycode::Kp1 => *mode = FullscreenMode::Board,
                    Keycode::_2 | Keycode::Kp2 => *mode = FullscreenMode::Status,
                    Keycode::_3 | Keycode::Kp3 => *mode = FullscreenMode::Counter,
                    Keycode::Up | Keycode::Down | Keycode::Left | Keycode::Right | Keycode::Tab => {
                        let index = match *mode {
                            FullscreenMode::Board => 0,
                            FullscreenMode::Status => 1,
                            FullscreenMode::Counter => 2,
                        };
                        let backwards = matches!(key, Keycode::Up | Keycode::Left)
                            || key == Keycode::Tab
                                && mods.intersects(Mod::LSHIFTMOD | Mod::RSHIFTMOD);
                        let count = FULLSCREEN_CHOICES.len();
                        let step = if backwards { count - 1 } else { 1 };
                        *mode = FULLSCREEN_CHOICES[(index + step) % count].0;
                        dialog.display.dirty = true;
                        return Ok(());
                    }
                    _ => return Ok(()),
                }
                return self.commit_dialog();
            }
            Panel::Save {
                path,
                select,
                overwrite,
                ..
            } => {
                edit_text(
                    path,
                    select,
                    key,
                    control,
                    if control && key == Keycode::V {
                        self.video.clipboard().clipboard_text().ok()
                    } else {
                        None
                    },
                    2048,
                );
                *overwrite = false;
            }
            Panel::Message { .. }
            | Panel::About { .. }
            | Panel::Settings(_)
            | Panel::CsvFolder(_)
            | Panel::CsvProgress(_) => {}
        }
        dialog.display.dirty = true;
        Ok(())
    }

    fn settings_outcome(&mut self, outcome: Outcome) -> Result<(), String> {
        match outcome {
            Outcome::Stay => Ok(()),
            Outcome::Apply => self.commit_dialog(),
            Outcome::Cancel => {
                self.close_dialog();
                self.sync_cursor();
                Ok(())
            }
        }
    }

    fn folder_picker_outcome(&mut self, outcome: folder_picker::Outcome) -> Result<(), String> {
        match outcome {
            folder_picker::Outcome::Stay => Ok(()),
            folder_picker::Outcome::Choose => self.commit_dialog(),
            folder_picker::Outcome::Cancel => {
                self.close_dialog();
                self.sync_cursor();
                Ok(())
            }
        }
    }

    fn dialog_click(&mut self, x: f32, y: f32, clicks: u8) -> Result<(), String> {
        let Some(dialog) = &mut self.dialog else {
            return Ok(());
        };
        let (x, y) = dialog.display.ui_point(x, y);
        let (width, height) = dialog.display.ui_pixels();
        if matches!(dialog.panel, Panel::CsvProgress(_)) {
            return Ok(());
        }
        if let Panel::CsvFolder(picker) = &mut dialog.panel {
            if folder_picker::path_field(width).contains(x, y) {
                if picker.composing() {
                    unsafe {
                        sdl3_sys::keyboard::SDL_ClearComposition(dialog.display.window.raw());
                    }
                    picker.composition(String::new(), 0, 0);
                }
                let shift = self
                    .sdl
                    .keyboard()
                    .mod_state()
                    .intersects(Mod::LSHIFTMOD | Mod::RSHIFTMOD);
                picker.path_click(x, width, clicks, shift, |text| {
                    dialog.display.measure_setting(text)
                });
                if picker.dragging {
                    self.sdl.mouse().capture(true);
                }
                dialog.display.dirty = true;
                return Ok(());
            }
            let outcome = picker.click((x, y), (width, height), clicks);
            dialog.display.dirty = true;
            return self.folder_picker_outcome(outcome);
        }
        if let Panel::Settings(form) = &mut dialog.panel {
            if form.composing() {
                unsafe {
                    sdl3_sys::keyboard::SDL_ClearComposition(dialog.display.window.raw());
                }
                form.clear_composition();
            }
            let shift = self
                .sdl
                .keyboard()
                .mod_state()
                .intersects(Mod::LSHIFTMOD | Mod::RSHIFTMOD);
            form.click((x, y), (width, height), clicks, shift, |text| {
                dialog.display.measure_setting(text)
            });
            if form.capturing() {
                self.sdl.mouse().capture(true);
            }
            dialog.display.dirty = true;
            return Ok(());
        }
        if let Panel::Fullscreen { pointer, .. } = &mut dialog.panel {
            let choice = fullscreen_choice_at((width, height), (x, y));
            pointer.motion(choice);
            pointer.pressed = choice;
            if choice.is_some() {
                self.sdl.mouse().capture(true);
            }
            dialog.display.dirty = true;
        } else if let Panel::About { version_clicks } = &mut dialog.panel {
            if view::about_version(width).contains(x, y) {
                *version_clicks += 1;
                if *version_clicks == 5 {
                    self.close_dialog();
                    self.show_easter_egg(
                        Text::EasterEggGuide,
                        Text::EasterEggTriggers,
                        (510, 300),
                    )?;
                }
            } else {
                *version_clicks = 0;
                if view::dialog_button(width, height, false).contains(x, y) {
                    self.close_dialog();
                }
            }
        } else if matches!(dialog.panel, Panel::Message { .. }) {
            if view::dialog_button(width, height, false).contains(x, y) {
                self.close_dialog();
            }
        } else if view::dialog_button(width, height, true).contains(x, y) {
            self.commit_dialog()?;
        } else if view::dialog_button(width, height, false).contains(x, y) {
            self.close_dialog();
        }
        Ok(())
    }

    fn dialog_release(&mut self, window_id: u32, x: f32, y: f32) -> Result<(), String> {
        let Some(dialog) = &mut self.dialog else {
            return Ok(());
        };
        let same_window = dialog.display.window.id() == window_id;
        let point = if same_window {
            dialog.display.ui_point(x, y)
        } else {
            (-1, -1)
        };
        let size = dialog.display.ui_pixels();
        match &mut dialog.panel {
            Panel::CsvFolder(picker) if picker.dragging => {
                picker.dragging = false;
                self.sdl.mouse().capture(false);
                if !folder_picker::path_field(size.0).contains(point.0, point.1) {
                    restore_default_cursor();
                }
            }
            Panel::Settings(form) if form.capturing() => {
                self.sdl.mouse().capture(false);
                let outcome = form.release(point, size);
                dialog.display.dirty = true;
                self.settings_outcome(outcome)?;
            }
            Panel::Fullscreen { mode, pointer } if pointer.pressed.is_some() => {
                self.sdl.mouse().capture(false);
                let selected = pointer.release(fullscreen_choice_at(size, point));
                dialog.display.dirty = true;
                if let Some(selected) = selected {
                    *mode = selected;
                    self.commit_dialog()?;
                }
            }
            _ => {}
        }
        Ok(())
    }

    fn release_cursor(&mut self) {
        if !self.confinement {
            return;
        }
        platform::release_cursor(&mut self.main.window);
        self.confinement = false;
    }

    fn sync_cursor(&mut self) {
        if !self.settings.cursor_lock
            || self.wayland
            || self.dialog.is_some()
            || self.resized_at.is_some()
            || unsafe { sdl3_sys::keyboard::SDL_GetKeyboardFocus() } != self.main.window.raw()
        {
            self.release_cursor();
            return;
        }
        if self.confinement {
            return;
        }
        let r = self.grid();
        let (x, y) = self.main.logical(r.0, r.1);
        let (right, bottom) = self.main.logical(r.0 + r.2, r.1 + r.3);
        let region = Rect::new(x, y, (right - x).max(1) as u32, (bottom - y).max(1) as u32);
        self.confinement = platform::confine_cursor(&mut self.main.window, region);
    }

    fn replay_point(&self, grid: Box2, x: i32, y: i32) -> (usize, usize) {
        let tile = self.layout.tile as usize;
        if grid.contains(x, y) {
            (
                (x - grid.0) as usize * CELL_PIXELS / tile,
                (y - grid.1) as usize * CELL_PIXELS / tile,
            )
        } else {
            (
                grid.2 as usize * CELL_PIXELS / tile,
                grid.3 as usize * CELL_PIXELS / tile,
            )
        }
    }

    fn grid(&self) -> Box2 {
        let size = self.main.pixels();
        if self.fullscreen {
            self.layout
                .fullscreen_regions(
                    self.settings.level,
                    size,
                    self.fullscreen_mode,
                    self.settings.counter_config.len(),
                )
                .grid
        } else {
            self.layout
                .grid(self.settings.level, size, self.settings.identity)
        }
    }

    fn cancel_input(&mut self) {
        self.cancel_input_at(Duration::ZERO);
    }

    fn cancel_input_at(&mut self, delay: Duration) {
        if self.held != 0 {
            let (x, y) = self.replay_point(self.grid(), -1, -1);
            for (bit, command) in [(1, 1), (2, 3)] {
                if self.held & bit != 0 {
                    self.round.play(command, x, y, &self.settings, delay);
                }
            }
            self.held = 0;
        }
        self.restart_pressed = false;
        self.status_clicks = 0;
        self.release_cursor();
        self.sdl.mouse().capture(false);
        self.main.dirty = true;
    }

    fn show_easter_egg(
        &mut self,
        title: Text,
        message: Text,
        size: (u32, u32),
    ) -> Result<(), String> {
        if self.fullscreen && !self.change_fullscreen(None) {
            return Ok(());
        }
        self.open_dialog(
            self.settings.text(title),
            Panel::Message {
                text: self.settings.text(message).into(),
            },
            size,
        )?;
        if let Some(dialog) = &self.dialog {
            #[cfg(windows)]
            platform::set_dialog_caption_buttons(&dialog.display.window, true);
            platform::center_settings(&dialog.display.window, &self.main.window);
        }
        Ok(())
    }

    fn restart_from_status(&mut self) -> Result<(), String> {
        let clicks = self.status_clicks + 1;
        self.action(Action::Restart)?;
        if clicks < 5 {
            self.status_clicks = clicks;
            Ok(())
        } else {
            self.show_easter_egg(
                Text::SmileyMeltdown,
                Text::SmileyMeltdownMessage,
                (300, 106),
            )
        }
    }

    fn mouse(
        &mut self,
        btn: MouseButton,
        down: bool,
        position: (f32, f32),
        timestamp: u64,
    ) -> Result<(), String> {
        let (x, y) = self.main.point(position.0, position.1);
        self.pointer = (x, y);
        self.main.dirty = true;
        if !self.fullscreen && btn == MouseButton::Left && down && y < MENU && self.held == 0 {
            if self.timer_restart_at.is_some() {
                self.restart_from_status()?;
                if self.dialog.is_some() {
                    return Ok(());
                }
            }
            self.status_clicks = 0;
            let choice = self
                .menu
                .top
                .iter()
                .find(|(rect, _)| rect.contains(x, y))
                .map(|(_, i)| *i);
            self.menu.open = choice.filter(|choice| self.menu.open != Some(*choice));
            return Ok(());
        }
        if self.menu.open.is_some() {
            if !down || btn != MouseButton::Left {
                return Ok(());
            }
            let choice = self
                .menu
                .options
                .iter()
                .find(|(rect, _)| rect.contains(x, y))
                .map(|(_, c)| *c);
            self.menu.open = None;
            if let Some(Choice::Command(action)) = choice {
                self.action(action)?;
            }
            if let Some(Choice::Menu(index)) = choice {
                self.menu.open = Some(index);
            }
            return Ok(());
        }
        let size = self.main.pixels();
        let status = if self.fullscreen {
            self.layout
                .fullscreen_regions(
                    self.settings.level,
                    size,
                    self.fullscreen_mode,
                    self.settings.counter_config.len(),
                )
                .status
        } else {
            Some(self.layout.status(size.0))
        };
        let over_status = status.is_some_and(|status| status.contains(x, y));
        let over_timer = self.round.ended()
            && status.is_some_and(|status| self.layout.status_timer(status).contains(x, y));
        if btn == MouseButton::Left && down {
            if let Some(deadline) = self.timer_restart_at.take() {
                if over_timer && Instant::now() <= deadline {
                    return self.show_easter_egg(
                        Text::TimerOnStrike,
                        Text::TimerOnStrikeMessage,
                        (340, 112),
                    );
                }
                self.restart_from_status()?;
                if self.dialog.is_some() {
                    return Ok(());
                }
            }
        }
        if down && (btn != MouseButton::Left || !over_status) {
            self.status_clicks = 0;
        }
        if btn == MouseButton::Left && self.held == 0 && (self.restart_pressed || over_status) {
            if !down && self.restart_pressed {
                if over_status {
                    if over_timer {
                        self.restart_pressed = false;
                        self.sdl.mouse().capture(false);
                        let interval =
                            platform::double_click_time().max(Duration::from_millis(500));
                        self.timer_restart_at = Some(Instant::now() + interval);
                        return Ok(());
                    }
                    return self.restart_from_status();
                }
                self.status_clicks = 0;
            }
            self.restart_pressed = down && over_status;
            self.sdl.mouse().capture(self.restart_pressed);
            return Ok(());
        }
        if self.round.ended() {
            if down && btn == MouseButton::Right {
                if self.round.phase() == 2
                    && status.is_some_and(|status| self.layout.status_face(status).contains(x, y))
                {
                    return self.show_easter_egg(
                        Text::MinesOffDuty,
                        Text::MinesOffDutyMessage,
                        (380, 122),
                    );
                }
                if self.round.phase() == 3 {
                    let grid = self.grid();
                    if let Some((col, row)) = grid.cell_at((x, y), self.layout.tile) {
                        let cols = grid.2 / self.layout.tile;
                        if self.round.cells.get((row * cols + col) as usize) == Some(&15) {
                            return self.show_easter_egg(
                                Text::MineProtest,
                                Text::MineProtestMessage,
                                (300, 106),
                            );
                        }
                    }
                }
            }
            return Ok(());
        }
        let bit = match btn {
            MouseButton::Left => 1,
            MouseButton::Right => 2,
            _ => return Ok(()),
        };
        let grid = self.grid();
        let inside = grid.contains(x, y);
        if down && (!inside || self.held & bit != 0) || !down && self.held & bit == 0 {
            return Ok(());
        }
        if down {
            self.held |= bit;
        } else {
            self.held &= !bit;
        }
        let (x, y) = self.replay_point(grid, x, y);
        self.round.play(
            (bit - 1) as u32 * 2 + u32::from(!down),
            x,
            y,
            &self.settings,
            input_delay(timestamp),
        );
        let auto_restart = self
            .round
            .should_auto_restart(self.settings.auto_replay_threshold());
        self.finish(auto_restart);
        if auto_restart {
            return self.action(Action::Restart);
        }
        if self.round.ended() {
            self.held = 0;
        }
        self.sdl.mouse().capture(self.held != 0);
        self.sync_cursor();
        if let Some(counter) = &mut self.counter {
            counter.dirty = true;
        }
        Ok(())
    }

    fn record_unfinished_round(&mut self) {
        if self.round.phase() == 1 {
            let record = self.round.stats(&self.settings, GameResult::Restart, None);
            self.queue_write(Job::Stats(record));
        }
    }

    fn finish(&mut self, auto_restart: bool) {
        if !self.round.ended() || self.last_saved_round {
            return;
        }
        self.last_saved_round = true;
        let won = self.round.phase() == 2;
        let result = if won {
            GameResult::Win
        } else {
            GameResult::Loss
        };
        let replay = self
            .round
            .timing_valid
            .then(|| self.round.replay(&self.settings));
        let record = self.round.stats(
            &self.settings,
            result,
            replay.as_ref().and_then(|result| result.as_ref().ok()),
        );
        self.queue_write(Job::Stats(record));
        if !self.round.timing_valid {
            self.errors
                .push(self.settings.text(Text::TimingWarning).into());
        } else if let Some(replay) = replay.filter(|_| {
            !auto_restart && (self.settings.autosave == 0 || (self.settings.autosave == 1 && won))
        }) {
            match replay {
                Ok(replay) => self.queue_replay(replay, None),
                Err(error) => self.errors.push(format!(
                    "{}\n{error}",
                    self.settings.text(Text::ReplayGenerationError)
                )),
            }
        }
    }

    fn event(&mut self, event: Event) -> Result<(), String> {
        match event {
            Event::Quit { .. } => self.quit = true,
            Event::Display { display_event, .. } => match display_event {
                DisplayEvent::Removed => {
                    if self.fullscreen && !self.change_fullscreen(None) {
                        return Ok(());
                    }
                    platform::recover_window(&self.main.window);
                    if let Some(counter) = &self.counter {
                        platform::recover_window(&counter.window);
                    }
                    self.update_refresh_rate();
                }
                DisplayEvent::CurrentModeChanged
                | DisplayEvent::DesktopModeChanged
                | DisplayEvent::Added => {
                    self.update_refresh_rate();
                }
                _ => {}
            },
            Event::Window {
                timestamp,
                window_id,
                win_event,
                ..
            } => self.window_event(window_id, win_event, timestamp)?,
            Event::KeyDown {
                keycode,
                scancode,
                keymod,
                repeat,
                window_id,
                ..
            } => {
                if let Some(dialog) = &self.dialog {
                    if window_id == dialog.display.window.id()
                        && (!repeat
                            || matches!(dialog.panel, Panel::Settings(_) | Panel::CsvFolder(_))
                                && matches!(
                                    keycode,
                                    Some(
                                        Keycode::Left
                                            | Keycode::Right
                                            | Keycode::Up
                                            | Keycode::Down
                                            | Keycode::PageUp
                                            | Keycode::PageDown
                                            | Keycode::Home
                                            | Keycode::End
                                            | Keycode::Backspace
                                            | Keycode::Delete
                                    )
                                ))
                    {
                        if let Some(key) = keycode {
                            return self.dialog_key(key, keymod);
                        }
                        return Ok(());
                    }
                    return Ok(());
                }
                if repeat {
                    return Ok(());
                }
                if keycode == Some(Keycode::Escape) {
                    self.menu.open = None;
                    self.main.dirty = true;
                } else if let Some(action) = shortcut(keycode, scancode, keymod) {
                    if !matches!(action, Action::CursorLock | Action::ExportCsv)
                        || window_id == self.main.window.id()
                    {
                        self.action(action)?;
                    }
                }
            }
            Event::TextInput {
                text, window_id, ..
            } => {
                if let Some(dialog) = &mut self.dialog {
                    if dialog.display.window.id() != window_id {
                        return Ok(());
                    }
                    match &mut dialog.panel {
                        Panel::Settings(form) => form.text(&text),
                        Panel::CsvFolder(picker) => picker.text(&text),
                        Panel::Save {
                            path,
                            select,
                            overwrite,
                            ..
                        } => {
                            append_text(path, select, &text, 2048);
                            *overwrite = false;
                        }
                        _ => {}
                    }
                    dialog.display.dirty = true;
                }
            }
            Event::TextEditing {
                text,
                start,
                length,
                window_id,
                ..
            } => {
                if let Some(Dialog { display, panel }) = self
                    .dialog
                    .as_mut()
                    .filter(|dialog| dialog.display.window.id() == window_id)
                {
                    match panel {
                        Panel::Settings(form) => form.composition(text, start, length),
                        Panel::CsvFolder(picker) => picker.composition(text, start, length),
                        _ => return Ok(()),
                    }
                    display.dirty = true;
                }
            }
            Event::MouseWheel {
                window_id,
                y,
                direction,
                mouse_x,
                mouse_y,
                ..
            } => {
                if let Some(Dialog { display, panel }) = self
                    .dialog
                    .as_mut()
                    .filter(|dialog| dialog.display.window.id() == window_id && y != 0.0)
                {
                    let step = if y > 0.0 { -1 } else { 1 };
                    let step = if direction == sdl3::mouse::MouseWheelDirection::Flipped {
                        -step
                    } else {
                        step
                    };
                    match panel {
                        Panel::Settings(form) => {
                            form.wheel(step * 3);
                            form.motion(display.ui_point(mouse_x, mouse_y), display.ui_pixels());
                        }
                        Panel::CsvFolder(picker) => {
                            picker.scroll(step as isize * 3, display.ui_pixels().1)
                        }
                        _ => return Ok(()),
                    }
                    display.dirty = true;
                }
            }
            Event::MouseMotion {
                window_id, x, y, ..
            } if self.dialog.is_some() => {
                if let Some(Dialog { display, panel }) = self
                    .dialog
                    .as_mut()
                    .filter(|dialog| dialog.display.window.id() == window_id)
                {
                    let point = display.ui_point(x, y);
                    let size = display.ui_pixels();
                    match panel {
                        Panel::CsvFolder(picker) => {
                            if picker.dragging
                                || folder_picker::path_field(size.0).contains(point.0, point.1)
                            {
                                if let Some(cursor) = &self.text_cursor {
                                    cursor.set();
                                }
                            } else {
                                restore_default_cursor();
                            }
                            if picker.dragging {
                                picker.path_drag(point.0, size.0, |text| {
                                    display.measure_setting(text)
                                });
                                display.dirty = true;
                            }
                        }
                        Panel::Settings(form) => {
                            display.dirty |= form.motion(point, size);
                            if form.dragging {
                                form.drag(point.0, size.0, |text| display.measure_setting(text));
                                display.dirty = true;
                            }
                        }
                        Panel::Fullscreen { pointer, .. } => {
                            display.dirty |= pointer.motion(fullscreen_choice_at(size, point));
                        }
                        _ => {}
                    }
                }
            }
            Event::MouseMotion {
                timestamp,
                window_id,
                x,
                y,
                ..
            } if window_id == self.main.window.id() && self.dialog.is_none() => {
                let pos = self.main.point(x, y);
                let menu_hover = !self.fullscreen
                    && (self.menu.open.is_some() || pos.1 < MENU || self.pointer.1 < MENU);
                let preview_active = self.held != 0 && self.round.mouse_visual() != 0;
                let track_pointer = self.menu.open.is_none();
                if preview_active || track_pointer {
                    let grid = self.grid();
                    self.main.dirty |= preview_active
                        && grid.cell_at(pos, self.layout.tile)
                            != grid.cell_at(self.pointer, self.layout.tile);
                    if track_pointer {
                        let (x, y) = self.replay_point(grid, pos.0, pos.1);
                        self.round.track(x, y, input_delay(timestamp));
                    }
                }
                self.main.dirty |= menu_hover;
                self.pointer = pos;
            }
            Event::MouseButtonDown {
                timestamp,
                window_id,
                mouse_btn,
                x,
                y,
                clicks,
                ..
            } => {
                if let Some(dialog) = &mut self.dialog {
                    if dialog.display.window.id() == window_id && mouse_btn == MouseButton::Left {
                        self.dialog_click(x, y, clicks)?;
                    } else {
                        dialog.display.window.raise();
                    }
                } else if window_id == self.main.window.id() {
                    self.mouse(mouse_btn, true, (x, y), timestamp)?;
                } else if let Some(counter) = &self.counter {
                    let (px, py) = counter.point(x, y);
                    let can_close = counter.hook.is_none();
                    if can_close
                        && window_id == counter.window.id()
                        && (0..37).contains(&py)
                        && px >= counter.pixels().0 - 24
                    {
                        self.action(Action::Counter)?;
                    }
                }
            }
            Event::MouseButtonUp {
                window_id,
                mouse_btn: MouseButton::Left,
                x,
                y,
                ..
            } if self.dialog.is_some() => {
                self.dialog_release(window_id, x, y)?;
            }
            Event::MouseButtonUp {
                timestamp,
                window_id,
                mouse_btn,
                x,
                y,
                ..
            } if window_id == self.main.window.id() && self.dialog.is_none() => {
                self.mouse(mouse_btn, false, (x, y), timestamp)?;
            }
            _ => {}
        }
        Ok(())
    }

    fn window_event(&mut self, id: u32, event: WindowEvent, timestamp: u64) -> Result<(), String> {
        if id == self.main.window.id() {
            match event {
                WindowEvent::CloseRequested => self.quit = true,
                WindowEvent::Resized(width, height)
                    if !self.fullscreen
                        && self.main.window.size() == (width as u32, height as u32) =>
                {
                    self.user_resize()
                }
                WindowEvent::PixelSizeChanged(width, height)
                    if !self.fullscreen && self.main.pixels() == (width, height) =>
                {
                    let preferred = self.settings.pixels[self.settings.level];
                    if self.resized_at.is_none()
                        && self
                            .layout
                            .size(self.settings.level, self.settings.identity)
                            != (width, height)
                    {
                        self.resize_main(preferred);
                    }
                    self.main.dirty = true;
                }
                WindowEvent::Resized(..) | WindowEvent::PixelSizeChanged(..) => {
                    self.release_cursor();
                    self.main.dirty = true;
                }
                WindowEvent::Moved(..) if !self.wayland => {
                    self.release_cursor();
                    self.remember_main_position();
                }
                WindowEvent::FocusLost => {
                    self.menu.open = None;
                    self.cancel_input_at(input_delay(timestamp));
                }
                WindowEvent::Minimized | WindowEvent::Hidden => self.release_cursor(),
                WindowEvent::FocusGained => self.sync_cursor(),
                WindowEvent::MouseLeave if self.held == 0 => {
                    self.pointer = (-1, -1);
                    let (x, y) = self.replay_point(self.grid(), -1, -1);
                    self.round.track(x, y, input_delay(timestamp));
                    self.main.dirty = true;
                }
                WindowEvent::DisplayChanged(..) => {
                    self.update_refresh_rate();
                    if !self.fullscreen {
                        self.resize_main(self.layout.tile);
                    }
                }
                WindowEvent::Restored | WindowEvent::Shown => {
                    if !self.fullscreen {
                        platform::recover_window(&self.main.window);
                    }
                    self.main.dirty = true;
                }
                WindowEvent::Exposed => self.main.dirty = true,
                _ => {}
            }
        } else if self
            .dialog
            .as_ref()
            .is_some_and(|d| d.display.window.id() == id)
        {
            if event == WindowEvent::CloseRequested {
                if !matches!(
                    self.dialog.as_ref().map(|dialog| &dialog.panel),
                    Some(Panel::CsvProgress(_))
                ) {
                    self.close_dialog();
                }
            } else if let Some(dialog) = self.dialog.as_mut() {
                match (&mut dialog.panel, event) {
                    (Panel::Settings(form), WindowEvent::FocusLost) => {
                        form.clear_composition();
                        if form.capturing() {
                            self.sdl.mouse().capture(false);
                        }
                        form.cancel_pointer();
                    }
                    (Panel::Settings(form), WindowEvent::MouseLeave) => form.mouse_leave(),
                    (Panel::CsvFolder(picker), WindowEvent::FocusLost) => {
                        picker.composition(String::new(), 0, 0);
                        if picker.dragging {
                            picker.dragging = false;
                            self.sdl.mouse().capture(false);
                        }
                        restore_default_cursor();
                    }
                    (Panel::CsvFolder(picker), WindowEvent::MouseLeave) if !picker.dragging => {
                        restore_default_cursor();
                    }
                    (Panel::Fullscreen { pointer, .. }, WindowEvent::FocusLost) => {
                        if pointer.pressed.is_some() {
                            self.sdl.mouse().capture(false);
                        }
                        *pointer = view::ButtonPointer::default();
                    }
                    (Panel::Fullscreen { pointer, .. }, WindowEvent::MouseLeave) => {
                        pointer.motion(None);
                    }
                    _ => {}
                }
                dialog.display.dirty = true;
            }
        } else if self
            .counter
            .as_ref()
            .is_some_and(|counter| counter.window.id() == id && (!self.fullscreen || counter.shown))
        {
            match event {
                WindowEvent::CloseRequested => self.action(Action::Counter)?,
                WindowEvent::Moved(..) if !self.wayland => {
                    if let Some(position) = self
                        .counter
                        .as_ref()
                        .and_then(|counter| platform::window_position(&counter.window))
                    {
                        self.settings.counter_position = Some(position);
                    }
                }
                WindowEvent::DisplayChanged(..) => self.update_refresh_rate(),
                WindowEvent::Exposed
                | WindowEvent::Resized(..)
                | WindowEvent::PixelSizeChanged(..)
                | WindowEvent::Restored
                | WindowEvent::Shown => {
                    self.counter_view.invalidate();
                    if let Some(counter) = &mut self.counter {
                        if matches!(
                            event,
                            WindowEvent::Resized(..) | WindowEvent::PixelSizeChanged(..)
                        ) && counter.ui_pixels()
                            != CounterLayout::new(self.settings.counter_pixels)
                                .size(self.settings.counter_config.len())
                        {
                            self.counter_resize_at = Some(Instant::now());
                        }
                        if matches!(event, WindowEvent::Restored | WindowEvent::Shown) {
                            platform::recover_window(&counter.window);
                        }
                        counter.dirty = true;
                    }
                }
                _ => {}
            }
        }
        Ok(())
    }

    fn update(&mut self, now: Instant, refresh: bool) -> Result<(), String> {
        if let Some(position) = self
            .counter
            .as_ref()
            .and_then(|counter| counter.hook.as_ref())
            .and_then(platform::WindowHook::moved_position)
        {
            self.settings.counter_position = Some(position);
            self.persist();
            self.update_refresh_rate();
        }
        if self
            .resized_at
            .is_some_and(|since| now.saturating_duration_since(since) >= RESIZE_SETTLE)
        {
            self.resize_main(self.layout.tile);
            self.persist();
            self.sync_cursor();
        }
        if self
            .counter_resize_at
            .is_some_and(|since| now.saturating_duration_since(since) >= RESIZE_SETTLE)
        {
            self.settle_counter_resize();
        }
        if refresh && self.refreshing() {
            if now.saturating_duration_since(self.refresh_checked) >= REFRESH_RECHECK {
                self.update_refresh_rate();
            }
            let previous_second = self.round.seconds() as u32;
            self.round.refresh();
            let timer_visible = !self.fullscreen || self.fullscreen_mode == FullscreenMode::Status;
            self.main.dirty |= timer_visible && previous_second != self.round.seconds() as u32;
            if let Some(counter) = &mut self.counter {
                counter.dirty = true;
            }
        }
        if self.round.phase() == 1 && !self.round.timing_valid {
            self.action(Action::Restart)?;
        }
        self.collect_write_replies(false);
        if self.pending_writes == 0
            && self.dialog.is_none()
            && std::mem::take(&mut self.save_requested)
        {
            self.action(Action::Save)?;
        }
        if self.dialog.is_none() && !self.errors.is_empty() {
            let error = self.errors.remove(0);
            self.cancel_input();
            if platform::message(
                &self.main.window,
                self.settings.text(Text::Title),
                &error,
                true,
            ) {
                self.sync_cursor();
                return Ok(());
            }
            self.open_dialog(
                self.settings.text(Text::Title),
                Panel::Message { text: error },
                (490, 190),
            )?;
        }
        Ok(())
    }

    fn draw(&mut self, events: &EventPump, refresh: bool) -> Result<(), String> {
        let fullscreen = self.fullscreen;
        let fullscreen_mode = self.fullscreen_mode;
        let (settings, round) = (&self.settings, &self.round);
        let counter_refresh = refresh && fullscreen && fullscreen_mode == FullscreenMode::Counter;
        if self.main.dirty || counter_refresh {
            let (art, menu) = (&mut self.art, &mut self.menu);
            let (layout, pointer, restart) = (self.layout, self.pointer, self.restart_pressed);
            let fullscreen_counter = &mut self.fullscreen_counter;
            let full_redraw = self.main.dirty;
            self.main.dirty = false;
            self.main.buffer.present_regions(
                &self.main.window,
                events,
                self.main.ui_scale,
                |p, w, h| {
                    if fullscreen {
                        view::fullscreen(
                            p,
                            art,
                            settings,
                            round,
                            layout,
                            pointer,
                            restart,
                            (w, h),
                            fullscreen_mode,
                            fullscreen_counter,
                            full_redraw,
                        )
                    } else {
                        view::game(
                            p,
                            art,
                            settings,
                            round,
                            layout,
                            menu,
                            pointer,
                            restart,
                            (w, h),
                        );
                        None
                    }
                },
            )?;
        }
        if let Some(counter) = self
            .counter
            .as_mut()
            .filter(|counter| counter.dirty && (!fullscreen || counter.shown))
        {
            let close = counter.hook.is_none();
            let values = settings.counter_config.values(
                round,
                settings.text(Text::Standard),
                settings.text(Text::UnsupportedFormula),
            );
            counter.buffer.present_regions(
                &counter.window,
                events,
                counter.ui_scale,
                |p, w, h| self.counter_view.draw(p, settings, values, w, h, close),
            )?;
            counter.dirty = false;
        }
        if let Some(Dialog { display, panel }) = &mut self.dialog {
            let size = match panel {
                Panel::Settings(_) => Some(settings_ui::SIZE),
                Panel::CsvFolder(_) => Some(folder_picker::SIZE),
                Panel::CsvProgress(_) => Some(CSV_PROGRESS_SIZE),
                Panel::About { .. } => Some(ABOUT_SIZE),
                _ => None,
            };
            if let Some(size) = size {
                let scale = platform::dpi_scale(&display.window);
                if scale != display.ui_scale {
                    let (width, height) =
                        scaled_size(size, scale / window_pixel_density(&display.window));
                    let _ = display.window.set_size(width, height);
                    display.ui_scale = scale;
                    display.dirty = true;
                }
            }
            if display.dirty {
                let input_position = match panel {
                    Panel::Settings(form) => {
                        Some(form.input_position(display.ui_pixels().0, |text| {
                            display.measure_setting(text)
                        }))
                    }
                    Panel::CsvFolder(picker) if display.shown => {
                        Some(picker.input_position(display.ui_pixels().0, |text| {
                            display.measure_setting(text)
                        }))
                    }
                    _ => None,
                };
                if let Some(position) = input_position {
                    let input = self.video.text_input();
                    if let Some((area, caret)) = position {
                        let (x, y) = display.ui_to_window(area.0, area.1);
                        let (right, bottom) =
                            display.ui_to_window(area.0 + area.2, area.1 + area.3);
                        let (cursor, _) = display.ui_to_window(area.0 + caret, area.1);
                        input.set_rect(
                            &display.window,
                            Rect::new(x, y, (right - x).max(1) as u32, (bottom - y).max(1) as u32),
                            cursor - x,
                        );
                        if !input.is_active(&display.window) {
                            input.start(&display.window);
                        }
                    } else if input.is_active(&display.window) {
                        input.stop(&display.window);
                    }
                }
            }
            display.draw(events, |p, w, h| match panel {
                Panel::Settings(form) => form.draw(p, w, h),
                Panel::Fullscreen { mode, pointer } => {
                    p.fill(Box2(0, 0, w, h), 0xf5f5f5);
                    for (choice, label, shortcut) in FULLSCREEN_CHOICES {
                        let area = view::fullscreen_button(w, h, choice);
                        view::control_button(
                            p,
                            area,
                            "",
                            pointer.state(choice, true),
                            *mode == choice,
                        );
                        let Box2(x, y, width, height) = area;
                        p.text(
                            Box2(x + 6, y, 13, height),
                            shortcut,
                            12,
                            Align::Center,
                            0x465768,
                        );
                        p.text(
                            Box2(x + 21, y, width - 25, height),
                            settings.text(label),
                            15,
                            Align::Center,
                            INK,
                        );
                    }
                }
                Panel::Save {
                    path,
                    overwrite,
                    select,
                    ..
                } => {
                    p.fill(Box2(0, 0, w, h), 0xf5f5f5);
                    let area = Box2(12, 13, w - 24, 33);
                    p.fill(area, if *select { 0xd5e9ff } else { WHITE });
                    p.border(area, 0x467eac);
                    p.text(area.inset(5), path, 15, Align::Left, INK);
                    if *overwrite {
                        p.text(
                            Box2(12, 48, w - 24, 25),
                            settings.text(Text::OverwriteReplay),
                            15,
                            Align::Left,
                            0x8a3030,
                        );
                    }
                    view::button(p, view::dialog_button(w, h, true), settings.text(Text::Ok));
                    view::button(
                        p,
                        view::dialog_button(w, h, false),
                        settings.text(Text::Cancel),
                    );
                }
                Panel::CsvFolder(picker) => picker.draw(p, settings, w, h),
                Panel::CsvProgress(percent) => {
                    view::csv_progress(p, settings.text(Text::CsvExporting), *percent, w, h)
                }
                Panel::About { .. } => {
                    p.fill(Box2(0, 0, w, h), 0xf5f5f5);
                    p.text(
                        Box2(12, 12, w - 24, 28),
                        settings.text(Text::Title),
                        18,
                        Align::Center,
                        INK,
                    );
                    p.text(
                        view::about_version(w),
                        concat!("v", env!("CARGO_PKG_VERSION")),
                        15,
                        Align::Center,
                        INK,
                    );
                    view::button(p, view::dialog_button(w, h, false), settings.text(Text::Ok));
                }
                Panel::Message { text } => view::message(p, text, settings.text(Text::Ok), w, h),
            })?;
        }
        Ok(())
    }

    fn run(mut self) -> Result<(), String> {
        let mut events = self.sdl.event_pump().map_err(|e| e.to_string())?;
        let mut timer = RefreshTimer::default();
        let mut refresh = false;
        let mut capture_guard = false;
        while !self.quit {
            self.update(Instant::now(), refresh)?;
            self.sync_cursor();
            let protect = self.round.phase() == 1 && !self.round.player.starts_with("[live]");
            if protect != capture_guard {
                platform::set_capture_guard(&self.main.window, protect);
                capture_guard = protect;
            }
            self.draw(&events, refresh)?;
            if self.reveal() {
                self.draw(&events, false)?;
                self.restore_positions();
                self.uncloak();
            }
            timer.sync(self.wake_type, self.refresh_period())?;
            let resize = self
                .resized_at
                .into_iter()
                .chain(self.counter_resize_at)
                .map(|since| (since + RESIZE_SETTLE).saturating_duration_since(Instant::now()));
            let replay = (self.pending_writes > 0).then_some(Duration::from_millis(20));
            let timer_restart = self
                .timer_restart_at
                .map(|deadline| deadline.saturating_duration_since(Instant::now()));
            let timeout = resize.chain(replay).chain(timer_restart).min();
            let first = match timeout {
                Some(timeout) => {
                    events.wait_event_timeout_ms(timeout.as_nanos().div_ceil(1_000_000) as u32)
                }
                None => Some(events.wait_event()),
            };
            refresh = false;
            for event in first.into_iter().chain(events.poll_iter()) {
                if matches!(event, Event::User { type_, code: REFRESH_TICK, .. } if type_ == self.wake_type)
                {
                    refresh = true;
                } else {
                    self.event(event)?;
                }
                if self.quit {
                    break;
                }
            }
            if !self.quit
                && self
                    .timer_restart_at
                    .is_some_and(|deadline| Instant::now() >= deadline)
            {
                self.restart_from_status()?;
            }
        }
        drop(timer);
        self.release_cursor();
        self.sdl.mouse().capture(false);
        self.record_unfinished_round();
        self.collect_write_replies(true);
        if !self.errors.is_empty() {
            self.close_dialog();
            let error = self.errors.join("\n\n");
            let title = self.settings.text(Text::Title);
            if !platform::message(&self.main.window, title, &error, true) {
                let _ = sdl3::messagebox::show_simple_message_box(
                    sdl3::messagebox::MessageBoxFlag::ERROR,
                    title,
                    &error,
                    &self.main.window,
                );
            }
        }
        self.remember_main_position();
        self.settings.save(&self.root).map_err(|e| e.to_string())
    }

    fn reveal(&mut self) -> bool {
        let mut revealed = false;
        if !self.main.shown {
            self.main.reveal_position = platform::stage_offscreen(&mut self.main.window);
            platform::show_main(&mut self.main.window);
            self.main.shown = true;
            self.main.dirty = true;
            revealed = true;
        }
        if let Some(counter) = self
            .counter
            .as_mut()
            .filter(|counter| !self.fullscreen && !counter.shown)
        {
            counter.reveal_position = platform::stage_offscreen(&mut counter.window);
            platform::show_without_activation(&mut counter.window);
            counter.shown = true;
            counter.dirty = true;
            revealed = true;
        }
        if let Some(Dialog { display, .. }) =
            self.dialog.as_mut().filter(|dialog| !dialog.display.shown)
        {
            display.reveal_position = platform::stage_offscreen(&mut display.window);
            platform::show_dialog(&mut display.window);
            display.shown = true;
            display.dirty = true;
            revealed = true;
        }
        revealed
    }

    fn restore_positions(&mut self) {
        if let Some(position) = self.main.reveal_position.take() {
            platform::restore_position(&mut self.main.window, position);
        }
        if let Some(counter) = &mut self.counter {
            if let Some(position) = counter.reveal_position.take() {
                platform::restore_position(&mut counter.window, position);
            }
        }
        if let Some(dialog) = &mut self.dialog {
            if let Some(position) = dialog.display.reveal_position.take() {
                platform::restore_position(&mut dialog.display.window, position);
            }
        }
    }

    fn uncloak(&self) {
        platform::uncloak(&self.main.window);
        if let Some(counter) = &self.counter {
            platform::uncloak(&counter.window);
        }
        if let Some(dialog) = &self.dialog {
            platform::uncloak(&dialog.display.window);
        }
    }
}

impl Drop for App {
    fn drop(&mut self) {
        self.release_cursor();
    }
}

fn ctrl(mods: Mod) -> bool {
    mods.intersects(Mod::LCTRLMOD | Mod::RCTRLMOD)
}

fn counter_capacity(window: &Window) -> (i32, i32) {
    window
        .get_display()
        .ok()
        .and_then(|display| display.get_usable_bounds().ok())
        .map_or((1920, 1080), |bounds| {
            (bounds.width() as i32, bounds.height() as i32)
        })
}

fn scaled_size((width, height): (u32, u32), scale: f64) -> (u32, u32) {
    (
        (width as f64 * scale).round() as u32,
        (height as f64 * scale).round() as u32,
    )
}

fn window_pixel_density(window: &Window) -> f64 {
    let density = f64::from(window.pixel_density());
    if density.is_finite() && density > 0.0 {
        density
    } else {
        1.0
    }
}

fn shortcut(key: Option<Keycode>, scancode: Option<Scancode>, mods: Mod) -> Option<Action> {
    let shift = Mod::LSHIFTMOD | Mod::RSHIFTMOD;
    if scancode == Some(Scancode::E)
        && ctrl(mods)
        && mods.intersects(shift)
        && !mods.intersects(Mod::LALTMOD | Mod::RALTMOD | Mod::LGUIMOD | Mod::RGUIMOD)
    {
        return Some(Action::ExportCsv);
    }
    if !platform::shortcut_allowed(mods) {
        return None;
    }
    let control = ctrl(mods);
    // Keycodes follow the active keyboard layout/IME, which can turn the
    // physical "/" key into "、" (outside the Keycode enum). Match the
    // physical scancode instead, like WinForms' Keys.OemQuestion.
    if !control && scancode == Some(Scancode::Slash) {
        return Some(Action::Counter);
    }
    match (key, control) {
        (Some(Keycode::S), true) => Some(Action::Save),
        (Some(Keycode::I), true) => Some(Action::Identity),
        (Some(Keycode::X), true) => Some(Action::Quit),
        (Some(Keycode::F4), false)
            if !mods.intersects(
                Mod::LSHIFTMOD
                    | Mod::RSHIFTMOD
                    | Mod::LALTMOD
                    | Mod::RALTMOD
                    | Mod::LGUIMOD
                    | Mod::RGUIMOD,
            ) =>
        {
            Some(Action::CursorLock)
        }
        (Some(Keycode::F11), false)
            if !mods.intersects(
                Mod::LSHIFTMOD
                    | Mod::RSHIFTMOD
                    | Mod::LALTMOD
                    | Mod::RALTMOD
                    | Mod::LGUIMOD
                    | Mod::RGUIMOD,
            ) =>
        {
            Some(Action::Fullscreen)
        }
        (Some(Keycode::F2 | Keycode::N), false) => Some(Action::Restart),
        (Some(Keycode::_1 | Keycode::B), false) => Some(Action::Level(0)),
        (Some(Keycode::_2 | Keycode::I), false) => Some(Action::Level(1)),
        (Some(Keycode::_3 | Keycode::E), false) => Some(Action::Level(2)),
        (Some(Keycode::S), false) => Some(Action::Settings),
        (Some(Keycode::W), false) => Some(Action::Open),
        (Some(Keycode::Z), false) => Some(Action::Shortcuts),
        (Some(Keycode::Slash), false) => Some(Action::Counter),
        _ => None,
    }
}

fn edit_text(
    value: &mut String,
    select: &mut bool,
    key: Keycode,
    control: bool,
    clipboard: Option<String>,
    max: usize,
) {
    match (key, control) {
        (Keycode::A, true) => *select = true,
        (Keycode::V, true) => {
            if let Some(text) = clipboard {
                append_text(value, select, &text, max);
            }
        }
        (Keycode::Backspace | Keycode::Delete, false) if *select => {
            value.clear();
            *select = false;
        }
        (Keycode::Backspace, false) => {
            value.pop();
        }
        (Keycode::Left | Keycode::Right, false) => *select = false,
        _ => {}
    }
}

fn append_text(value: &mut String, select: &mut bool, text: &str, max: usize) {
    if *select {
        value.clear();
        *select = false;
    }
    value.extend(
        text.chars()
            .filter(|ch| !ch.is_control())
            .take(max.saturating_sub(value.chars().count())),
    );
}

fn save_path(root: &Path, name: &str) -> PathBuf {
    let mut path = root.join("replay").join(name.trim());
    if !path
        .extension()
        .is_some_and(|ext| ext.eq_ignore_ascii_case("evf"))
    {
        path.as_mut_os_string().push(".evf");
    }
    path
}

fn open_directory(path: &Path) -> std::io::Result<()> {
    platform::open_directory(path)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn csv_export_is_only_bound_to_the_hidden_shortcut() {
        let modifiers = Mod::LCTRLMOD | Mod::LSHIFTMOD;
        assert_eq!(
            shortcut(Some(Keycode::E), Some(Scancode::E), modifiers),
            Some(Action::ExportCsv)
        );
        assert_ne!(
            shortcut(Some(Keycode::E), Some(Scancode::E), Mod::LCTRLMOD),
            Some(Action::ExportCsv)
        );
        assert_ne!(
            shortcut(
                Some(Keycode::E),
                Some(Scancode::E),
                modifiers | Mod::LALTMOD
            ),
            Some(Action::ExportCsv)
        );
        assert!(view::ENTRIES
            .iter()
            .flat_map(|entries| entries.iter())
            .all(|(action, _, _)| *action != Action::ExportCsv));
    }

    #[test]
    fn refresh_timer_posts_a_tick_with_fractional_millisecond_period() {
        let interval = refresh_interval(Some(360.0));
        assert_eq!(interval, Duration::from_nanos(2_777_778));
        assert_eq!(refresh_interval(Some(0.0)), refresh_interval(Some(60.0)));

        let sdl = sdl3::init().unwrap();
        let subsystem = sdl.event().unwrap();
        let event_type = unsafe { subsystem.register_event() }.unwrap();
        let mut events = sdl.event_pump().unwrap();
        let mut timer = RefreshTimer::default();
        timer.sync(event_type, Some(interval)).unwrap();
        assert!(matches!(events.wait_event_timeout_ms(1000),
            Some(Event::User { type_, code: REFRESH_TICK, .. }) if type_ == event_type));
        timer.sync(event_type, None).unwrap();
        assert!(timer.active.is_none());
    }

    #[test]
    fn slash_shortcut_uses_physical_key_when_ime_remaps_keycode() {
        assert_eq!(
            shortcut(None, Some(Scancode::Slash), Mod::NOMOD),
            Some(Action::Counter)
        );
        assert_eq!(
            shortcut(Some(Keycode::Slash), Some(Scancode::Slash), Mod::NOMOD),
            Some(Action::Counter)
        );
        assert_eq!(
            shortcut(Some(Keycode::Period), Some(Scancode::Slash), Mod::NOMOD),
            Some(Action::Counter)
        );
        assert_eq!(shortcut(None, Some(Scancode::Slash), Mod::LCTRLMOD), None);
        assert_eq!(shortcut(None, Some(Scancode::A), Mod::NOMOD), None);
    }
}

fn run() -> Result<(), String> {
    let root = platform::data_root()?;
    let settings = Settings::read(&root).map_err(|e| e.to_string())?;
    platform::prepare_root(&root, &settings)?;
    let directory = root.join("replay");
    let stats_path = std::env::var_os("MINI_STATS_PATH")
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| root.join("stats.dat"));
    let (jobs, queue) = mpsc::channel::<Job>();
    let (reply, replies) = mpsc::channel();
    let writer = thread::Builder::new()
        .name("Mini game writer".into())
        .spawn(move || {
            while let Ok(job) = queue.recv() {
                let text = job.error_text();
                let result = match job {
                    Job::Replay(replay, path) => {
                        replay.save(&directory, path.as_deref()).map(|_| None)
                    }
                    Job::Stats(record) => {
                        record.append(&stats_path).map(|_| None).map_err(|error| {
                            std::io::Error::new(
                                error.kind(),
                                format!("{}: {error}", stats_path.display()),
                            )
                        })
                    }
                    Job::ExportCsv { targets, overwrite } => {
                        csv_export::export(&stats_path, &targets, overwrite, |percent| {
                            let _ = reply.send(WriteReply::ExportProgress(percent));
                        })
                        .map(|()| Some(targets))
                    }
                };
                if let Err(error) = &result {
                    eprintln!("{error}");
                }
                let _ = reply.send(WriteReply::Finished(
                    result.map_err(|error| (text, error.to_string())),
                ));
            }
        })
        .map_err(|e| e.to_string())?;
    let result = App::new(root, settings, jobs, replies).and_then(App::run);
    let _ = writer.join();
    result
}

fn main() {
    platform::apply_process_hardening();
    if let Err(error) = run() {
        eprintln!("MetaSweeper-Mini: {error}");
        platform::fatal(&error);
        std::process::exit(1);
    }
}
