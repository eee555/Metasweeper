use crate::{
    ctrl,
    layout::Box2,
    paint::{Align, Painter, INK, WHITE},
    settings_ui::{draw_edit, Edit},
    text::Text,
    view, Settings,
};
use sdl3::{
    keyboard::{Keycode, Mod},
    VideoSubsystem,
};
use std::{
    ffi::OsString,
    fs, io,
    path::{Path, PathBuf},
};

#[cfg(windows)]
const LIST_TOP: i32 = 88;
#[cfg(not(windows))]
const LIST_TOP: i32 = 52;
pub(crate) const SIZE: (u32, u32) = (640, LIST_TOP as u32 + 352);
const ROW_HEIGHT: i32 = 26;
const PATH_LIMIT: usize = 32767;

pub(crate) enum Outcome {
    Stay,
    Choose,
    Cancel,
}

pub(crate) struct Picker {
    current: PathBuf,
    #[cfg(windows)]
    drives: Vec<PathBuf>,
    folders: Vec<OsString>,
    offset: usize,
    selected: Option<usize>,
    draft: Edit,
    editing: bool,
    pub(crate) dragging: bool,
    overwrite: bool,
    error: Option<io::Error>,
}

impl Picker {
    pub(crate) fn new(directory: &Path) -> Self {
        let mut picker = Self {
            current: directory.to_path_buf(),
            #[cfg(windows)]
            drives: logical_drives(),
            folders: Vec::new(),
            offset: 0,
            selected: None,
            draft: Edit::with_limit(directory.to_string_lossy().into_owned(), PATH_LIMIT),
            editing: false,
            dragging: false,
            overwrite: false,
            error: None,
        };
        picker.open(directory.to_path_buf());
        picker.focus_path();
        picker
    }

    fn open(&mut self, directory: PathBuf) -> bool {
        self.overwrite = false;
        match read_folders(&directory) {
            Ok(folders) => {
                self.draft = Edit::with_limit(directory.to_string_lossy().into_owned(), PATH_LIMIT);
                self.current = directory;
                self.folders = folders;
                self.offset = 0;
                self.selected = None;
                self.editing = false;
                self.dragging = false;
                self.error = None;
                true
            }
            Err(error) => {
                self.error = Some(error);
                false
            }
        }
    }

    fn open_draft(&mut self) -> bool {
        if self.draft.value.is_empty() {
            self.error = Some(io::ErrorKind::NotFound.into());
            return false;
        }
        if self.draft.value == self.current.to_string_lossy() {
            return self.open(self.current.clone());
        }
        let path = self.current.join(&self.draft.value);
        match resolve_path(&path) {
            Ok(directory) => self.open(directory),
            Err(error) => {
                self.error = Some(error);
                false
            }
        }
    }

    fn open_parent(&mut self) {
        if let Some(parent) = self.current.parent() {
            self.open(parent.to_path_buf());
        }
    }

    fn open_selected(&mut self) {
        if let Some(folder) = self.selected.and_then(|index| self.folders.get(index)) {
            self.open(self.current.join(folder));
        }
    }

    pub(crate) fn destination(&mut self) -> Option<&Path> {
        if self.draft.value != self.current.to_string_lossy() && !self.open_draft() {
            return None;
        }
        if let Err(error) = fs::read_dir(&self.current) {
            self.error = Some(error);
            self.overwrite = false;
            return None;
        }
        self.error = None;
        Some(&self.current)
    }

    pub(crate) fn confirm_overwrite(&mut self, exists: bool) -> Option<bool> {
        if exists && !self.overwrite {
            self.overwrite = true;
            None
        } else {
            Some(self.overwrite)
        }
    }

    pub(crate) fn text(&mut self, text: &str) {
        if self.editing {
            self.draft.insert(text, false);
            self.error = None;
            self.overwrite = false;
        }
    }

    pub(crate) fn composition(&mut self, text: String, start: i32, length: i32) {
        if self.editing {
            self.draft.set_composition(text, start, length);
        }
    }

    pub(crate) fn composing(&self) -> bool {
        self.draft.composing()
    }

