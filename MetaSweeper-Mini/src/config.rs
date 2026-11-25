use crate::{
    counter_formula::CounterConfig,
    layout::{COUNTER_MAX, COUNTER_MIN, PRESETS, SECTIONS},
};
use flate2::read::DeflateDecoder;
use std::{
    fs,
    io::{self, Read},
    path::{Path, PathBuf},
    sync::{Arc, OnceLock},
};

pub const CODES: [&str; 5] = ["zh_CN", "en_US", "de_DE", "pl_PL", "ja_JP"];
pub const LANGUAGES: [&str; 5] = ["简体中文", "English", "Deutsch", "Polski", "日本語"];
pub const DEFAULT_AUTO_REPLAY: i32 = 30;
pub use crate::text::Text;
use crate::text::STRINGS;

#[derive(Clone)]
pub struct Settings {
    pub level: usize,
    pub pixels: [i32; 3],
    pub lang: usize,
    pub player: String,
    pub race: String,
    pub country: String,
    pub autosave: usize,
    pub auto_replay: i32,
    pub cursor_lock: bool,
    pub flag_win: bool,
    pub counter: bool,
    pub counter_pixels: i32,
    pub counter_config: Arc<CounterConfig>,
    pub identity: bool,
    pub position: Option<(i32, i32)>,
    pub counter_position: Option<(i32, i32)>,
}

impl Settings {
    pub fn read(root: &Path) -> io::Result<Self> {
        let ini = Ini::open(root)?;
        let n = |section, key, fallback| {
            ini.get(section, key)
                .and_then(|s| s.parse().ok())
                .unwrap_or(fallback)
        };
        let get = |key, fallback: &str| ini.get("DEFAULT", key).unwrap_or(fallback).to_owned();
        let flag = |section, key, fallback| match ini
            .get(section, key)
            .map(str::to_ascii_lowercase)
            .as_deref()
        {
            Some("true" | "1" | "yes" | "on") => true,
            Some("false" | "0" | "no" | "off") => false,
            _ => fallback,
        };
        let board = (
            n("DEFAULT", "row", 8),
            n("DEFAULT", "column", 8),
            n("DEFAULT", "minenum", 10),
        );
        let level = PRESETS
            .iter()
            .enumerate()
            .find(|(i, (rows, cols, mines))| {
                board == (*rows, *cols, *mines as i32)
                    && ini.get("DEFAULT", "gamemode").unwrap_or("0") == "0"
                    && ini.get(SECTIONS[*i], "gamemode").unwrap_or("0") == "0"
            })
            .map(|(i, _)| i)
            .unwrap_or(0);
        let position = |x, y| {
            Some((
                ini.get("DEFAULT", x)?.parse().ok()?,
                ini.get("DEFAULT", y)?.parse().ok()?,
            ))
        };
        Ok(Self {
            level,
            pixels: SECTIONS.map(|section| n(section, "pixsize", 20).clamp(5, 255)),
            lang: CODES
                .iter()
                .position(|code| code.eq_ignore_ascii_case(&get("language", "")))
                .unwrap_or(0),
            player: clean_player(&get("player_identifier", "")),
            race: clean(&get("race_identifier", "")),
            country: clean(&get("country", "")),
            autosave: if !flag("DEFAULT", "autosave_video", true) {
                2
            } else if flag("WINFORMS", "autosave_losses", false) {
                0
            } else {
                1
            },
            auto_replay: n("DEFAULT", "auto_replay", -DEFAULT_AUTO_REPLAY).clamp(-100, 100),
            cursor_lock: flag("DEFAULT", "cursor_limit", false),
            flag_win: flag("DEFAULT", "end_then_flag", true),
            counter: flag("WINFORMS", "show_counter", true),
            identity: flag("WINFORMS", "show_identity", true),
            counter_pixels: n("DEFAULT", "scoreboard_pixsize", 27).clamp(COUNTER_MIN, COUNTER_MAX),
            counter_config: Arc::new(CounterConfig::read(root)?),
            position: position("mainwinleft", "mainwintop"),
            counter_position: position("scoreboardleft", "scoreboardtop"),
        })
    }

    pub fn text(&self, key: Text) -> &'static str {
        STRINGS[key as usize][self.lang]
    }

    pub fn save(&self, root: &Path) -> io::Result<()> {
        let mut ini = Ini::open(root)?;
        let preset = PRESETS[self.level];
        for (key, value) in [
            ("language", CODES[self.lang].into()),
            ("player_identifier", self.player.clone()),
            ("race_identifier", self.race.clone()),
            ("country", self.country.clone()),
            ("autosave_video", (self.autosave != 2).to_string()),
            ("cursor_limit", self.cursor_lock.to_string()),
            ("auto_replay", self.auto_replay.to_string()),
            ("end_then_flag", self.flag_win.to_string()),
            ("scoreboard_pixsize", self.counter_pixels.to_string()),
            ("row", preset.0.to_string()),
            ("column", preset.1.to_string()),
            ("minenum", preset.2.to_string()),
        ] {
            ini.set("DEFAULT", key, &value);
        }
        if let Some((x, y)) = self.position {
            ini.set("DEFAULT", "mainwinleft", &x.to_string());
            ini.set("DEFAULT", "mainwintop", &y.to_string());
        }
        if let Some((x, y)) = self.counter_position {
            ini.set("DEFAULT", "scoreboardleft", &x.to_string());
            ini.set("DEFAULT", "scoreboardtop", &y.to_string());
        }
        for (key, value) in [
            ("show_counter", self.counter),
            ("show_identity", self.identity),
            ("autosave_losses", self.autosave == 0),
        ] {
            ini.set("WINFORMS", key, &value.to_string());
        }
        for (section, pixels) in SECTIONS.into_iter().zip(self.pixels) {
            ini.set(section, "pixsize", &pixels.to_string());
        }
        ini.save()
    }
}

