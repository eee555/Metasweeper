//! Every platform difference lives here. The rest of the crate calls these
//! functions through one API regardless of the target.

pub use imp::*;

pub fn wake_event(event_type: u32, code: i32) {
    use sdl3_sys::events::{SDL_Event, SDL_PushEvent};
    let mut event = SDL_Event::default();
    event.user.r#type = event_type;
    event.user.code = code;
    unsafe { SDL_PushEvent(&mut event); }
}

fn sdl_refresh_rate(window: &sdl3::video::Window) -> Option<f64> {
    use sdl3_sys::video::{SDL_GetCurrentDisplayMode, SDL_GetDisplayForWindow};
    let mode = unsafe { SDL_GetCurrentDisplayMode(SDL_GetDisplayForWindow(window.raw())).as_ref()? };
    Some(f64::from(mode.refresh_rate))
}

pub fn set_counter_hit_test(window: &mut sdl3::video::Window, close: bool) {
    use sdl3::video::HitTestResult::*;
    let raw = window.raw();
    let _ = window.set_hit_test(move |point| {
        let (mut width, mut height) = (0, 0);
        unsafe { sdl3_sys::video::SDL_GetWindowSizeInPixels(raw, &mut width, &mut height); }
        let (x, y) = (point.x, point.y);
        match (x < 6, x >= width - 6, y < 6, y >= height - 6) {
            (true, _, true, _) => ResizeTopLeft,
            (_, true, true, _) => ResizeTopRight,
            (true, _, _, true) => ResizeBottomLeft,
            (_, true, _, true) => ResizeBottomRight,
            (true, _, _, _) => ResizeLeft,
            (_, true, _, _) => ResizeRight,
            (_, _, true, _) => ResizeTop,
            (_, _, _, true) => ResizeBottom,
            _ if close && y < 37 && x >= width - 24 => Normal,
            _ => Draggable,
        }
    });
}

#[cfg(windows)]
mod imp {
    use crate::config::{Settings, Text};
    use crate::layout::{CounterLayout, Layout, PRESETS};
    use sdl3::keyboard::Mod;
    use sdl3::video::{Window, WindowBuilder, WindowPos};
    use std::{
        cell::Cell, ffi::OsString, io, mem::size_of,
        os::windows::ffi::OsStringExt, path::{Path, PathBuf}, process::Command,
        ptr::null_mut,
    };
    use windows_sys::Win32::{
        Foundation::{HWND, LPARAM, LRESULT, POINT, RECT, WPARAM},
        Graphics::Dwm::{DwmExtendFrameIntoClientArea, DwmSetWindowAttribute,
                        DWMWA_CLOAK, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND},
        Graphics::Gdi::{
            ClientToScreen, EnumDisplaySettingsW, GetMonitorInfoW, MonitorFromRect, MonitorFromWindow, DEVMODEW,
            ENUM_CURRENT_SETTINGS, MONITORINFO, MONITORINFOEXW, MONITOR_DEFAULTTONEAREST,
        },
        System::Threading::{
            GetCurrentProcess, GetPriorityClass, SetPriorityClass, HIGH_PRIORITY_CLASS, REALTIME_PRIORITY_CLASS,
        },
        UI::{
            Controls::{MARGINS, Dialogs::{CommDlgExtendedError, GetSaveFileNameW, OPENFILENAMEW,
                                OFN_EXPLORER, OFN_NOCHANGEDIR, OFN_OVERWRITEPROMPT, OFN_PATHMUSTEXIST}},
            HiDpi::GetDpiForWindow,
            Shell::{DefSubclassProc, IsUserAnAdmin, RemoveWindowSubclass, SetWindowSubclass},
            WindowsAndMessaging::*,
        },
    };

    pub fn font_paths() -> Vec<PathBuf> {
        const CANDIDATES: &[&str] = &[
            "C:\\Windows\\Fonts\\msyh.ttc",
            "C:\\Windows\\Fonts\\simhei.ttf",
            "C:\\Windows\\Fonts\\segoeui.ttf",
            "C:\\Windows\\Fonts\\simsun.ttc",
            "C:\\Windows\\Fonts\\arial.ttf",
        ];
        CANDIDATES.iter().map(PathBuf::from).filter(|path| path.exists()).take(3).collect()
    }

    pub fn counter_font_face(path: &Path) -> Option<u32> {
        path.file_name().is_some_and(|name| name == "msyh.ttc").then_some(1)
    }

    pub fn data_root() -> Result<PathBuf, String> {
        std::env::current_dir().map_err(|e| e.to_string())
    }

