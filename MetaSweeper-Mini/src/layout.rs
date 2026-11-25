pub const MENU: i32 = 27;
pub const FOOTER: i32 = 41;
pub const GAP: i32 = 8;
pub const COUNTER_ROWS: usize = 17;
pub const COUNTER_MIN: i32 = 5;
pub const COUNTER_MAX: i32 = 255;
pub const PRESETS: [(i32, i32, usize); 3] = [(8, 8, 10), (16, 16, 40), (16, 30, 99)];
pub const SECTIONS: [&str; 3] = ["BEGINNER", "INTERMEDIATE", "EXPERT"];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Box2(pub i32, pub i32, pub i32, pub i32);

impl Box2 {
    pub fn contains(self, x: i32, y: i32) -> bool {
        x >= self.0 && x < self.0 + self.2 && y >= self.1 && y < self.1 + self.3
    }

    pub fn cell_at(self, (x, y): (i32, i32), tile: i32) -> Option<(i32, i32)> {
        self.contains(x, y)
            .then(|| ((x - self.0) / tile, (y - self.1) / tile))
    }

    pub fn inset(self, edge: i32) -> Self {
        Self(
            self.0 + edge,
            self.1 + edge,
            self.2 - 2 * edge,
            self.3 - 2 * edge,
        )
    }
}

#[derive(Clone, Copy)]
pub struct CounterLayout {
    pub heading: i32,
    pub title_px: i32,
    pub table_px: i32,
    pub columns: (i32, i32),
    pub row: i32,
}

impl CounterLayout {
    pub fn new(pixels: i32) -> Self {
        let scaled = |base: i32| (base * pixels / 26).max(base * 10 / 12);
        let to_pixels = |points| (points * 4 + 1) / 3;
        let table_px = scaled(15);
        let line_px = to_pixels(table_px);
        let ascent = (line_px * 2080 + 1024) / 2048;
        let descent = (line_px * 521 + 1024) / 2048;
        Self {
            heading: scaled(27),
            title_px: to_pixels(scaled(12)),
            table_px,
            columns: (scaled(80), scaled(150)),
            row: (ascent + descent + 2).max(23),
        }
    }

    pub fn size(self, rows: usize) -> (i32, i32) {
        (
            34 + self.columns.0 + self.columns.1,
            self.table_top() + self.row * rows as i32 + 16 + self.table_px,
        )
    }

    pub fn table_top(self) -> i32 {
        14 + self.heading
    }

    pub fn title_line(self) -> i32 {
        let px = self.title_px;
        (px * 2080 + 1024) / 2048 + (px * 521 + 1024) / 2048
    }

    pub fn fit(pixels: i32, available: (i32, i32), rows: usize) -> i32 {
        (COUNTER_MIN..=pixels)
            .rev()
            .find(|&scale| {
                let (width, height) = Self::new(scale).size(rows);
                width <= available.0 && height <= available.1
            })
            .unwrap_or(COUNTER_MIN)
    }

