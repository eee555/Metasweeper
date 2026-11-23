include!("native.rs");

use crate::{config, layout::PRESETS};
use hmac::{Hmac, Mac};
use sha2::Sha256;
use std::{fs::{self, OpenOptions}, io::{self, Write}, path::{Path, PathBuf},
          ptr::NonNull, sync::atomic::{AtomicU32, Ordering}, time::{Duration, Instant}};

pub struct Round {
    session: NonNull<GameSession>,
    pub cells: Vec<u8>,
    pub status: GameStatus,
    pub metrics: Option<ReplayMetrics>,
    pub player: String,
    race: String,
    pub country: String,
    last_position: Option<(usize, usize)>,
    cursor_limit_used: bool,
    pub timing_valid: bool,
    started_clock_ms: Option<u64>,
    last_clock_check: Option<Instant>,
}

impl Round {
    pub fn new(settings: &config::Settings) -> Self {
        let (rows, cols, mines) = PRESETS[settings.level];
        Self {
            session: NonNull::new(new_game(rows as usize, cols as usize, mines)).expect("native game allocation"),
            cells: vec![10; (rows * cols) as usize],
            status: GameStatus { seconds: 0.0, path: 0.0, phase: 0, left: 0, right: 0, chords: 0, flags: 0, mouse_visual: 0 },
            metrics: None, player: settings.player.clone(), race: settings.race.clone(),
            country: config::country_code(&settings.country).unwrap_or_default(),
            last_position: None, cursor_limit_used: false, timing_valid: true,
            started_clock_ms: None, last_clock_check: None,
        }
    }

    pub fn set_identity(&mut self, settings: &config::Settings) {
        if self.status.phase == 0 {
            self.player = settings.player.clone();
            self.race = settings.race.clone();
            self.country = config::country_code(&settings.country).unwrap_or_default();
        }
    }

    pub fn record_cursor_lock(&mut self, enabled: bool) {
        if self.phase() == 1 { self.cursor_limit_used |= enabled; }
    }

    pub fn play(&mut self, button: u32, x: usize, y: usize, settings: &config::Settings) {
        if self.ended() { return; }
        let now = Instant::now();
        let clock = crate::platform::clock_ms();
        let ready = self.status.phase == 0;
        let accepted = unsafe { game_button(self.session.as_mut(), button, x, y, settings.flag_win as u32, self.cells.as_mut_ptr()) };
        if accepted == 0 { return; }
        self.last_position = Some((x, y));
        self.refresh();
        if ready && self.status.phase != 0 {
            self.cursor_limit_used = settings.cursor_lock;
            self.started_clock_ms = clock;
            self.last_clock_check = Some(now);
        }
        if self.ended() { self.check_clock(clock, now, true); }
    }

    pub fn track(&mut self, x: usize, y: usize) {
        if !self.ended() && self.last_position != Some((x, y)) {
            unsafe { game_move(self.session.as_mut(), x, y) };
            self.last_position = Some((x, y));
        }
    }

    pub fn refresh(&mut self) {
        let game = unsafe { self.session.as_ref() };
        game_status(game, &mut self.status);
        if self.status.phase == 1 {
            self.check_clock(crate::platform::clock_ms(), Instant::now(), false);
        }
        if self.ended() && self.metrics.is_none() {
            // A zeroed ReplayMetrics is valid: it contains only integer and float fields.
            let mut metrics: ReplayMetrics = unsafe { std::mem::zeroed() };
            if game_metrics(unsafe { self.session.as_ref() }, &mut metrics) == 1 {
                self.metrics = Some(metrics);
            }
        }
    }

    pub fn ended(&self) -> bool { self.status.phase >= 2 }

    pub fn should_auto_restart(&self, threshold: i32) -> bool {
        if self.phase() != 3 || threshold <= 0 || !self.timing_valid { return false; }
        let video = &unsafe { self.session.as_ref() }.video;
        let total = video.static_params.bbbv;
        total != 0 && video.get_bbbv_solved()
            .is_ok_and(|solved| solved * 100 < total * threshold as usize)
    }

    pub fn seconds(&self) -> f64 { self.status.seconds }
    pub fn remaining(&self, mines: usize, flag_win: bool) -> u32 {
        if self.status.phase == 2 && flag_win { 0 }
        else { (mines as u32).saturating_sub(self.status.flags) }
    }
    pub fn phase(&self) -> u32 { self.status.phase }
    pub fn mouse_visual(&self) -> u32 { self.status.mouse_visual }

    fn check_clock(&mut self, clock: Option<u64>, now: Instant, terminal: bool) {
        let (Some(clock), Some(start), Some(last)) =
            (clock, self.started_clock_ms, self.last_clock_check) else { return };
        if !self.timing_valid
            || (!terminal && now.saturating_duration_since(last) < Duration::from_secs(1)) { return; }
        self.last_clock_check = Some(now);
        self.timing_valid = clock.checked_sub(start)
            .is_some_and(|elapsed| (self.seconds() * 1000.0 - elapsed as f64).abs() <= 100.0);
    }