pub fn clean(value: &str) -> String {
    let value: String = value
        .chars()
        .filter(|ch| !matches!(ch, '\0' | '\r' | '\n'))
        .collect();
    crate::platform::limit_identifier(&value)
}

pub fn clean_player(value: &str) -> String {
    let value = clean(value);
    if value.is_empty() {
        "匿名玩家".into()
    } else {
        value
    }
}

pub fn country_code(value: &str) -> Option<String> {
    let value = value.trim();
    if value.is_empty() {
        return Some(String::new());
    }
    if value.len() == 2 && value.bytes().all(|b| b.is_ascii_alphabetic()) {
        return Some(if value.eq_ignore_ascii_case("xx") {
            String::new()
        } else {
            value.to_ascii_uppercase()
        });
    }
    countries()
        .find(|(_, name)| name.eq_ignore_ascii_case(value))
        .map(|(code, _)| {
            if code == "XX" {
                String::new()
            } else {
                code.into()
            }
        })
}

pub fn countries() -> impl Iterator<Item = (&'static str, &'static str)> {
    static COUNTRIES: OnceLock<String> = OnceLock::new();
    COUNTRIES
        .get_or_init(|| {
            let mut text = String::new();
            DeflateDecoder::new(
                &include_bytes!(concat!(env!("OUT_DIR"), "/countries.deflate"))[..],
            )
            .read_to_string(&mut text)
            .expect("embedded country table");
            text
        })
        .lines()
        .filter_map(|line| line.split_once('\t'))
}

struct Ini {
    path: PathBuf,
    lines: Vec<String>,
}

impl Ini {
    fn open(root: &Path) -> io::Result<Self> {
        let path = root.join("gameSetting.ini");
        let text = match fs::read_to_string(&path) {
            Ok(text) => text,
            Err(e) if e.kind() == io::ErrorKind::NotFound => String::new(),
            Err(e) => return Err(e),
        };
        Ok(Self {
            path,
            lines: text
                .trim_start_matches('\u{feff}')
                .lines()
                .map(str::to_owned)
                .collect(),
        })
    }

    fn locate(&self, section: &str, key: &str) -> (Option<usize>, Option<usize>) {
        let (mut active, mut found, mut end) = (false, None, None);
        for (i, line) in self.lines.iter().enumerate() {
            let text = line.trim();
            if let Some(name) = text.strip_prefix('[').and_then(|s| s.split_once(']')) {
                active = name.0.trim().eq_ignore_ascii_case(section);
            }
            if active {
                end = Some(i + 1);
                if !text.starts_with(['#', ';', '['])
                    && text
                        .split_once(['=', ':'])
                        .is_some_and(|(k, _)| k.trim().eq_ignore_ascii_case(key))
                {
                    found = Some(i);
                }
            }
        }
        (found, end)
    }

    fn get(&self, section: &str, key: &str) -> Option<&str> {
        let i = self.locate(section, key).0?;
        Some(self.lines[i].split_once(['=', ':'])?.1.trim())
    }

    fn set(&mut self, section: &str, key: &str, value: &str) {
        let line = format!("{key} = {value}");
        let (index, end) = self.locate(section, key);
        if let Some(i) = index {
            self.lines[i] = line;
        } else if let Some(mut i) = end {
            while i > 0 && self.lines[i - 1].is_empty() {
                i -= 1;
            }
            self.lines.insert(i, line);
        } else {
            if !self.lines.is_empty() {
                self.lines.push(String::new());
            }
            self.lines.extend([format!("[{section}]"), line]);
        }
    }

    fn save(self) -> io::Result<()> {
        let temp = self
            .path
            .with_extension(format!("{}.tmp", std::process::id()));
        fs::write(&temp, self.lines.join("\n") + "\n")?;
        let result = fs::rename(&temp, &self.path);
        if result.is_err() {
            let _ = fs::remove_file(temp);
        }
        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_to_autosaving_wins_and_respects_saved_modes() {
        let root = tempfile::tempdir().unwrap();
        let mut settings = Settings::read(root.path()).unwrap();
        assert_eq!(settings.autosave, 1);

        for mode in [1, 0, 2] {
            settings.autosave = mode;
            settings.save(root.path()).unwrap();
            assert_eq!(Settings::read(root.path()).unwrap().autosave, mode);
        }
    }
}
