use ms_toollib::videos::base_video::NewBaseVideo2;
use ms_toollib::{laymine, BaseVideo, GameBoardState, MouseState};

const CELL_PIXELS: usize = 16;

pub struct GameSession {
    video: BaseVideo<Vec<Vec<i32>>>,
    laid: bool,
}

#[repr(C)]
pub struct GameStatus {
    seconds: f64,
    path: f64,
    phase: u32,
    left: u32,
    right: u32,
    chords: u32,
    flags: u32,
    mouse_visual: u32,
}

#[no_mangle]
pub extern "C" fn new_game(rows: usize, columns: usize, mines: usize) -> *mut GameSession {
    let mut video =
        BaseVideo::<Vec<Vec<i32>>>::new(vec![vec![0; columns]; rows], CELL_PIXELS as u8);
    video.mine_num = mines;
    video.set_live_pluck_enabled(true);
    Box::into_raw(Box::new(GameSession { video, laid: false }))
}

#[no_mangle]
pub unsafe extern "C" fn free_game(game: *mut GameSession) {
    drop(Box::from_raw(game));
}

#[no_mangle]
pub extern "C" fn game_status(game: &GameSession, status: &mut GameStatus) {
    let video = &game.video;
    *status = GameStatus {
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
    };
}

#[no_mangle]
pub unsafe extern "C" fn game_button(
    game: &mut GameSession,
    button: u32,
    x: usize,
    y: usize,
    flag_on_win: u32,
    cells: *mut u8,
) -> u32 {
    let video = &mut game.video;
    let pos = (y, x);
    let (row, col) = (y / CELL_PIXELS, x / CELL_PIXELS);
    if finished(video) {
        return 0;
    }
    let event = match button {
        0 => "lc",
        1 => "lr",
        2 => "rc",
        3 => "rr",
        _ => return 0,
    };
    if !game.laid
        && button == 1
        && row < video.height
        && col < video.width
        && video.minesweeper_board.mouse_state == MouseState::DownUp
        && video.minesweeper_board.game_board[row][col] == 10
    {
        let board = laymine(video.height, video.width, video.mine_num, row, col);
        if video.set_board(board).is_err() {
            return 0;
        }
        game.laid = true;
    }
    if video.step(event, pos).is_err() {
        return 0;
    }
    match video.game_board_state {
        GameBoardState::Win if flag_on_win != 0 => video.win_then_flag_all_mine(),
        GameBoardState::Loss => video.loss_then_open_all_mine(),
        _ => {}
    }
    let cells = std::slice::from_raw_parts_mut(cells, video.height * video.width);
    for (target, value) in cells
        .iter_mut()
        .zip(video.minesweeper_board.game_board.iter().flatten())
    {
        *target = *value as u8;
    }
    1
}

#[no_mangle]
pub extern "C" fn game_move(game: &mut GameSession, x: usize, y: usize) {
    let _ = game.video.step("mv", (y, x));
}

fn finished(video: &BaseVideo<Vec<Vec<i32>>>) -> bool {
    matches!(
        video.game_board_state,
        GameBoardState::Win | GameBoardState::Loss
    )
}

#[no_mangle]
pub unsafe extern "C" fn encode_replay(
    game: &mut GameSession,
    identifiers: *const u8,
    identifiers_length: usize,
    used_cursor_limit: u32,
    length: &mut usize,
) -> *mut u8 {
    let video = &mut game.video;
    if !finished(video) || video.video_action_state_recorder.is_empty() {
        return std::ptr::null_mut();
    }
    let Ok(identifiers) =
        std::str::from_utf8(std::slice::from_raw_parts(identifiers, identifiers_length))
    else {
        return std::ptr::null_mut();
    };
    let mut identifiers = identifiers.splitn(3, '\0');
    let (Some(player), Some(race), Some(country)) =
        (identifiers.next(), identifiers.next(), identifiers.next())
    else {
        return std::ptr::null_mut();
    };
    video.player_identifier = player.to_owned();
    video.race_identifier = race.to_owned();
    video.country = country.to_owned();
    video.software = "元3.3.4-迷你版".to_owned();
    video.translated = false;
    video.use_cursor_pos_lim = used_cursor_limit != 0;
    video.generate_evf_v4_raw_data();

    let bytes = std::mem::take(&mut video.raw_data).into_boxed_slice();
    *length = bytes.len();
    Box::into_raw(bytes) as *mut u8
}

#[no_mangle]
pub unsafe extern "C" fn free_replay(bytes: *mut u8, length: usize) {
    drop(Box::from_raw(std::ptr::slice_from_raw_parts_mut(
        bytes, length,
    )));
}

#[repr(C)]
#[cfg_attr(test, derive(Default))]
pub struct ReplayMetrics {
    estimated_time: f64,
    three_bv_per_second: f64,
    stnb: f64,
    ioe: f64,
    thrp: f64,
    corr: f64,
    pluck: f64,
    solved: u32,
    total: u32,
    zini: u32,
    openings: u32,
    islands: u32,
}

#[no_mangle]
pub extern "C" fn game_metrics(game: &GameSession, metrics: &mut ReplayMetrics) -> u32 {
    let video = &game.video;
    if !finished(video) {
        return 0;
    }

    let pluck = match video.live_pluck_snapshot().ready() {
        Ok(Some(value)) => value,
        Ok(None) => return 0,
        Err(_) => f64::NAN,
    };
    *metrics = ReplayMetrics {
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
    };
    1
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn background_pluck_keeps_the_successful_prefix_after_loss() {
        let layout = vec![vec![-1, 2, -1], vec![1, 2, 1], vec![0, 0, 0]];
        let mut game = GameSession {
            video: BaseVideo::<Vec<Vec<i32>>>::new(layout, CELL_PIXELS as u8),
            laid: true,
        };
        game.video.set_live_pluck_enabled(true);
        let mut visible = [10; 9];
        let mut open = |game: &mut GameSession, x, y| unsafe {
            assert_eq!(
                game_button(
                    game,
                    0,
                    x * CELL_PIXELS + 3,
                    y * CELL_PIXELS + 3,
                    1,
                    visible.as_mut_ptr()
                ),
                1
            );
            game_button(
                game,
                1,
                x * CELL_PIXELS + 3,
                y * CELL_PIXELS + 3,
                1,
                visible.as_mut_ptr(),
            )
        };

        assert_eq!(open(&mut game, 1, 1), 1);
        assert_eq!(open(&mut game, 1, 0), 1);
        let pluck = -0.75_f64.log10();
        let during_play = game.video.live_pluck_snapshot().wait().unwrap();
        assert!((during_play - pluck).abs() < 1e-12);

        assert_eq!(open(&mut game, 0, 0), 1);
        assert_eq!(game.video.game_board_state, GameBoardState::Loss);
        let mut metrics = ReplayMetrics::default();
        assert_eq!(game_metrics(&game, &mut metrics), 1);
        assert!((metrics.pluck - pluck).abs() < 1e-12);
        assert_eq!(visible[0], 15);
        assert_eq!(visible[2], 16);
    }
}