    pub fn replay(&mut self, settings: &config::Settings) -> io::Result<Replay> {
        if !self.ended() || !self.timing_valid {
            return Err(io::Error::other("The game did not finish with a valid clock"));
        }
        let game = unsafe { self.session.as_mut() };
        let time = game.video.get_time();
        let total = game.video.static_params.bbbv;
        let speed = game.video.get_bbbv_s().unwrap_or(f64::NAN);
        let name = format!("{}_0_{}_{total}_{}_{}{}", ["b", "i", "e"][settings.level],
            decimal(time), decimal(speed), safe_identifier(&self.player),
            if self.status.phase == 3 { "_fail" } else { "" });
        let mut len = 0;
        let identity = format!("{}\0{}\0{}", self.player, self.race, self.country);
        let raw = unsafe { encode_replay(game, identity.as_ptr(), identity.len(),
            self.cursor_limit_used as u32, u32::from(settings.auto_replay > 0), &mut len) };
        if raw.is_null() { return Err(io::Error::other("EVF data unavailable")); }
        let mut data = unsafe { std::slice::from_raw_parts(raw, len).to_vec() };
        unsafe { free_replay(raw, len) };
        sign(&mut data)?;
        Ok(Replay { name, data })
    }
}

impl Drop for Round {
    fn drop(&mut self) { unsafe { free_game(self.session.as_ptr()) } }
}

pub fn decimal(v: f64) -> String {
    if v.is_nan() { "nan".into() }
    else if v == f64::INFINITY { "inf".into() }
    else if v == f64::NEG_INFINITY { "-inf".into() }
    else { format!("{v:.3}") }
}

fn safe_identifier(name: &str) -> String {
    crate::platform::filename_stem(name)
}

fn sign(data: &mut Vec<u8>) -> io::Result<()> {
    if !data.ends_with(&[0, 0, 0]) { return Err(io::Error::other("Invalid unsigned EVF header")); }
    data.truncate(data.len() - 2);
    let mut hmac = Hmac::<Sha256>::new_from_slice(include_bytes!("../assets/replay-key.bin"))
        .expect("valid embedded HMAC key");
    hmac.update(data);
    data.extend_from_slice(&[0, 32]);
    data.extend_from_slice(&hmac.finalize().into_bytes());
    Ok(())
}

pub struct Replay { pub name: String, pub data: Vec<u8> }

impl Replay {
    pub fn save(&self, dir: &Path, chosen: Option<&Path>) -> io::Result<PathBuf> {
        let actual_dir = chosen.and_then(Path::parent).unwrap_or(dir);
        fs::create_dir_all(actual_dir)?;
        static NEXT: AtomicU32 = AtomicU32::new(0);
        let temp = actual_dir.join(format!(".mini-{}-{}.tmp", std::process::id(), NEXT.fetch_add(1, Ordering::Relaxed)));
        let mut file = OpenOptions::new().create_new(true).write(true).open(&temp)?;
        let result = file.write_all(&self.data);
        drop(file);
        let result = result.and_then(|_| {
            if let Some(path) = chosen {
                fs::rename(&temp, path).map(|()| path.to_owned())
            } else {
                for suffix in 1.. {
                    let filename = if suffix == 1 { format!("{}.evf", self.name) } else { format!("{}({suffix}).evf", self.name) };
                    let path = dir.join(filename);
                    match fs::hard_link(&temp, &path) {
                        Err(e) if e.kind() == io::ErrorKind::AlreadyExists => continue,
                        Err(e) if matches!(e.raw_os_error(), Some(1 | 38 | 95)) => {
                            // Some portable volumes do not support hard links.
                            let mut output = match OpenOptions::new().create_new(true).write(true).open(&path) {
                                Ok(file) => file,
                                Err(e) if e.kind() == io::ErrorKind::AlreadyExists => continue,
                                Err(e) => return Err(e),
                            };
                            let result = output.write_all(&self.data);
                            drop(output);
                            if result.is_err() { let _ = fs::remove_file(&path); }
                            return result.map(|()| path);
                        }
                        Err(e) => return Err(e),
                        Ok(()) => return Ok(path),
                    }
                }
                unreachable!()
            }
        });
        let _ = fs::remove_file(temp);
        result
    }
}

#[cfg(test)]
mod linux_tests {
    use super::*;

