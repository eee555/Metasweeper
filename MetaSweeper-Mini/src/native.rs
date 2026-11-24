use ms_toollib::videos::base_video::NewBaseVideo2;
use ms_toollib::{laymine, BaseVideo, GameBoardState, MouseState};
use std::time::Instant;

pub const CELL_PIXELS: usize = 16;

pub struct GameSession {
    video: BaseVideo<Vec<Vec<i32>>>,
    laid: bool,
}

#[derive(Default)]
pub struct GameStatus {
    pub seconds: f64,
    pub path: f64,
    pub phase: u32,
    pub left: u32,
    pub right: u32,
    pub chords: u32,
    pub flags: u32,
    pub mouse_visual: u32,
}

pub struct ReplayMetrics {
    pub estimated_time: f64,
    pub three_bv_per_second: f64,
    pub stnb: f64,
    pub ioe: f64,
    pub thrp: f64,
    pub corr: f64,
    pub pluck: f64,
    pub solved: u32,
    pub total: u32,
    pub zini: u32,
    pub openings: u32,
    pub islands: u32,
}

impl GameSession {
    pub fn new(rows: usize, columns: usize, mines: usize) -> Self {
        let mut video =
            BaseVideo::<Vec<Vec<i32>>>::new(vec![vec![0; columns]; rows], CELL_PIXELS as u8);
        video.mine_num = mines;
        video.set_live_pluck_enabled(true);
        Self { video, laid: false }
    }

    #[cfg(test)]
    pub fn with_board(board: Vec<Vec<i32>>) -> Self {
        Self {
            video: BaseVideo::<Vec<Vec<i32>>>::new(board, CELL_PIXELS as u8),
            laid: true,
        }
    }

    pub fn status(&self) -> GameStatus {
        let video = &self.video;
        GameStatus {
            seconds: video.get_time().max(0.0),
            path: video.get_path(),
            phase: match video.game_board_state {
                GameBoardState::Playing => 1,
                GameBoardState::Win => 2,
                GameBoardState::Loss => 3,
                _ => 0,
            },
            left: video.get_left() as u32,
            right: video.get_right() as u32,
            chords: video.get_double() as u32,
            flags: video.get_flag() as u32,
            mouse_visual: match video.minesweeper_board.mouse_state {
                MouseState::DownUp => 1,
                MouseState::Chording | MouseState::ChordingNotFlag => 2,
                _ => 0,
            },
        }
    }

    pub fn button(
        &mut self,
        button: u32,
        x: usize,
        y: usize,
        flag_on_win: bool,
        cells: &mut [u8],
        input_at: Instant,
    ) -> bool {
        if self.finished() || cells.len() != self.video.height * self.video.width {
            return false;
        }
        let video = &mut self.video;
        let (row, col) = (y / CELL_PIXELS, x / CELL_PIXELS);
        let event = match button {
            0 => "lc",
            1 => "lr",
            2 => "rc",
            3 => "rr",
            _ => return false,
        };
        if !self.laid
            && button == 1
            && row < video.height
            && col < video.width
            && video.minesweeper_board.mouse_state == MouseState::DownUp
            && video.minesweeper_board.game_board[row][col] == 10
        {
            let board = laymine(video.height, video.width, video.mine_num, row, col);
            if video.set_board(board).is_err() {
                return false;
            }
            self.laid = true;
        }
        if video.step_at(event, (y, x), input_at).is_err() {
            return false;
        }
        match video.game_board_state {
            GameBoardState::Win if flag_on_win => video.win_then_flag_all_mine(),
            GameBoardState::Loss => video.loss_then_open_all_mine(),
            _ => {}
        }
        for (target, value) in cells
            .iter_mut()
            .zip(video.minesweeper_board.game_board.iter().flatten())
        {
            *target = *value as u8;
        }
        true
    }

    pub fn track(&mut self, x: usize, y: usize, input_at: Instant) {
        let _ = self.video.step_at("mv", (y, x), input_at);
    }

    fn finished(&self) -> bool {
        matches!(
            self.video.game_board_state,
            GameBoardState::Win | GameBoardState::Loss
        )
    }

    pub fn solved_below(&self, threshold: usize) -> bool {
        let total = self.video.static_params.bbbv;
        total != 0
            && self
                .video
                .get_bbbv_solved()
                .is_ok_and(|solved| solved * 100 < total * threshold)
    }

    pub fn replay_stats(&self) -> (f64, usize, f64) {
        (
            self.video.get_time(),
            self.video.static_params.bbbv,
            self.video.get_bbbv_s().unwrap_or(f64::NAN),
        )
    }

    pub fn encode_replay(
        &mut self,
        player: &str,
        race: &str,
        country: &str,
        used_cursor_limit: bool,
        auto_replay_enabled: bool,
    ) -> Option<Vec<u8>> {
        if !self.finished() || self.video.video_action_state_recorder.is_empty() {
            return None;
        }
        let video = &mut self.video;
        video.player_identifier = player.to_owned();
        video.race_identifier = race.to_owned();
        video.country = country.to_owned();
        video.software = format!(
            "迷你元{}-{}",
            env!("CARGO_PKG_VERSION"),
            std::env::consts::OS
        );
        video.translated = false;
        video.is_fair = true;
        video.is_official = video.is_completed && video.mode == 0;
        video.use_question = false;
        video.use_cursor_pos_lim = used_cursor_limit;
        video.use_auto_replay = auto_replay_enabled;
        video.generate_evf_v4_raw_data();
        Some(std::mem::take(&mut video.raw_data))
    }

