use crate::{
    config,
    layout::{COUNTER_ROWS, PRESETS},
    native::{GameSession, GameStatus, ReplayMetrics},
    replay_signature::sign,
    stats::{GameResult, Record},
};
use std::{
    borrow::Cow,
    fs::{self, OpenOptions},
    io::{self, Write},
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicU32, Ordering},
        Arc,
    },
    time::{Duration, Instant},
};

pub type CounterRows = [Cow<'static, str>; COUNTER_ROWS];

pub struct Round {
    session: GameSession,
    pub cells: Vec<u8>,
    pub status: GameStatus,
    pub metrics: Option<ReplayMetrics>,
    pub player: String,
    race: String,
    pub country: String,
    last_position: Option<(usize, usize)>,
    last_input_at: Instant,
    cursor_limit_used: bool,
    pub timing_valid: bool,
    started_clock_ms: Option<u64>,
    last_clock_check: Option<Instant>,
    replay: Option<Result<Replay, String>>,
}

impl Round {
    pub fn new(settings: &config::Settings) -> Self {
        let (rows, cols, mines) = PRESETS[settings.level];
        Self {
            session: GameSession::new(rows as usize, cols as usize, mines),
            cells: vec![10; (rows * cols) as usize],
            status: GameStatus::default(),
            metrics: None,
            player: settings.player.clone(),
            race: settings.race.clone(),
            country: config::country_code(&settings.country).unwrap_or_default(),
            last_position: None,
            last_input_at: Instant::now(),
            cursor_limit_used: false,
            timing_valid: true,
            started_clock_ms: None,
            last_clock_check: None,
            replay: None,
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
        if self.phase() == 1 {
            self.cursor_limit_used |= enabled;
        }
    }

    pub fn play(
        &mut self,
        button: u32,
        x: usize,
        y: usize,
        settings: &config::Settings,
        input_delay: Duration,
    ) {
        if self.ended() {
            return;
        }
        let now = Instant::now();
        let clock = crate::platform::clock_ms();
        let input_at = self.input_instant(now, input_delay);
        let clock = clock.and_then(|ms| ms.checked_sub((now - input_at).as_millis() as u64));
        let ready = self.status.phase == 0;
        if !self
            .session
            .button(button, x, y, settings.flag_win, &mut self.cells, input_at)
        {
            return;
        }
        self.last_position = Some((x, y));
        self.refresh();
        if ready && self.status.phase != 0 {
            self.cursor_limit_used = settings.cursor_lock;
            self.started_clock_ms = clock;
            self.last_clock_check = Some(now);
        }
        if self.ended() {
            self.check_clock(clock, now, true);
        }
    }

    fn input_instant(&mut self, now: Instant, delay: Duration) -> Instant {
        let input_at = now.checked_sub(delay).unwrap_or(self.last_input_at);
        self.last_input_at = input_at.max(self.last_input_at);
        self.last_input_at
    }

    pub fn track(&mut self, x: usize, y: usize, input_delay: Duration) {
        if !self.ended() && self.last_position != Some((x, y)) {
            let input_at = self.input_instant(Instant::now(), input_delay);
            self.session.track(x, y, input_at);
            self.last_position = Some((x, y));
        }
    }

    pub fn refresh(&mut self) {
        self.status = self.session.status();
        if self.status.phase == 1 {
            self.check_clock(crate::platform::clock_ms(), Instant::now(), false);
        }
        if self.ended() && self.metrics.is_none() {
            self.metrics = self.session.metrics();
        }
    }

    pub fn ended(&self) -> bool {
        self.status.phase >= 2
    }

    pub fn should_auto_restart(&self, threshold: i32) -> bool {
        if self.phase() != 3 || threshold <= 0 || !self.timing_valid {
            return false;
        }
        self.session.solved_below(threshold as usize)
    }

    pub fn seconds(&self) -> f64 {
        if self.phase() == 0 {
            0.0
        } else {
            self.status.seconds
        }
    }
    pub fn remaining(&self, mines: usize, flag_win: bool) -> u32 {
        if self.status.phase == 2 && flag_win {
            0
        } else {
            (mines as u32).saturating_sub(self.status.flags)
        }
    }
    pub fn phase(&self) -> u32 {
        self.status.phase
    }
    pub fn mouse_visual(&self) -> u32 {
        self.status.mouse_visual
    }

    fn check_clock(&mut self, clock: Option<u64>, now: Instant, terminal: bool) {
        let (Some(clock), Some(start), Some(last)) =
            (clock, self.started_clock_ms, self.last_clock_check)
        else {
            return;
        };
        if !self.timing_valid
            || (!terminal && now.saturating_duration_since(last) < Duration::from_secs(1))
        {
            return;
        }
        self.last_clock_check = Some(now);
        self.timing_valid = clock
            .checked_sub(start)
            .is_some_and(|elapsed| (self.status.seconds * 1000.0 - elapsed as f64).abs() <= 100.0);
    }

    pub fn replay(&mut self, settings: &config::Settings) -> Result<Replay, String> {
        if !self.ended() || !self.timing_valid {
            return Err("The game did not finish with a valid clock".into());
        }
        if let Some(replay) = &self.replay {
            return replay.clone();
        }
        let replay = self
            .build_replay(settings)
            .map_err(|error| error.to_string());
        self.replay = Some(replay.clone());
        replay
    }

    fn build_replay(&mut self, settings: &config::Settings) -> io::Result<Replay> {
        let (time, total, speed) = self.session.replay_stats();
        let name = format!(
            "{}_0_{}_{total}_{}_{}{}{}",
            ["b", "i", "e"][settings.level],
            decimal(time),
            decimal(speed),
            safe_identifier(&self.player),
            if self.status.phase == 3 { "_fail" } else { "" },
            if cfg!(mini_custom_replay_signer) {
                ""
            } else {
                "_fake"
            }
        );
        let mut data = self
            .encode_replay(settings)
            .ok_or_else(|| io::Error::other("EVF data unavailable"))?;
        sign(&mut data)?;
        Ok(Replay {
            name,
            data: data.into(),
        })
    }

    pub(crate) fn stats(
        &mut self,
        settings: &config::Settings,
        result: GameResult,
        replay: Option<&Replay>,
    ) -> Record {
        if matches!(result, GameResult::Restart) {
            self.session.abandon();
        }
        let unsigned;
        let data: &[u8] = match replay {
            Some(replay) => &replay.data,
            None => {
                unsigned = self.encode_replay(settings).unwrap_or_default();
                &unsigned
            }
        };
        self.session.stats(result, self.timing_valid, data)
    }

    fn encode_replay(&mut self, settings: &config::Settings) -> Option<Vec<u8>> {
        self.session.encode_replay(
            &self.player,
            &self.race,
            &self.country,
            self.cursor_limit_used,
            settings.auto_replay > 0,
        )
    }
}

pub fn decimal(v: f64) -> String {
    if v.is_nan() {
        "nan".into()
    } else if v == f64::INFINITY {
        "inf".into()
    } else if v == f64::NEG_INFINITY {
        "-inf".into()
    } else {
        format!("{v:.3}")
    }
}

fn safe_identifier(name: &str) -> String {
    crate::platform::filename_stem(name)
}

#[derive(Clone)]
pub struct Replay {
    pub name: String,
    pub data: Arc<[u8]>,
}

impl Replay {
    pub fn save(&self, dir: &Path, chosen: Option<&Path>) -> io::Result<PathBuf> {
        let actual_dir = chosen.and_then(Path::parent).unwrap_or(dir);
        fs::create_dir_all(actual_dir)?;
        static NEXT: AtomicU32 = AtomicU32::new(0);
        let temp = actual_dir.join(format!(
            ".mini-{}-{}.tmp",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        let mut file = OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(&temp)?;
        let result = file.write_all(&self.data);
        drop(file);
        let result = result.and_then(|_| {
            if let Some(path) = chosen {
                fs::rename(&temp, path).map(|()| path.to_owned())
            } else {
                for suffix in 1.. {
                    let filename = if suffix == 1 {
                        format!("{}.evf", self.name)
                    } else {
                        format!("{}({suffix}).evf", self.name)
                    };
                    let path = dir.join(filename);
                    match fs::hard_link(&temp, &path) {
                        Err(e) if e.kind() == io::ErrorKind::AlreadyExists => continue,
                        Err(e) if matches!(e.raw_os_error(), Some(1 | 38 | 95)) => {
                            // Some portable volumes do not support hard links.
                            let mut output =
                                match OpenOptions::new().create_new(true).write(true).open(&path) {
                                    Ok(file) => file,
                                    Err(e) if e.kind() == io::ErrorKind::AlreadyExists => continue,
                                    Err(e) => return Err(e),
                                };
                            let result = output.write_all(&self.data);
                            drop(output);
                            if result.is_err() {
                                let _ = fs::remove_file(&path);
                            }
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
    use crate::native::CELL_PIXELS;

    #[test]
    fn pregame_flags_update_the_mine_count_but_not_the_displayed_metrics() {
        let root = tempfile::tempdir().unwrap();
        let settings = config::Settings::read(root.path()).unwrap();
        let mut round = Round::new(&settings);
        round.session = GameSession::with_board(vec![vec![-1, 1, 0], vec![1, 1, 0], vec![0, 0, 0]]);
        round.cells.resize(9, 10);
        let initial = round.counter_rows("Standard");

        for button in [2, 3] {
            round.play(button, 3, 3, &settings, Duration::ZERO);
        }
        assert_eq!(round.cells[0], 11);
        assert_eq!(round.remaining(1, false), 0);
        assert_eq!(round.status.right, 1);
        assert_eq!(round.counter_rows("Standard"), initial);
        assert_eq!(round.seconds(), 0.0);

        for button in [0, 1] {
            round.play(button, CELL_PIXELS + 3, 3, &settings, Duration::ZERO);
        }
        assert_eq!(round.phase(), 1);
        assert!(round.counter_rows("Standard")[9].starts_with("1@"));
    }

    #[test]
    fn auto_restart_requires_loss_below_the_threshold() {
        let root =
            std::env::temp_dir().join(format!("metasweeper-mini-test-{}", std::process::id()));
        let settings = config::Settings::read(&root).unwrap();
        for (second_cell, lost) in [((3, 3), true), ((3, CELL_PIXELS + 3), false)] {
            let mut round = Round::new(&settings);
            round.session = GameSession::with_board(vec![vec![-1, 2], vec![2, -1]]);
            round.cells.resize(4, 10);

            round.play(0, CELL_PIXELS + 3, 3, &settings, Duration::ZERO);
            round.play(1, CELL_PIXELS + 3, 3, &settings, Duration::ZERO);
            assert!(!round.should_auto_restart(100));
            round.play(0, second_cell.0, second_cell.1, &settings, Duration::ZERO);
            round.play(1, second_cell.0, second_cell.1, &settings, Duration::ZERO);

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
        let root =
            std::env::temp_dir().join(format!("metasweeper-mini-test-{}", std::process::id()));
        let mut settings = config::Settings::read(&root).unwrap();
        settings.player = "[lag]player".into();
        let start = Instant::now();
        for (elapsed_ms, expected) in [(1100, true), (1101, false)] {
            let mut round = Round::new(&settings);
            round.started_clock_ms = Some(10_000);
            round.last_clock_check = Some(start);
            round.status.seconds = 1.0;
            round.check_clock(
                Some(10_000 + elapsed_ms),
                start + Duration::from_secs(1),
                false,
            );
            assert_eq!(round.timing_valid, expected);
        }
    }

    #[test]
    fn evf_records_lock_at_start_or_during_play() {
        let root =
            std::env::temp_dir().join(format!("metasweeper-mini-test-{}", std::process::id()));
        let mut settings = config::Settings::read(&root).unwrap();
        for (at_start, during_play, expected) in [
            (true, false, true),
            (false, true, true),
            (false, false, false),
        ] {
            let mut round = Round::new(&settings);
            round.session =
                GameSession::with_board(vec![vec![-1, 2, -1], vec![1, 2, 1], vec![0, 0, 0]]);
            round.cells.resize(9, 10);

            round.record_cursor_lock(true);
            settings.cursor_lock = at_start;
            round.play(
                0,
                CELL_PIXELS + 3,
                CELL_PIXELS + 3,
                &settings,
                Duration::ZERO,
            );
            round.play(
                1,
                CELL_PIXELS + 3,
                CELL_PIXELS + 3,
                &settings,
                Duration::ZERO,
            );
            assert_eq!(round.phase(), 1);
            round.record_cursor_lock(during_play);
            settings.cursor_lock = false;
            round.record_cursor_lock(false);
            round.play(0, 3, 3, &settings, Duration::ZERO);
            round.play(1, 3, 3, &settings, Duration::ZERO);
            assert_eq!(round.phase(), 3);
            round.record_cursor_lock(true);

            let replay = round.replay(&settings).unwrap();
            assert_eq!(
                replay.name.ends_with("_fake"),
                !cfg!(mini_custom_replay_signer)
            );
            assert_eq!(replay.data[2] & 0x40 != 0, expected);
        }
    }

    #[test]
    fn saving_again_reuses_the_finished_replay_after_settings_change() {
        let root = tempfile::tempdir().unwrap();
        let mut settings = config::Settings::read(root.path()).unwrap();
        settings.auto_replay = 30;
        let mut round = Round::new(&settings);
        round.session = GameSession::with_board(vec![vec![-1, 2], vec![2, -1]]);
        round.cells.resize(4, 10);

        for (x, y) in [(CELL_PIXELS + 3, 3), (3, CELL_PIXELS + 3)] {
            round.play(0, x, y, &settings, Duration::ZERO);
            round.play(1, x, y, &settings, Duration::ZERO);
        }
        assert_eq!(round.phase(), 2);
        let finished = round.replay(&settings).unwrap();
        assert_ne!(finished.data[2] & 0x20, 0);

        settings.auto_replay = -30;
        let manual = round.replay(&settings).unwrap();
        assert_eq!(finished.name, manual.name);
        assert_eq!(finished.data, manual.data);
    }

    #[test]
    #[cfg(not(mini_custom_replay_signer))]
    fn evf_signature_matches_windows_fixture() {
        let mut data = vec![4, 0, 0, 3, 3, 10, 16, 1, 2, 3, 4, 5, 0, 0, 0];
        sign(&mut data).unwrap();
        assert_eq!(&data[13..15], &[0, 32]);
        assert_eq!(
            data[15..]
                .iter()
                .map(|byte| format!("{byte:02x}"))
                .collect::<String>(),
            "8dc128859f3e18c0fec1c2e2b07b6e077f27dbb167a7a8a575be36fe45d4756f"
        );
    }
}

impl Round {
    pub fn counter_rows(&self, mode: &'static str) -> CounterRows {
        let mut rows = [const { Cow::Borrowed("--") }; COUNTER_ROWS];
        rows[0] = mode.into();
        if self.phase() == 0 {
            rows[1] = "0.000".into();
            rows[8..=10].fill(Cow::Borrowed("0@0.000"));
            rows[15] = "0.0".into();
            return rows;
        }
        let time = self.seconds();
        let rate = |count| {
            let per_second = if time > 0.0 { count as f64 / time } else { 0.0 };
            format!("{count}@{per_second:.3}")
        };
        rows[1] = decimal(time).into();
        rows[8] = rate(self.status.left).into();
        rows[9] = rate(self.status.right).into();
        rows[10] = rate(self.status.chords).into();
        rows[15] = format!("{:.1}", self.status.path).into();
        if let Some(m) = &self.metrics {
            let metric = |v: f64| {
                if v.is_nan() {
                    "--".into()
                } else if v == f64::INFINITY {
                    "∞".into()
                } else {
                    decimal(v).into()
                }
            };
            rows[2] = metric(m.estimated_time);
            rows[3] = format!("{}/{}", m.solved, m.total).into();
            rows[4] = metric(m.three_bv_per_second);
            rows[5] = format!("{}@{}", m.zini, metric(m.zini as f64 / m.estimated_time)).into();
            rows[6] = m.openings.to_string().into();
            rows[7] = m.islands.to_string().into();
            for (i, value) in [
                (11, m.stnb),
                (12, m.ioe),
                (13, m.thrp),
                (14, m.corr),
                (16, m.pluck),
            ] {
                rows[i] = metric(value);
            }
        }
        rows
    }
}