    fn enter(&mut self) -> Outcome {
        if self.editing {
            if !self.composing() {
                self.open_draft();
            }
        } else if self.selected.is_none() || self.overwrite {
            return Outcome::Choose;
        } else {
            self.open_selected();
        }
        Outcome::Stay
    }

    pub(crate) fn key(
        &mut self,
        key: Keycode,
        mods: Mod,
        video: &VideoSubsystem,
        size: (i32, i32),
    ) -> Outcome {
        let control = ctrl(mods);
        let alt = mods.intersects(Mod::LALTMOD | Mod::RALTMOD);
        match key {
            Keycode::Escape => return Outcome::Cancel,
            Keycode::L if control => self.focus_path(),
            Keycode::Up if alt => self.open_parent(),
            Keycode::Return | Keycode::KpEnter => return self.enter(),
            Keycode::Right if !self.editing => self.open_selected(),
            Keycode::Left | Keycode::Backspace if !self.editing => self.open_parent(),
            Keycode::Tab => {
                if self.editing {
                    self.leave_path();
                } else {
                    self.focus_path();
                }
            }
            Keycode::Up
            | Keycode::Down
            | Keycode::PageUp
            | Keycode::PageDown
            | Keycode::Home
            | Keycode::End
                if !self.editing =>
            {
                let rows = visible_rows(size.1);
                let last = self.folders.len().saturating_sub(1);
                let selected = self.selected.unwrap_or(self.offset);
                let next = match key {
                    Keycode::Up => selected.saturating_sub(1),
                    Keycode::Down if self.selected.is_none() => selected,
                    Keycode::Down => selected + 1,
                    Keycode::PageUp => selected.saturating_sub(rows),
                    Keycode::PageDown => selected + rows,
                    Keycode::Home => 0,
                    _ => last,
                };
                if !self.folders.is_empty() {
                    self.selected = Some(next.min(last));
                    let next = next.min(last);
                    self.offset = self
                        .offset
                        .clamp(next.saturating_sub(rows - 1), next)
                        .min(self.folders.len().saturating_sub(rows));
                    self.overwrite = false;
                }
            }
            _ if self.editing && !self.composing() => {
                let previous = self.draft.value.clone();
                let shift = mods.intersects(Mod::LSHIFTMOD | Mod::RSHIFTMOD);
                self.draft.key(key, shift, control, false, video);
                if self.draft.value != previous {
                    self.error = None;
                    self.overwrite = false;
                }
            }
            _ => {}
        }
        Outcome::Stay
    }

    fn focus_path(&mut self) {
        self.editing = true;
        self.draft.select_all();
    }

    fn leave_path(&mut self) {
        if self.editing {
            self.draft = Edit::with_limit(self.current.to_string_lossy().into_owned(), PATH_LIMIT);
            self.editing = false;
            self.dragging = false;
            self.error = None;
        }
    }

    pub(crate) fn click(&mut self, point: (i32, i32), size: (i32, i32), clicks: u8) -> Outcome {
        let (x, y) = point;
        let (width, height) = size;
        if choose_button(width, height).contains(x, y) {
            return Outcome::Choose;
        }
        if view::dialog_button(width, height, false).contains(x, y) {
            return Outcome::Cancel;
        }
        #[cfg(windows)]
        if let Some(index) = (0..self.drives.len())
            .find(|&index| drive_button(width, self.drives.len(), index).contains(x, y))
        {
            self.open(self.drives[index].clone());
            return Outcome::Stay;
        }
        if go_button(width).contains(x, y) {
            self.open_draft();
        } else if parent_button(width).contains(x, y) {
            self.open_parent();
        } else if list_area(width, height).contains(x, y) {
            let list = list_area(width, height).inset(1);
            self.leave_path();
            if x >= list.0 + list.2 - 10 && self.folders.len() > visible_rows(height) {
                let rows = visible_rows(height);
                let relative = y.saturating_sub(list.1).max(0).min(list.3 - 1) as usize;
                self.offset = relative * (self.folders.len() - rows) / (list.3 as usize - 1);
                self.selected = None;
            } else if let Some(row) =
                (0..visible_rows(height)).find(|row| list_row(width, height, *row).contains(x, y))
            {
                let index = self.offset + row;
                if index < self.folders.len() {
                    self.selected = Some(index);
                    self.overwrite = false;
                    if clicks >= 2 {
                        self.open_selected();
                    }
                }
            }
        }
        Outcome::Stay
    }