    pub fn nearest(
        current: i32,
        proposed: (i32, i32),
        available: (i32, i32),
        axes: (bool, bool),
        rows: usize,
    ) -> i32 {
        let max = Self::fit(COUNTER_MAX, available, rows);
        (COUNTER_MIN..=max)
            .min_by_key(|&scale| {
                let (width, height) = Self::new(scale).size(rows);
                let dx = if axes.0 {
                    i64::from(width - proposed.0)
                } else {
                    0
                };
                let dy = if axes.1 {
                    i64::from(height - proposed.1)
                } else {
                    0
                };
                (dx * dx + dy * dy, (current - scale).abs())
            })
            .unwrap_or(COUNTER_MIN)
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub struct Layout {
    pub tile: i32,
    pub outer_edge: i32,
    pub inner_edge: i32,
    pub outer_inset: i32,
    pub status_inset: i32,
    pub sprite: i32,
    pub digit: i32,
}

pub struct FullscreenRegions {
    pub frame: Box2,
    pub grid: Box2,
    pub status: Option<Box2>,
    pub counter: Option<Box2>,
    pub counter_scale: i32,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FullscreenMode {
    Board,
    Status,
    Counter,
}

impl Layout {
    pub fn new(tile: i32, reference: i32) -> Self {
        let bevel = |pixels| {
            ((pixels * tile) as f64 / reference.max(1) as f64)
                .round_ties_even()
                .max(1.0) as i32
        };
        Self {
            tile,
            outer_edge: bevel(6),
            inner_edge: bevel(4),
            outer_inset: bevel(6) + 10,
            status_inset: bevel(4) + 5,
            sprite: tile * 3 / 2,
            digit: tile * 312 / 368,
        }
    }

    pub fn size(self, level: usize, footer: bool) -> (i32, i32) {
        let (rows, cols, _) = PRESETS[level];
        let width = (cols * self.tile + 2 * self.inner_edge).max(self.status_width());
        let height = rows * self.tile + 2 * self.inner_edge + self.status_height() + GAP;
        (
            width + 2 * self.outer_inset,
            MENU + height + 2 * self.outer_inset + if footer { FOOTER } else { 0 },
        )
    }

    pub fn status_height(self) -> i32 {
        self.sprite + 2 * self.status_inset
    }

    fn status_width(self) -> i32 {
        6 * self.digit + self.sprite + 2 * self.status_inset + 16
    }

    pub fn status(self, width: i32) -> Box2 {
        Box2(
            self.outer_inset,
            MENU + self.outer_inset,
            width - 2 * self.outer_inset,
            self.status_height(),
        )
    }

    pub fn status_face(self, status: Box2) -> Box2 {
        Box2(
            status.0 + (status.2 - self.sprite) / 2,
            status.1 + self.status_inset,
            self.sprite,
            self.sprite,
        )
    }

    pub fn status_timer(self, status: Box2) -> Box2 {
        let width = 3 * self.digit;
        Box2(
            status.0 + status.2 - self.status_inset - width,
            status.1 + self.status_inset,
            width,
            self.sprite,
        )
    }

    pub fn grid(self, level: usize, size: (i32, i32), footer: bool) -> Box2 {
        let (rows, cols, _) = PRESETS[level];
        let spare = (size.1 - self.size(level, footer).1).max(0) / 2;
        Box2(
            (size.0 - cols * self.tile) / 2,
            MENU + self.outer_inset + self.status_height() + GAP + self.inner_edge + spare,
            cols * self.tile,
            rows * self.tile,
        )
    }

    pub fn board_size(self, level: usize) -> (i32, i32) {
        let (rows, cols, _) = PRESETS[level];
        (cols * self.tile, rows * self.tile)
    }

    pub fn fullscreen_size(
        self,
        level: usize,
        mode: FullscreenMode,
        rows: usize,
    ) -> (i32, i32, i32) {
        let (width, height) = self.board_size(level);
        let grid_width = width + 2 * self.inner_edge;
        let grid_height = height + 2 * self.inner_edge;
        let (width, height, counter_scale) = match mode {
            FullscreenMode::Board => (grid_width, grid_height, 0),
            FullscreenMode::Status => (
                grid_width.max(self.status_width()),
                grid_height + self.status_height() + GAP,
                0,
            ),
            FullscreenMode::Counter => {
                let counter_scale = CounterLayout::fit(COUNTER_MAX, (i32::MAX, grid_height), rows);
                let counter_size = CounterLayout::new(counter_scale).size(rows);
                (
                    grid_width + counter_size.0,
                    grid_height.max(counter_size.1),
                    counter_scale,
                )
            }
        };
        (
            width + 2 * self.outer_inset,
            height + 2 * self.outer_inset,
            counter_scale,
        )
    }

    pub fn fullscreen_regions(
        self,
        level: usize,
        size: (i32, i32),
        mode: FullscreenMode,
        rows: usize,
    ) -> FullscreenRegions {
        let (width, height) = self.board_size(level);
        let (frame_width, frame_height, counter_scale) = self.fullscreen_size(level, mode, rows);
        let frame = Box2(
            (size.0 - frame_width) / 2,
            (size.1 - frame_height) / 2,
            frame_width,
            frame_height,
        );
        let inside = frame.inset(self.outer_inset);
        let grid_x = if mode == FullscreenMode::Counter {
            inside.0 + inside.2 - width
        } else {
            inside.0 + (inside.2 - width) / 2
        };
        let grid = Box2(
            grid_x,
            if mode == FullscreenMode::Counter {
                inside.1 + (inside.3 - height) / 2
            } else {
                inside.1 + inside.3 - self.inner_edge - height
            },
            width,
            height,
        );
        let status = (mode == FullscreenMode::Status)
            .then(|| Box2(inside.0, inside.1, inside.2, self.status_height()));
        let counter = (mode == FullscreenMode::Counter).then(|| {
            let (width, height) = CounterLayout::new(counter_scale).size(rows);
            Box2(inside.0, inside.1 + (inside.3 - height) / 2, width, height)
        });
        FullscreenRegions {
            frame,
            grid,
            status,
            counter,
            counter_scale,
        }
    }

    pub fn fit(reference: i32, level: usize, footer: bool, available: (i32, i32)) -> Self {
        let mut low = 5;
        let mut high = 255;
        while low < high {
            let mid = (low + high + 1) / 2;
            let (w, h) = Self::new(mid, reference).size(level, footer);
            if w <= available.0 && h <= available.1 {
                low = mid;
            } else {
                high = mid - 1;
            }
        }
        Self::new(low, reference)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn board_preview_cell_changes_at_cell_and_board_edges() {
        let grid = Box2(7, 13, 40, 40);
        assert_eq!(grid.cell_at((7, 13), 20), Some((0, 0)));
        assert_eq!(grid.cell_at((26, 32), 20), Some((0, 0)));
        assert_eq!(grid.cell_at((27, 33), 20), Some((1, 1)));
        assert_eq!(grid.cell_at((47, 33), 20), None);
        assert_eq!(grid.cell_at((7, 12), 20), None);
    }

    #[test]
    fn counter_uses_qt_geometry_and_snaps_dragged_edges() {
        let size = CounterLayout::new(27).size(COUNTER_ROWS);
        let larger = CounterLayout::new(33).size(COUNTER_ROWS);
        assert_eq!(size, (272, 532));
        assert_eq!(larger, (325, 644));
        assert_eq!(
            CounterLayout::nearest(27, (larger.0, size.1), larger, (true, false), COUNTER_ROWS),
            33
        );
        assert_eq!(
            CounterLayout::nearest(27, (size.0, larger.1), larger, (false, true), COUNTER_ROWS),
            33
        );
        assert_eq!(CounterLayout::fit(255, larger, COUNTER_ROWS), 33);
    }

    #[test]
    fn configured_row_count_scales_counter_and_fullscreen_counter() {
        assert_eq!(CounterLayout::new(27).size(COUNTER_ROWS), (272, 532));
        assert!(CounterLayout::new(27).size(24).1 > CounterLayout::new(27).size(COUNTER_ROWS).1);
        assert!(CounterLayout::new(27).size(8).1 < CounterLayout::new(27).size(COUNTER_ROWS).1);
        let layout = Layout::new(20, 20);
        for rows in [8, COUNTER_ROWS, 24] {
            let (width, height, scale) = layout.fullscreen_size(0, FullscreenMode::Counter, rows);
            let (counter_width, counter_height) = CounterLayout::new(scale).size(rows);
            let regions = layout.fullscreen_regions(
                0,
                (width + 40, height + 40),
                FullscreenMode::Counter,
                rows,
            );
            let counter = regions.counter.unwrap();
            assert_eq!((counter.2, counter.3), (counter_width, counter_height));
        }
    }

    #[test]
    fn matches_winforms_pixels() {
        for (tile, reference, expected) in [
            (20, 20, (200, 324)),
            (30, 30, (280, 419)),
            (50, 50, (440, 609)),
            (70, 50, (608, 811)),
            (20, 50, (188, 308)),
        ] {
            let layout = Layout::new(tile, reference);
            assert_eq!(layout.size(0, true), expected);
            assert_eq!(Layout::fit(reference, 0, true, expected).tile, tile);
            assert_eq!(layout.size(0, false).1, expected.1 - 41);
        }
    }

    #[test]
    fn fullscreen_keeps_the_frame_and_cell_size_in_all_modes() {
        for tile in [5, 20, 50] {
            let layout = Layout::new(tile, 20);
            for level in 0..PRESETS.len() {
                let (width, height) = layout.board_size(level);
                let border = layout.outer_inset + layout.inner_edge;
                let (frame_width, frame_height, _) =
                    layout.fullscreen_size(level, FullscreenMode::Board, COUNTER_ROWS);
                let regions = layout.fullscreen_regions(
                    level,
                    (frame_width, frame_height),
                    FullscreenMode::Board,
                    COUNTER_ROWS,
                );
                let inside = regions.frame.inset(layout.outer_inset);
                assert_eq!(
                    regions.grid,
                    Box2(
                        inside.0 + (inside.2 - width) / 2,
                        inside.1 + inside.3 - layout.inner_edge - height,
                        width,
                        height
                    )
                );
                assert_eq!(regions.status, None);

                let (frame_width, frame_height, _) =
                    layout.fullscreen_size(level, FullscreenMode::Status, COUNTER_ROWS);
                let (board_width, board_height) = layout.board_size(level);
                let regions = layout.fullscreen_regions(
                    level,
                    (frame_width + 12, frame_height + 8),
                    FullscreenMode::Status,
                    COUNTER_ROWS,
                );
                assert_eq!(regions.frame, Box2(6, 4, frame_width, frame_height));
                assert_eq!(regions.grid.2, board_width);
                assert_eq!(regions.grid.3, board_height);
                let status = regions.status.unwrap();
                assert_eq!(
                    status.1 + status.3 + GAP + layout.inner_edge,
                    regions.grid.1
                );
                assert_eq!(
                    regions.frame.1 + regions.frame.3 - border,
                    regions.grid.1 + board_height
                );

                let (frame_width, frame_height, counter_scale) =
                    layout.fullscreen_size(level, FullscreenMode::Counter, COUNTER_ROWS);
                let regions = layout.fullscreen_regions(
                    level,
                    (frame_width, frame_height),
                    FullscreenMode::Counter,
                    COUNTER_ROWS,
                );
                assert_eq!(regions.counter_scale, counter_scale);
                let counter = regions.counter.unwrap();
                let counter_size = CounterLayout::new(counter_scale).size(COUNTER_ROWS);
                let inside = regions.frame.inset(layout.outer_inset);
                assert_eq!(
                    counter,
                    Box2(
                        inside.0,
                        inside.1 + (inside.3 - counter_size.1) / 2,
                        counter_size.0,
                        counter_size.1
                    )
                );
                assert_eq!(
                    regions.grid,
                    Box2(
                        inside.0 + inside.2 - board_width,
                        inside.1 + (inside.3 - board_height) / 2,
                        board_width,
                        board_height
                    )
                );
                assert!(
                    counter.1 + counter.3 <= regions.frame.1 + regions.frame.3 - layout.outer_inset
                );
                assert!(counter.1 >= inside.1);
                assert_eq!(
                    inside.3,
                    counter_size.1.max(board_height + 2 * layout.inner_edge)
                );
            }
        }
    }
}