    pub fn prepare_root(root: &Path, settings: &Settings) -> Result<(), String> {
        if !root.join("gameSetting.ini").exists() { let _ = settings.save(root); }
        let _ = std::fs::create_dir_all(root.join("replay"));
        Ok(())
    }

    pub fn fatal(error: &str) {
        let _ = sdl3::messagebox::show_simple_message_box(
            sdl3::messagebox::MessageBoxFlag::ERROR,
            "MetaSweeper-Mini",
            error,
            None::<&Window>,
        );
    }

    pub fn open_directory(path: &Path) -> io::Result<()> {
        Command::new("explorer").arg(path).spawn().map(|_| ())
    }

    pub fn place_main_window(builder: &mut WindowBuilder, _position: Option<(i32, i32)>, _wayland: bool) {
        builder.hidden().position_centered();
    }

    pub fn show_main(window: &mut Window) { show_cloaked(window); }

    pub fn show_dialog(window: &mut Window) {
        show_cloaked(window);
        window.raise();
    }

    pub fn uncloak(window: &Window) {
        let Some(hwnd) = hwnd(window) else { return };
        let off: i32 = 0;
        unsafe {
            DwmSetWindowAttribute(hwnd, DWMWA_CLOAK as u32,
                (&off as *const i32).cast(), size_of::<i32>() as u32);
        }
    }

    pub fn stage_offscreen(window: &mut Window) -> Option<(i32, i32)> {
        let position = window.position();
        window.set_position(WindowPos::Positioned(-32000), WindowPos::Positioned(-32000));
        Some(position)
    }

    pub fn restore_position(window: &mut Window, position: (i32, i32)) {
        window.set_position(WindowPos::Positioned(position.0), WindowPos::Positioned(position.1));
    }

    fn show_cloaked(window: &mut Window) {
        if let Some(hwnd) = hwnd(window) {
            let on: i32 = 1;
            unsafe {
                DwmSetWindowAttribute(hwnd, DWMWA_CLOAK as u32,
                    (&on as *const i32).cast(), size_of::<i32>() as u32);
            }
        }
        window.show();
    }

    pub fn set_capture_guard(window: &Window, enabled: bool) {
        if let Some(handle) = hwnd(window) {
            let affinity = if enabled { WDA_EXCLUDEFROMCAPTURE } else { WDA_NONE };
            if unsafe { SetWindowDisplayAffinity(handle, affinity) } == 0 {
                sdl3::log::log(&format!("SetWindowDisplayAffinity failed: {}", io::Error::last_os_error()));
            }
        }
    }

    pub fn fit_to_screen(window: &Window, (x, y): (i32, i32)) {
        let Some(hwnd) = hwnd(window) else { return };
        let Some(size) = bounds(hwnd) else { return };
        let desired = RECT { left: x, top: y, right: x.saturating_add(width(size)),
            bottom: y.saturating_add(height(size)) };
        let Some(work) = work_area(desired) else { return };
        move_window(hwnd, x.min(work.right - width(size)).max(work.left),
            y.min(work.bottom - height(size)).max(work.top));
    }

    pub fn recover_window(_window: &Window) {}

    pub fn normal(window: &Window) -> bool {
        hwnd(window).map_or(true, |hwnd| unsafe { IsIconic(hwnd) == 0 && IsZoomed(hwnd) == 0 })
    }

    pub fn window_position(window: &Window) -> Option<(i32, i32)> {
        let hwnd = hwnd(window).filter(|hwnd| normal_hwnd(*hwnd))?;
        bounds(hwnd).map(|rect| (rect.left, rect.top))
    }

    pub fn client_capacity(window: &Window) -> Option<(i32, i32)> {
        client_capacity_hwnd(hwnd(window)?)
    }

    pub fn dpi_scale(window: &Window) -> f64 {
        hwnd(window).map_or(1.0, |hwnd| unsafe { GetDpiForWindow(hwnd).max(96) as f64 / 96.0 })
    }

    pub fn configure_dpi() {
        sdl3::hint::set("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2");
    }

    pub fn configure_window_hints() {
        sdl3::hint::set("SDL_WINDOWS_ERASE_BACKGROUND_MODE", "never");
    }

    pub fn configure_process_priority() {
        unsafe {
            let process = GetCurrentProcess();
            let realtime = IsUserAnAdmin() != 0
                && SetPriorityClass(process, REALTIME_PRIORITY_CLASS) != 0
                && GetPriorityClass(process) == REALTIME_PRIORITY_CLASS;
            if !realtime {
                SetPriorityClass(process, HIGH_PRIORITY_CLASS);
            }
        }
    }