    pub fn metrics(&self) -> Option<ReplayMetrics> {
        if !self.finished() {
            return None;
        }
        let video = &self.video;
        let pluck = match video.live_pluck_snapshot().ready() {
            Ok(Some(value)) => value,
            Ok(None) => return None,
            Err(_) => f64::NAN,
        };
        Some(ReplayMetrics {
            estimated_time: video.get_etime().unwrap_or(f64::NAN),
            three_bv_per_second: video.get_bbbv_s().unwrap_or(f64::NAN),
            stnb: video.get_stnb().unwrap_or(f64::NAN),
            ioe: video.get_ioe().unwrap_or(f64::NAN),
            thrp: video.get_thrp().unwrap_or(f64::NAN),
            corr: video.get_corr().unwrap_or(f64::NAN),
            pluck,
            solved: video.get_bbbv_solved().unwrap_or_default() as u32,
            total: video.static_params.bbbv as u32,
            zini: video.static_params.zini as u32,
            openings: video.static_params.op as u32,
            islands: video.static_params.isl as u32,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ms_toollib::{videos::NewSomeVideo2, EvfVideo};

    #[test]
    fn button_rejects_mismatched_cell_buffers_before_processing_input() {
        let mut game = GameSession::with_board(vec![vec![-1, 1], vec![1, 1]]);
        assert!(!game.button(0, 17, 17, true, &mut [10; 3], Instant::now()));
        assert!(!game.button(0, 17, 17, true, &mut [10; 5], Instant::now()));
        assert_eq!(game.status().mouse_visual, 0);
        assert!(game.button(0, 17, 17, true, &mut [10; 4], Instant::now()));
        assert_eq!(game.status().mouse_visual, 1);
    }

    #[test]
    fn background_pluck_keeps_the_successful_prefix_after_loss() {
        let layout = vec![vec![-1, 2, -1], vec![1, 2, 1], vec![0, 0, 0]];
        let mut game = GameSession::with_board(layout);
        game.video.set_live_pluck_enabled(true);
        let mut visible = [10; 9];
        let mut open = |game: &mut GameSession, x, y| {
            let x = x * CELL_PIXELS + 3;
            let y = y * CELL_PIXELS + 3;
            assert!(game.button(0, x, y, true, &mut visible, Instant::now()));
            assert!(game.button(1, x, y, true, &mut visible, Instant::now()));
        };

        open(&mut game, 1, 1);
        open(&mut game, 1, 0);
        let pluck = -0.75_f64.log10();
        let during_play = game.video.live_pluck_snapshot().wait().unwrap();
        assert!((during_play - pluck).abs() < 1e-12);

        open(&mut game, 0, 0);
        assert_eq!(game.video.game_board_state, GameBoardState::Loss);
        assert!((game.metrics().unwrap().pluck - pluck).abs() < 1e-12);
        assert_eq!(visible[0], 15);
        assert_eq!(visible[2], 16);
    }

    #[test]
    fn replay_records_the_build_identity_and_result_flags() {
        for (moves, won, auto_replay) in [
            (&[(17, 17), (1, 1)][..], false, false),
            (&[(17, 17), (1, 1)][..], false, true),
            (&[(17, 17), (1, 17), (17, 1)][..], true, false),
            (&[(17, 17), (1, 17), (17, 1)][..], true, true),
        ] {
            let mut game = GameSession::with_board(vec![vec![-1, 1], vec![1, 1]]);
            for &position in moves {
                game.video.step("lc", position).unwrap();
                game.video.step("lr", position).unwrap();
            }
            let replay = game
                .encode_replay("玩家", "赛事", "CN", false, auto_replay)
                .unwrap();
            let mut parsed = EvfVideo::new(replay, "flags.evf");
            parsed.parse().unwrap();
            let version = env!("CARGO_PKG_VERSION");
            let os = std::env::consts::OS;
            assert_eq!(parsed.data.software, format!("迷你元{version}-{os}"));
            assert_eq!(parsed.data.player_identifier, "玩家");
            assert_eq!(parsed.data.race_identifier, "赛事");
            assert_eq!(parsed.data.country, "CN");
            assert!(parsed.data.is_fair);
            assert_eq!(parsed.data.is_completed, won);
            assert_eq!(parsed.data.is_official, won);
            assert!(!parsed.data.use_question);
            assert_eq!(parsed.data.use_auto_replay, auto_replay);
        }
    }

    #[test]
    fn replay_uses_input_timestamps_for_a_buffered_round() {
        use std::time::Duration;

        let mut game = GameSession::with_board(vec![vec![-1, 1], vec![1, 1]]);
        let now = Instant::now();
        let start = now - Duration::from_millis(480);
        let end = start + Duration::from_millis(417);
        game.video.video_start_instant = start;
        let mut cells = [10; 4];
        for (x, y, time) in [(17, 17, start), (3, 3, end)] {
            assert!(game.button(0, x, y, true, &mut cells, time));
            assert!(game.button(1, x, y, true, &mut cells, time));
        }
        assert_eq!(game.status().phase, 3);
        assert_eq!(game.replay_stats().0, 0.417);
        let data = game.encode_replay("玩家", "", "", false, false).unwrap();
        let mut parsed = EvfVideo::new(data, "timing.evf");
        parsed.parse().unwrap();
        assert_eq!(parsed.data.get_rtime().unwrap(), 0.417);
        assert!(
            parsed
                .data
                .end_time
                .abs_diff(parsed.data.start_time + 417_000)
                < 5_000
        );
    }
}