    pub(crate) fn scroll(&mut self, step: isize, height: i32) {
        let rows = visible_rows(height);
        self.offset = self
            .offset
            .saturating_add_signed(step)
            .min(self.folders.len().saturating_sub(rows));
        if self
            .selected
            .is_some_and(|index| index < self.offset || index >= self.offset + rows)
        {
            self.selected = None;
        }
    }

    pub(crate) fn input_position(
        &mut self,
        width: i32,
        measure: impl Fn(&str) -> i32,
    ) -> Option<(Box2, i32)> {
        self.editing.then(|| {
            self.draft
                .input_position(path_field(width).inset(6), measure, false)
        })
    }

    pub(crate) fn path_click(
        &mut self,
        x: i32,
        width: i32,
        clicks: u8,
        shift: bool,
        measure: impl Fn(&str) -> i32,
    ) {
        let extend = shift && self.editing;
        self.editing = true;
        self.draft.click(
            x - path_field(width).inset(6).0,
            extend,
            clicks > 1,
            measure,
        );
        self.dragging = clicks <= 1;
    }

    pub(crate) fn path_drag(&mut self, x: i32, width: i32, measure: impl Fn(&str) -> i32) {
        self.draft
            .click(x - path_field(width).inset(6).0, true, false, measure);
    }

    pub(crate) fn draw(&self, painter: &Painter, settings: &Settings, width: i32, height: i32) {
        const ERROR: u32 = 0x8a3030;
        const SELECTED: u32 = 0xd5e9ff;
        painter.fill(Box2(0, 0, width, height), 0xf5f5f5);
        let field = path_field(width);
        painter.fill(field, WHITE);
        painter.border(field, if self.editing { 0x467eac } else { 0xa1a7ae });
        draw_edit(painter, field.inset(6), &self.draft, self.editing, false);
        view::button(painter, go_button(width), settings.text(Text::CsvGo));
        view::control_button(
            painter,
            parent_button(width),
            settings.text(Text::CsvParent),
            if self.current.parent().is_some() {
                view::ButtonState::Normal
            } else {
                view::ButtonState::Disabled
            },
            false,
        );
        #[cfg(windows)]
        for (index, drive) in self.drives.iter().enumerate() {
            let root = drive.to_string_lossy();
            view::control_button(
                painter,
                drive_button(width, self.drives.len(), index),
                root.trim_end_matches('\\'),
                if self.current.starts_with(drive) {
                    view::ButtonState::Pressed
                } else {
                    view::ButtonState::Normal
                },
                false,
            );
        }

        let list = list_area(width, height);
        let rows = visible_rows(height);
        painter.fill(list, WHITE);
        painter.border(list, 0xa1a7ae);
        for (row, folder) in self.folders.iter().skip(self.offset).take(rows).enumerate() {
            let area = list_row(width, height, row);
            if self.selected == Some(self.offset + row) {
                painter.fill(area, SELECTED);
            }
            let Box2(x, y, _, _) = area;
            painter.fill(Box2(x + 7, y + 7, 7, 4), 0xc89637);
            painter.fill(Box2(x + 7, y + 10, 16, 10), 0xe3b757);
            painter.text(
                Box2(x + 29, y, area.2 - 35, ROW_HEIGHT),
                &folder.to_string_lossy(),
                15,
                Align::Left,
                INK,
            );
        }
        if self.folders.is_empty() && self.error.is_none() {
            painter.text(
                list.inset(10),
                settings.text(Text::CsvEmptyFolder),
                15,
                Align::Center,
                0x536170,
            );
        }
        if self.folders.len() > rows {
            let track = list.inset(1);
            let height = (track.3 as usize * rows / self.folders.len()).max(12);
            let position = (track.3 as usize - height) * self.offset / (self.folders.len() - rows);
            let x = track.0 + track.2 - 10;
            painter.fill(Box2(x, track.1, 10, track.3), 0xe7e9ec);
            painter.fill(
                Box2(x + 1, track.1 + position as i32, 8, height as i32),
                0x929da9,
            );
        }
        let status = Box2(12, list.1 + list.3 + 1, width - 24, 25);
        if let Some(error) = &self.error {
            painter.text(
                status,
                &format!("{} {error}", settings.text(Text::CsvFolderError)),
                14,
                Align::Left,
                ERROR,
            );
        } else if self.overwrite {
            painter.text(
                status,
                settings.text(Text::CsvOverwrite),
                14,
                Align::Left,
                ERROR,
            );
        }
        view::button(
            painter,
            choose_button(width, height),
            settings.text(Text::CsvChoose),
        );
        view::button(
            painter,
            view::dialog_button(width, height, false),
            settings.text(Text::Cancel),
        );
    }
}