    pub fn center_settings(window: &Window, owner: &Window) {
        let Some(window) = hwnd(window) else { return };
        let (Some(dialog), Some(parent)) = (bounds(window), hwnd(owner).and_then(bounds)) else { return };
        let Some(work) = work_area(parent) else { return };
        let x = parent.left + (width(parent) - width(dialog)) / 2;
        let y = parent.top + (height(parent) - height(dialog)) / 2;
        move_window(window, x.min(work.right - width(dialog)).max(work.left),
            y.min(work.bottom - height(dialog)).max(work.top));
    }

    pub fn show_without_activation(window: &mut Window) {
        let name = "SDL_WINDOW_ACTIVATE_WHEN_SHOWN";
        let previous = sdl3::hint::get(name);
        sdl3::hint::set(name, "0");
        show_cloaked(window);
        if let Some(previous) = previous {
            sdl3::hint::set(name, &previous);
        } else {
            unsafe { sdl3_sys::hints::SDL_ResetHint(c"SDL_WINDOW_ACTIVATE_WHEN_SHOWN".as_ptr()); }
        }
    }

    pub fn position_counter(main: &Window, counter: &Window, saved: Option<(i32, i32)>) {
        let (Some(main), Some(counter)) = (hwnd(main), hwnd(counter)) else { return };
        if !normal_hwnd(main) { return; }
        if let Some(position) = saved {
            let Some(size) = bounds(counter) else { return };
            let desired = RECT { left: position.0, top: position.1,
                right: position.0.saturating_add(width(size)),
                bottom: position.1.saturating_add(height(size)) };
            let Some(work) = work_area(desired) else { return };
            move_window(counter,
                position.0.min(work.right - width(size)).max(work.left),
                position.1.min(work.bottom - height(size)).max(work.top));
            return;
        }
        let (Some(main_bounds), Some(counter_bounds)) = (bounds(main), bounds(counter)) else { return };
        let Some(work) = work_area(main_bounds) else { return };
        let counter_width = width(counter_bounds);
        let mut left = main_bounds.left - counter_width - 9;
        if left < work.left && main_bounds.right + 9 + counter_width <= work.right {
            left = main_bounds.right + 9;
        }
        let top = (main_bounds.top + 10).min(work.bottom - height(counter_bounds)).max(work.top);
        move_window(counter, left.max(work.left), top);
    }

    pub fn message(window: &Window, title: &str, text: &str, warning: bool) -> bool {
        let Some(owner) = hwnd(window) else { return false };
        let flags = if warning { MB_ICONWARNING } else { MB_OK };
        unsafe { MessageBoxW(owner, wide(text).as_ptr(), wide(title).as_ptr(), flags); }
        true
    }

    pub fn save_dialog(
        window: &Window, settings: &Settings, name: &str,
    ) -> Option<Result<Option<PathBuf>, String>> {
        hwnd(window).map(|owner| save_dialog_native(owner, settings, name))
    }

    fn save_dialog_native(owner: HWND, settings: &Settings, name: &str) -> Result<Option<PathBuf>, String> {
        let title = wide(settings.text(Text::SaveReplayTitle));
        let filter = wide(&format!("{} (*.evf)\0*.evf\0", settings.text(Text::ReplayFiles)));
        let mut filename = wide(&format!("{name}.evf"));
        filename.resize(32768, 0);
        let mut dialog = OPENFILENAMEW {
            lStructSize: size_of::<OPENFILENAMEW>() as u32,
            hwndOwner: owner,
            lpstrFilter: filter.as_ptr(),
            nFilterIndex: 1,
            lpstrFile: filename.as_mut_ptr(),
            nMaxFile: filename.len() as u32,
            lpstrTitle: title.as_ptr(),
            lpstrDefExt: windows_sys::w!("evf"),
            Flags: OFN_EXPLORER | OFN_NOCHANGEDIR | OFN_OVERWRITEPROMPT | OFN_PATHMUSTEXIST,
            ..Default::default()
        };
        if unsafe { GetSaveFileNameW(&mut dialog) } != 0 {
            let end = filename.iter().position(|&unit| unit == 0).unwrap_or(filename.len());
            return Ok(Some(OsString::from_wide(&filename[..end]).into()));
        }
        let code = unsafe { CommDlgExtendedError() };
        if code == 0 { Ok(None) } else { Err(format!("GetSaveFileNameW: 0x{code:04X}")) }
    }