    #[test]
    fn auto_restart_requires_loss_below_the_threshold() {
        let root = std::env::temp_dir().join(format!("metasweeper-mini-test-{}", std::process::id()));
        let settings = config::Settings::read(&root).unwrap();
        for (second_cell, lost) in [((3, 3), true), ((3, CELL_PIXELS + 3), false)] {
            let mut round = Round::new(&settings);
            let session = unsafe { round.session.as_mut() };
            let board = vec![vec![-1, 2], vec![2, -1]];
            session.video = BaseVideo::<Vec<Vec<i32>>>::new(board, CELL_PIXELS as u8);
            session.laid = true;

            round.play(0, CELL_PIXELS + 3, 3, &settings);
            round.play(1, CELL_PIXELS + 3, 3, &settings);
            assert!(!round.should_auto_restart(100));
            round.play(0, second_cell.0, second_cell.1, &settings);
            round.play(1, second_cell.0, second_cell.1, &settings);

            assert_eq!(round.phase(), if lost { 3 } else { 2 });
            assert!(!round.should_auto_restart(-100));
            assert!(!round.should_auto_restart(0));
            assert!(!round.should_auto_restart(49));
            assert!(!round.should_auto_restart(50));
            assert_eq!(round.should_auto_restart(51), lost);
        }
    }

    #[test]
    fn clock_check_uses_the_same_limit_for_lag_identifiers() {
        let root = std::env::temp_dir().join(format!("metasweeper-mini-test-{}", std::process::id()));
        let mut settings = config::Settings::read(&root).unwrap();
        settings.player = "[lag]player".into();
        let start = Instant::now();
        for (elapsed_ms, expected) in [(1100, true), (1101, false)] {
            let mut round = Round::new(&settings);
            round.started_clock_ms = Some(10_000);
            round.last_clock_check = Some(start);
            round.status.seconds = 1.0;
            round.check_clock(Some(10_000 + elapsed_ms), start + Duration::from_secs(1), false);
            assert_eq!(round.timing_valid, expected);
        }
    }

    #[test]
    fn evf_records_lock_at_start_or_during_play() {
        let root = std::env::temp_dir().join(format!("metasweeper-mini-test-{}", std::process::id()));
        let mut settings = config::Settings::read(&root).unwrap();
        for (at_start, during_play, expected) in [(true, false, true), (false, true, true), (false, false, false)] {
            let mut round = Round::new(&settings);
            let session = unsafe { round.session.as_mut() };
            let board = vec![vec![-1, 2, -1], vec![1, 2, 1], vec![0, 0, 0]];
            session.video = BaseVideo::<Vec<Vec<i32>>>::new(board, CELL_PIXELS as u8);
            session.laid = true;

            round.record_cursor_lock(true);
            settings.cursor_lock = at_start;
            round.play(0, CELL_PIXELS + 3, CELL_PIXELS + 3, &settings);
            round.play(1, CELL_PIXELS + 3, CELL_PIXELS + 3, &settings);
            assert_eq!(round.phase(), 1);
            round.record_cursor_lock(during_play);
            settings.cursor_lock = false;
            round.record_cursor_lock(false);
            round.play(0, 3, 3, &settings);
            round.play(1, 3, 3, &settings);
            assert_eq!(round.phase(), 3);
            round.record_cursor_lock(true);

            let replay = round.replay(&settings).unwrap();
            assert_eq!(replay.data[2] & 0x40 != 0, expected);
        }
    }

    #[test]
    fn evf_signature_matches_windows_fixture() {
        let mut data = vec![4, 0, 0, 3, 3, 10, 16, 1, 2, 3, 4, 5, 0, 0, 0];
        sign(&mut data).unwrap();
        assert_eq!(&data[13..15], &[0, 32]);
        assert_eq!(data[15..].iter().map(|byte| format!("{byte:02x}")).collect::<String>(),
            "8dc128859f3e18c0fec1c2e2b07b6e077f27dbb167a7a8a575be36fe45d4756f");
    }

}

impl Round {
    pub fn counter_rows(&self, mode: &str) -> Vec<String> {
        let time = self.seconds();
        let rate = |n| format!("{n}@{}", decimal(if time > 0.0 { n as f64 / time } else { 0.0 }));
        let mut rows = vec!["--".to_owned(); 17];
        rows[0] = mode.into();
        rows[1] = decimal(time);
        rows[8] = rate(self.status.left);
        rows[9] = rate(self.status.right);
        rows[10] = rate(self.status.chords);
        rows[15] = format!("{:.1}", self.status.path);
        if let Some(m) = &self.metrics {
            let metric = |v: f64| if v.is_nan() { "--".into() } else if v == f64::INFINITY { "∞".into() } else { decimal(v) };
            rows[2] = metric(m.estimated_time);
            rows[3] = format!("{}/{}", m.solved, m.total);
            rows[4] = metric(m.three_bv_per_second);
            rows[5] = format!("{}@{}", m.zini, metric(m.zini as f64 / m.estimated_time));
            rows[6] = m.openings.to_string();
            rows[7] = m.islands.to_string();
            for (i, value) in [(11,m.stnb), (12,m.ioe), (13,m.thrp), (14,m.corr), (16,m.pluck)] {
                rows[i] = metric(value);
            }
        }
        rows
    }
}