#[cfg(windows)]
fn logical_drives() -> Vec<PathBuf> {
    use windows_sys::Win32::Storage::FileSystem::GetLogicalDrives;

    let mask = unsafe { GetLogicalDrives() };
    (b'A'..=b'Z')
        .filter(|&letter| mask & (1 << (letter - b'A')) != 0)
        .map(|letter| PathBuf::from(format!("{}:\\", char::from(letter))))
        .collect()
}

#[cfg(windows)]
fn drive_button(width: i32, count: usize, index: usize) -> Box2 {
    let stride = ((width - 24) / count as i32).min(52);
    Box2(12 + index as i32 * stride, 52, stride - 2, 28)
}

fn read_folders(directory: &Path) -> io::Result<Vec<OsString>> {
    let mut folders = Vec::new();
    for entry in fs::read_dir(directory)? {
        let entry = entry?;
        if entry
            .file_type()
            .is_ok_and(|kind| kind.is_dir() || (kind.is_symlink() && entry.path().is_dir()))
        {
            folders.push(entry.file_name());
        }
    }
    folders.sort_by_cached_key(|name| name.to_string_lossy().to_lowercase());
    Ok(folders)
}

#[cfg(windows)]
fn resolve_path(path: &Path) -> io::Result<PathBuf> {
    std::path::absolute(path)
}

#[cfg(not(windows))]
fn resolve_path(path: &Path) -> io::Result<PathBuf> {
    fs::canonicalize(path)
}

pub(crate) fn path_field(width: i32) -> Box2 {
    Box2(12, 12, width - 236, 32)
}

fn go_button(width: i32) -> Box2 {
    Box2(width - 216, 12, 96, 32)
}

fn parent_button(width: i32) -> Box2 {
    Box2(width - 112, 12, 100, 32)
}

fn list_area(width: i32, height: i32) -> Box2 {
    Box2(12, LIST_TOP, width - 24, height - LIST_TOP - 70)
}

fn list_row(width: i32, height: i32, index: usize) -> Box2 {
    let list = list_area(width, height).inset(1);
    Box2(
        list.0,
        list.1 + ROW_HEIGHT * index as i32,
        list.2 - 10,
        ROW_HEIGHT,
    )
}

fn visible_rows(height: i32) -> usize {
    ((list_area(1, height).3 - 2) / ROW_HEIGHT).max(1) as usize
}

fn choose_button(width: i32, height: i32) -> Box2 {
    Box2(width - 268, height - 42, 156, 29)
}

#[cfg(test)]
mod tests {
    use super::*;

    const WINDOW: (i32, i32) = (SIZE.0 as i32, SIZE.1 as i32);

    fn center(area: Box2) -> (i32, i32) {
        (area.0 + area.2 / 2, area.1 + area.3 / 2)
    }

    #[test]
    fn typing_a_path_and_pressing_enter_opens_it_without_exporting() {
        let root = tempfile::tempdir().unwrap();
        let child = root.path().join("测试目录");
        fs::create_dir(&child).unwrap();
        let mut picker = Picker::new(root.path());

        assert!(picker.input_position(WINDOW.0, |_| 0).is_some());
        picker.text("找不到");
        assert!(matches!(picker.enter(), Outcome::Stay));
        assert!(picker.error.is_some());
        assert_eq!(picker.current, root.path());

        picker.focus_path();
        picker.text(&child.to_string_lossy());
        assert!(matches!(picker.enter(), Outcome::Stay));
        assert_eq!(picker.destination(), Some(child.as_path()));
        assert!(picker.input_position(WINDOW.0, |_| 0).is_none());
    }