    pub fn shortcut_allowed(mods: Mod) -> bool {
        !mods.intersects(Mod::LSHIFTMOD | Mod::RSHIFTMOD | Mod::LALTMOD | Mod::RALTMOD
            | Mod::LGUIMOD | Mod::RGUIMOD)
    }

    pub fn confine_cursor(window: &mut Window, region: sdl3::rect::Rect) -> bool {
        let Some(handle) = hwnd(window) else { return false };
        let mut origin = POINT { x: 0, y: 0 };
        unsafe {
            if GetForegroundWindow() != handle || IsIconic(handle) != 0 || IsWindowVisible(handle) == 0
                || ClientToScreen(handle, &mut origin) == 0 {
                return false;
            }
            let clip = RECT {
                left: origin.x + region.left(), top: origin.y + region.top(),
                right: origin.x + region.right(), bottom: origin.y + region.bottom(),
            };
            if ClipCursor(&clip) == 0 { return false; }
            SetWindowPos(handle, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
        }
        true
    }

    pub fn release_cursor(window: &mut Window) {
        unsafe {
            ClipCursor(std::ptr::null());
            if let Some(handle) = hwnd(window) {
                SetWindowPos(handle, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
            }
        }
    }

    pub fn clock_ms() -> Option<u64> {
        Some(unsafe { windows_sys::Win32::System::SystemInformation::GetTickCount64() })
    }

    pub fn limit_identifier(value: &str) -> String {
        let mut units = 0;
        value.trim().chars().take_while(|ch| {
            units += ch.len_utf16();
            units <= 128
        }).collect()
    }

    pub fn text_units(value: &str) -> usize {
        value.encode_utf16().count()
    }

    pub fn filename_stem(name: &str) -> String {
        name.chars().map(sanitize_char).collect::<String>().trim().trim_end_matches('.').into()
    }

    pub fn board_hook(
        window: &Window, reference: i32, settings: &Settings,
    ) -> Result<Option<WindowHook>, String> {
        match hwnd(window) {
            Some(hwnd) => WindowHook::board(hwnd, reference, settings).map(Some),
            None => Ok(None),
        }
    }

    pub fn refresh_rate(window: &Window) -> Option<f64> {
        let read_current_mode = || {
            let monitor = unsafe { MonitorFromWindow(hwnd(window)?, MONITOR_DEFAULTTONEAREST) };
            let mut info = MONITORINFOEXW::default();
            info.monitorInfo.cbSize = size_of::<MONITORINFOEXW>() as u32;
            if unsafe { GetMonitorInfoW(monitor, (&raw mut info).cast()) } == 0 { return None; }
            let mut mode = DEVMODEW::default();
            mode.dmSize = size_of::<DEVMODEW>() as u16;
            if unsafe { EnumDisplaySettingsW(info.szDevice.as_ptr(), ENUM_CURRENT_SETTINGS, &mut mode) } == 0
                || mode.dmDisplayFrequency <= 1 {
                return None;
            }
            Some(f64::from(mode.dmDisplayFrequency))
        };
        read_current_mode().or_else(|| super::sdl_refresh_rate(window))
    }

    pub fn counter_hook(window: &Window, wake_type: u32, pixels: i32) -> Result<Option<WindowHook>, String> {
        match hwnd(window) {
            Some(hwnd) => WindowHook::counter(hwnd, wake_type, pixels).map(Some),
            None => Ok(None),
        }
    }

    fn sanitize_char(c: char) -> char {
        if c.is_control() || "<>:\"/\\|?*".contains(c) { '_' } else { c }
    }

    fn hwnd(window: &Window) -> Option<HWND> {
        use sdl3_sys::{
            properties::SDL_GetPointerProperty,
            video::{SDL_GetWindowProperties, SDL_PROP_WINDOW_WIN32_HWND_POINTER},
        };
        let handle = unsafe {
            SDL_GetPointerProperty(SDL_GetWindowProperties(window.raw()),
                SDL_PROP_WINDOW_WIN32_HWND_POINTER, null_mut())
        };
        (!handle.is_null()).then_some(handle)
    }

    fn wide(text: &str) -> Vec<u16> {
        text.encode_utf16().chain([0]).collect()
    }

    fn bounds(hwnd: HWND) -> Option<RECT> {
        let mut rect = RECT::default();
        (unsafe { GetWindowRect(hwnd, &mut rect) } != 0).then_some(rect)
    }

    fn work_area(rect: RECT) -> Option<RECT> {
        let mut info = MONITORINFO { cbSize: size_of::<MONITORINFO>() as u32, ..Default::default() };
        let monitor = unsafe { MonitorFromRect(&rect, MONITOR_DEFAULTTONEAREST) };
        (unsafe { GetMonitorInfoW(monitor, &mut info) } != 0).then_some(info.rcWork)
    }

    fn width(rect: RECT) -> i32 { rect.right - rect.left }
    fn height(rect: RECT) -> i32 { rect.bottom - rect.top }

    fn normal_hwnd(hwnd: HWND) -> bool {
        unsafe { IsIconic(hwnd) == 0 && IsZoomed(hwnd) == 0 }
    }

    fn move_window(hwnd: HWND, x: i32, y: i32) {
        unsafe { SetWindowPos(hwnd, null_mut(), x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE); }
    }

    fn chrome_size(hwnd: HWND, outer: RECT) -> Option<(i32, i32)> {
        let mut client = RECT::default();
        (unsafe { GetClientRect(hwnd, &mut client) } != 0)
            .then_some((width(outer) - width(client), height(outer) - height(client)))
    }

    fn client_capacity_hwnd(hwnd: HWND) -> Option<(i32, i32)> {
        let outer = bounds(hwnd)?;
        let work = work_area(outer)?;
        let (extra_width, extra_height) = chrome_size(hwnd, outer)?;
        Some((width(work) - extra_width, height(work) - extra_height))
    }

    #[derive(Clone, Copy)]
    struct BoardSizing {
        reference: i32,
        level: usize,
        footer: bool,
    }

    enum HookState {
        Board(Cell<BoardSizing>),
        Counter(Cell<CounterSizing>, u32),
    }

    #[derive(Clone, Copy)]
    struct CounterSizing {
        moved: bool,
        pixels: i32,
    }

    pub struct WindowHook {
        window: HWND,
        state: Box<HookState>,
    }

    impl WindowHook {
        fn board(window: HWND, reference: i32, settings: &Settings) -> Result<Self, String> {
            Self::attach(window, HookState::Board(Cell::new(BoardSizing {
                reference, level: settings.level, footer: settings.identity,
            })))
        }

        fn counter(window: HWND, wake_type: u32, pixels: i32) -> Result<Self, String> {
            let hook = Self::attach(window, HookState::Counter(
                Cell::new(CounterSizing { moved: false, pixels }), wake_type))?;
            unsafe {
                let style = GetWindowLongPtrW(window, GWL_STYLE);
                SetWindowLongPtrW(window, GWL_STYLE, style | WS_THICKFRAME as isize);
                SetWindowPos(window, null_mut(), 0, 0, 0, 0,
                    SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE);
                extend_counter_frame(window);
                DwmSetWindowAttribute(window, DWMWA_WINDOW_CORNER_PREFERENCE as u32,
                    (&DWMWCP_ROUND as *const i32).cast(), size_of::<i32>() as u32);
            }
            Ok(hook)
        }

        fn attach(window: HWND, state: HookState) -> Result<Self, String> {
            let state = Box::new(state);
            if unsafe { SetWindowSubclass(window, Some(window_proc), 1, (&*state as *const HookState) as usize) } == 0 {
                return Err(io::Error::last_os_error().to_string());
            }
            Ok(Self { window, state })
        }

        pub fn update_board(&self, settings: &Settings) {
            if let HookState::Board(state) = &*self.state {
                state.set(BoardSizing { level: settings.level, footer: settings.identity, ..state.get() });
            }
        }

        pub fn update_counter(&self, pixels: i32) {
            if let HookState::Counter(state, _) = &*self.state {
                state.set(CounterSizing { pixels, ..state.get() });
            }
        }

        pub fn moved_position(&self) -> Option<(i32, i32)> {
            let moved = matches!(&*self.state, HookState::Counter(state, _) if state.get().moved);
            if let HookState::Counter(state, _) = &*self.state {
                if moved { state.set(CounterSizing { moved: false, ..state.get() }); }
            }
            if !moved { return None; }
            bounds(self.window).map(|rect| (rect.left, rect.top))
        }
    }

    impl Drop for WindowHook {
        fn drop(&mut self) {
            unsafe { RemoveWindowSubclass(self.window, Some(window_proc), 1); }
        }
    }

    unsafe fn extend_counter_frame(window: HWND) {
        let margins = MARGINS { cxLeftWidth: 1, cxRightWidth: 1, cyTopHeight: 1, cyBottomHeight: 1 };
        DwmExtendFrameIntoClientArea(window, &margins);
    }

    unsafe extern "system" fn window_proc(
        hwnd: HWND, msg: u32, wparam: WPARAM, lparam: LPARAM, _: usize, data: usize,
    ) -> LRESULT {
        match (&*(data as *const HookState), msg) {
            (HookState::Board(_) | HookState::Counter(..), WM_ERASEBKGND) => return 1,
            (HookState::Board(sizing), WM_SIZING) if lparam != 0 => {
                if constrain_drag(hwnd, &mut *(lparam as *mut RECT), wparam as u32, sizing.get()) {
                    return 1;
                }
            }
            (HookState::Counter(..), WM_NCCALCSIZE) => return 0,
            (HookState::Counter(..), WM_DWMCOMPOSITIONCHANGED) => extend_counter_frame(hwnd),
            (HookState::Counter(..), WM_SIZING) if lparam != 0 => {
                let rect = &mut *(lparam as *mut RECT);
                if let Some(work) = work_area(*rect) {
                    let edge = wparam as u32;
                    let HookState::Counter(state, _) = &*(data as *const HookState) else { return 0 };
                    let axes = (!matches!(edge, WMSZ_TOP | WMSZ_BOTTOM),
                        !matches!(edge, WMSZ_LEFT | WMSZ_RIGHT));
                    let scale = CounterLayout::nearest(state.get().pixels, (width(*rect), height(*rect)),
                        (width(work), height(work)), axes);
                    resize_rect(rect, edge, CounterLayout::new(scale).size());
                    state.set(CounterSizing { pixels: scale, ..state.get() });
                    return 1;
                }
            }
            (HookState::Counter(state, wake_type), WM_EXITSIZEMOVE) => {
                state.set(CounterSizing { moved: true, ..state.get() });
                super::wake_event(*wake_type, 0);
            }
            _ => {}
        }
        DefSubclassProc(hwnd, msg, wparam, lparam)
    }

    unsafe fn constrain_drag(hwnd: HWND, rect: &mut RECT, edge: u32, sizing: BoardSizing) -> bool {
        let (Some(chrome), Some(work)) = (bounds(hwnd).and_then(|outer| chrome_size(hwnd, outer)),
            work_area(*rect)) else { return false };
        let BoardSizing { reference, level, footer } = sizing;
        let (rows, cols, _) = PRESETS[level];
        let weights = (if matches!(edge, WMSZ_TOP | WMSZ_BOTTOM) { 0 } else { cols },
            if matches!(edge, WMSZ_LEFT | WMSZ_RIGHT) { 0 } else { rows + 2 });
        let available = (width(work) - chrome.0, height(work) - chrome.1);
        let client = fit_drag(reference, level, footer,
            (width(*rect) - chrome.0, height(*rect) - chrome.1), available, weights);
        resize_rect(rect, edge, (client.0 + chrome.0, client.1 + chrome.1));
        true
    }

    fn resize_rect(rect: &mut RECT, edge: u32, (width, height): (i32, i32)) {
        if matches!(edge, WMSZ_LEFT | WMSZ_TOPLEFT | WMSZ_BOTTOMLEFT) { rect.left = rect.right - width; }
        else { rect.right = rect.left + width; }
        if matches!(edge, WMSZ_TOP | WMSZ_TOPLEFT | WMSZ_TOPRIGHT) { rect.top = rect.bottom - height; }
        else { rect.bottom = rect.top + height; }
    }

    fn fit_drag(reference: i32, level: usize, footer: bool, proposed: (i32, i32),
                available: (i32, i32), weights: (i32, i32)) -> (i32, i32) {
        let projection = |(width, height)| i64::from(width) * i64::from(weights.0)
            + i64::from(height) * i64::from(weights.1);
        let size = |tile| Layout::new(tile, reference).size(level, footer);
        let wanted = projection(proposed);
        let mut low = 5;
        let mut high = Layout::fit(reference, level, footer, available).tile;
        while low < high {
            let mid = (low + high) / 2;
            if 2 * wanted >= projection(size(mid)) + projection(size(mid + 1)) { low = mid + 1; }
            else { high = mid; }
        }
        size(low)
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        #[test]
        fn filenames_keep_unicode_identifiers_on_windows() {
            assert_eq!(filename_stem(" A:*? /B. "), "A___ _B");
            let player = "扫".repeat(128);
            assert_eq!(filename_stem(&player), player);
        }

        #[test]
        fn windows_side_drags_resize_both_dimensions() {
            let size = Layout::new(31, 20).size(0, true);
            let available = Layout::new(50, 20).size(0, true);
            assert_eq!(fit_drag(20, 0, true, (size.0, 100), available, (8, 0)), size);
            assert_eq!(fit_drag(20, 0, true, (100, size.1), available, (0, 10)), size);
            assert_eq!(fit_drag(20, 0, true, (4000, 4000), available, (8, 10)), available);
        }
    }
}

#[cfg(not(windows))]
mod imp {
    use crate::config::Settings;
    use sdl3::keyboard::Mod;
    use sdl3::rect::Rect;
    use sdl3::video::{Window, WindowBuilder};
    use sdl3_sys::video::{SDL_GetWindowPosition, SDL_SetWindowPosition};
    use std::{
        io,
        path::{Path, PathBuf},
        process::Command,
    };

    pub fn font_paths() -> Vec<PathBuf> {
        const CANDIDATES: &[&str] = &[
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ];
        CANDIDATES.iter().map(PathBuf::from).filter(|path| path.exists()).take(3).collect()
    }

    pub fn counter_font_face(_path: &Path) -> Option<u32> { None }

    pub fn data_root() -> Result<PathBuf, String> {
        std::env::current_exe().map_err(|e| e.to_string())?
            .parent().ok_or_else(|| "Cannot locate the program directory".to_string())
            .map(Path::to_path_buf)
    }

    pub fn prepare_root(root: &Path, settings: &Settings) -> Result<(), String> {
        if !root.join("gameSetting.ini").exists() {
            settings.save(root).map_err(|e| e.to_string())?;
        }
        std::fs::create_dir_all(root.join("replay")).map_err(|e| e.to_string())
    }

    pub fn fatal(_error: &str) {}

    pub fn open_directory(path: &Path) -> io::Result<()> {
        Command::new("xdg-open").arg(path).spawn().map(|_| ())
    }

    pub fn place_main_window(builder: &mut WindowBuilder, position: Option<(i32, i32)>, wayland: bool) {
        if let Some((x, y)) = position.filter(|_| !wayland) { builder.position(x, y); }
        else { builder.position_centered(); }
    }

    pub fn show_main(window: &mut Window) { window.show(); }

    pub fn show_dialog(window: &mut Window) {
        window.show();
        window.raise();
    }

    pub fn uncloak(_window: &Window) {}

    pub fn stage_offscreen(_window: &mut Window) -> Option<(i32, i32)> { None }

    pub fn restore_position(_window: &mut Window, _position: (i32, i32)) {}

    pub fn set_capture_guard(_window: &Window, _enabled: bool) {}

    pub fn fit_to_screen(window: &Window, position: (i32, i32)) {
        if window.subsystem().current_video_driver() != "x11" || !normal(window) { return; }
        let Ok(displays) = window.subsystem().displays() else { return };
        let areas = displays.iter().filter_map(|display| {
            display.get_usable_bounds().or_else(|_| display.get_bounds()).ok()
        });
        let borders = window.border_size().unwrap_or_default();
        if let Some((x, y)) = fit_position(position, window.size(), borders, areas) {
            if window_position(window) != Some((x, y)) {
                unsafe { SDL_SetWindowPosition(window.raw(), x, y); }
            }
        }
    }

    fn fit_position(
        (x, y): (i32, i32), (width, height): (u32, u32),
        (top, left, bottom, right): (u16, u16, u16, u16), areas: impl IntoIterator<Item = Rect>,
    ) -> Option<(i32, i32)> {
        areas.into_iter().map(|area| {
            let min_x = area.left() + i32::from(left);
            let min_y = area.top() + i32::from(top);
            let max_x = area.right() - width as i32 - i32::from(right);
            let max_y = area.bottom() - height as i32 - i32::from(bottom);
            (x.clamp(min_x, max_x.max(min_x)), y.clamp(min_y, max_y.max(min_y)))
        }).min_by_key(|&(fitted_x, fitted_y)| u64::from(x.abs_diff(fitted_x)) + u64::from(y.abs_diff(fitted_y)))
    }

    pub fn recover_window(window: &Window) {
        if let Some(position) = window_position(window) { fit_to_screen(window, position); }
    }

    pub fn normal(window: &Window) -> bool { !window.is_minimized() && !window.is_maximized() }

    pub fn window_position(window: &Window) -> Option<(i32, i32)> {
        if window.subsystem().current_video_driver() != "x11" || !normal(window) { return None; }
        let (mut x, mut y) = (0, 0);
        unsafe { SDL_GetWindowPosition(window.raw(), &mut x, &mut y) }.then_some((x, y))
    }

    pub fn client_capacity(_window: &Window) -> Option<(i32, i32)> { None }

    pub fn dpi_scale(window: &Window) -> f64 {
        let scale = f64::from(window.display_scale());
        if scale.is_finite() && scale > 0.0 { scale } else { 1.0 }
    }

    pub fn configure_dpi() {}

    pub fn configure_window_hints() {}

    pub fn configure_process_priority() {}

    pub fn center_settings(window: &Window, owner: &Window) {
        if window.subsystem().current_video_driver() != "x11" { return; }
        let (x, y) = owner.position();
        let (owner_width, owner_height) = owner.size();
        let (width, height) = window.size();
        fit_to_screen(window, (x + (owner_width as i32 - width as i32) / 2,
            y + (owner_height as i32 - height as i32) / 2));
    }

    pub fn show_without_activation(window: &mut Window) { window.show(); }

    pub fn position_counter(main: &Window, counter: &Window, saved: Option<(i32, i32)>) {
        let Some((x, y)) = window_position(main) else { return };
        let position = saved.unwrap_or_else(|| {
            let counter_width = counter.size().0 as i32;
            let left = x - counter_width - 9;
            let right = x + main.size().0 as i32 + 9;
            let area = main.get_display().ok().and_then(|display| display.get_usable_bounds().ok());
            let x = if area.is_some_and(|area| left < area.left() && right + counter_width <= area.right()) {
                right
            } else {
                left
            };
            (x, y + 10)
        });
        fit_to_screen(counter, position);
    }

    pub fn message(_window: &Window, _title: &str, _text: &str, _warning: bool) -> bool { false }

    pub fn save_dialog(
        _window: &Window, _settings: &Settings, _name: &str,
    ) -> Option<Result<Option<PathBuf>, String>> {
        None
    }

    pub fn shortcut_allowed(_mods: Mod) -> bool { true }

    pub fn confine_cursor(window: &mut Window, region: sdl3::rect::Rect) -> bool {
        if window.set_mouse_rect(Some(region)).is_ok() && window.set_mouse_grab(true) { return true; }
        let _ = window.set_mouse_rect(None);
        false
    }

    pub fn release_cursor(window: &mut Window) {
        let _ = window.set_mouse_rect(None);
        window.set_mouse_grab(false);
    }

    pub fn clock_ms() -> Option<u64> {
        Some(unsafe { sdl3_sys::timer::SDL_GetTicks() })
    }

    pub fn limit_identifier(value: &str) -> String {
        value.trim().chars().take(128).collect()
    }

    pub fn text_units(value: &str) -> usize {
        value.chars().count()
    }

    pub fn filename_stem(name: &str) -> String {
        let mut bytes = 0;
        let clipped: String = name.chars().map(sanitize_char).take_while(|ch| {
            bytes += ch.len_utf8();
            bytes <= 170
        }).collect();
        clipped.trim().trim_end_matches('.').into()
    }

    pub fn board_hook(
        _window: &Window, _reference: i32, _settings: &Settings,
    ) -> Result<Option<WindowHook>, String> {
        Ok(None)
    }

    pub fn refresh_rate(window: &Window) -> Option<f64> { super::sdl_refresh_rate(window) }

    pub fn counter_hook(_window: &Window, _wake_type: u32, _pixels: i32) -> Result<Option<WindowHook>, String> {
        Ok(None)
    }

    fn sanitize_char(c: char) -> char {
        if c.is_control() || "<>:\"/\\|?*".contains(c) { '_' } else { c }
    }

    #[allow(dead_code)]
    pub struct WindowHook;

    #[allow(dead_code)]
    impl WindowHook {
        pub fn update_board(&self, _settings: &Settings) {}
        pub fn update_counter(&self, _pixels: i32) {}
        pub fn moved_position(&self) -> Option<(i32, i32)> { None }
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        #[test]
        fn filenames_keep_room_for_suffixes_on_linux() {
            assert_eq!(filename_stem(" A:*? /B. "), "A___ _B");
            let long = filename_stem(&"扫".repeat(128));
            assert_eq!(long.len(), 168);
        }

        #[test]
        fn x11_position_uses_remaining_work_area_after_display_removal() {
            let primary = Rect::new(0, 30, 1920, 1050);
            let secondary = Rect::new(-1920, 0, 1920, 1080);
            let size = (704, 922);
            let borders = (30, 5, 5, 5);

            assert_eq!(fit_position((-1600, 60), size, borders, [primary, secondary]), Some((-1600, 60)));
            assert_eq!(fit_position((-1600, 60), size, borders, [primary]), Some((5, 60)));
            assert_eq!(fit_position((2100, 500), size, borders, [primary]), Some((1211, 153)));
            assert_eq!(fit_position((900, 500), (2000, 1200), borders, [primary]), Some((5, 60)));
        }
    }
}