    #[test]
    fn clicking_and_dragging_select_part_of_the_path_for_replacement() {
        let root = tempfile::tempdir().unwrap();
        let mut picker = Picker::new(root.path());
        let origin = path_field(WINDOW.0).inset(6).0;
        let measure = |text: &str| text.chars().count() as i32 * 10;
        picker.text("甲乙丙丁");
        picker.input_position(WINDOW.0, measure);
        picker.path_click(origin + 10, WINDOW.0, 1, false, measure);
        picker.path_drag(origin + 30, WINDOW.0, measure);
        picker.text("新");
        assert_eq!(picker.draft.value, "甲新丁");
        assert_eq!(picker.input_position(WINDOW.0, measure).unwrap().1, 20);
    }

    #[cfg(windows)]
    #[test]
    fn drive_buttons_switch_between_available_drive_roots() {
        let temp = tempfile::tempdir().unwrap();
        let mut picker = Picker::new(temp.path());
        let drives: Vec<_> = picker
            .drives
            .iter()
            .enumerate()
            .filter(|(_, drive)| read_folders(drive).is_ok())
            .map(|(index, drive)| (index, drive.clone()))
            .collect();
        assert!(!drives.is_empty());
        for (index, root) in drives.into_iter().rev() {
            let button = center(drive_button(WINDOW.0, picker.drives.len(), index));
            assert!(matches!(picker.click(button, WINDOW, 1), Outcome::Stay));
            assert_eq!(picker.destination(), Some(root.as_path()));
        }
    }

    #[test]
    fn browsing_chooses_a_directory_and_resets_overwrite_when_moving() {
        let root = tempfile::tempdir().unwrap();
        let first = root.path().join("Alpha");
        let second = root.path().join("文件夹");
        fs::create_dir(&second).unwrap();
        fs::create_dir(&first).unwrap();
        fs::write(root.path().join("ignored.csv"), []).unwrap();
        let mut picker = Picker::new(root.path());

        assert_eq!(
            picker.folders,
            [OsString::from("Alpha"), OsString::from("文件夹")]
        );
        assert_eq!(picker.confirm_overwrite(true), None);
        let folder = center(list_row(WINDOW.0, WINDOW.1, 1));
        picker.click(folder, WINDOW, 1);
        assert_eq!(picker.destination(), Some(root.path()));
        picker.click(folder, WINDOW, 2);
        assert_eq!(picker.destination(), Some(second.as_path()));
        assert_eq!(picker.confirm_overwrite(true), None);
        assert!(matches!(
            picker.click(center(choose_button(WINDOW.0, WINDOW.1)), WINDOW, 1),
            Outcome::Choose
        ));
        assert_eq!(picker.confirm_overwrite(true), Some(true));
        picker.click(center(parent_button(WINDOW.0)), WINDOW, 1);
        assert_eq!(picker.destination(), Some(root.path()));
        assert_eq!(picker.confirm_overwrite(false), Some(false));
    }

    #[test]
    fn a_bad_address_keeps_the_directory_and_scrolling_reaches_the_last_row() {
        let root = tempfile::tempdir().unwrap();
        let total = visible_rows(WINDOW.1) + 5;
        for index in 0..total {
            fs::create_dir(root.path().join(format!("Folder {index:02}"))).unwrap();
        }
        let mut picker = Picker::new(root.path());
        picker.focus_path();
        picker.text("missing");
        assert_eq!(picker.destination(), None);
        assert_eq!(picker.current, root.path());
        picker.scroll(100, WINDOW.1);
        let last = center(list_row(WINDOW.0, WINDOW.1, visible_rows(WINDOW.1) - 1));
        picker.click(last, WINDOW, 2);
        assert_eq!(
            picker.destination(),
            Some(
                root.path()
                    .join(format!("Folder {:02}", total - 1))
                    .as_path()
            )
        );
    }
}
