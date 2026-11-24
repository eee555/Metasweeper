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

    pub fn inset(self, edge: i32) -> Self {
        Self(self.0 + edge, self.1 + edge, self.2 - 2 * edge, self.3 - 2 * edge)
    }
}

#[derive(Clone, Copy)]
pub struct CounterLayout {
    pub heading: i32,
    pub title_px: i32,
    pub table_px: i32,
    pub columns: (i32, i32),
    row: i32,
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

    pub fn size(self) -> (i32, i32) {
        (34 + self.columns.0 + self.columns.1,
         self.table_top() + self.row * COUNTER_ROWS as i32 + 16 + self.table_px)
    }

    pub fn table_top(self) -> i32 { 14 + self.heading }

    pub fn title_line(self) -> i32 {
        let px = self.title_px;
        (px * 2080 + 1024) / 2048 + (px * 521 + 1024) / 2048
    }

    pub fn fit(pixels: i32, available: (i32, i32)) -> i32 {
        (COUNTER_MIN..=pixels).rev().find(|&scale| {
            let (width, height) = Self::new(scale).size();
            width <= available.0 && height <= available.1
        }).unwrap_or(COUNTER_MIN)
    }

    pub fn nearest(current: i32, proposed: (i32, i32), available: (i32, i32),
                   axes: (bool, bool)) -> i32 {
        let max = Self::fit(COUNTER_MAX, available);
        (COUNTER_MIN..=max).min_by_key(|&scale| {
            let (width, height) = Self::new(scale).size();
            let dx = if axes.0 { i64::from(width - proposed.0) } else { 0 };
            let dy = if axes.1 { i64::from(height - proposed.1) } else { 0 };
            (dx * dx + dy * dy, (current - scale).abs())
        }).unwrap_or(COUNTER_MIN)
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
}

impl Layout {
    pub fn new(tile: i32, reference: i32) -> Self {
        let bevel = |pixels| ((pixels * tile) as f64 / reference.max(1) as f64).round_ties_even().max(1.0) as i32;
        Self {
            tile, outer_edge: bevel(6), inner_edge: bevel(4),
            outer_inset: bevel(6) + 10, status_inset: bevel(4) + 5,
            sprite: tile * 3 / 2, digit: tile * 312 / 368,
        }
    }

    pub fn size(self, level: usize, footer: bool) -> (i32, i32) {
        let (rows, cols, _) = PRESETS[level];
        let width = (cols * self.tile + 2 * self.inner_edge).max(self.status_width());
        let height = rows * self.tile + 2 * self.inner_edge + self.status_height() + GAP;
        (width + 2 * self.outer_inset,
         MENU + height + 2 * self.outer_inset + if footer { FOOTER } else { 0 })
    }

    pub fn status_height(self) -> i32 {
        self.sprite + 2 * self.status_inset
    }

    fn status_width(self) -> i32 {
        6 * self.digit + self.sprite + 2 * self.status_inset + 16
    }

    pub fn status(self, width: i32) -> Box2 {
        Box2(self.outer_inset, MENU + self.outer_inset,
             width - 2 * self.outer_inset, self.status_height())
    }

    pub fn grid(self, level: usize, size: (i32, i32), footer: bool) -> Box2 {
        let (rows, cols, _) = PRESETS[level];
        let spare = (size.1 - self.size(level, footer).1).max(0) / 2;
        Box2((size.0 - cols * self.tile) / 2,
             MENU + self.outer_inset + self.status_height() + GAP + self.inner_edge + spare,
             cols * self.tile, rows * self.tile)
    }

    pub fn board_size(self, level: usize) -> (i32, i32) {
        let (rows, cols, _) = PRESETS[level];
        (cols * self.tile, rows * self.tile)
    }

    pub fn fullscreen_size(self, level: usize, show_status: bool) -> (i32, i32) {
        let (width, height) = self.board_size(level);
        let grid_width = width + 2 * self.inner_edge;
        let grid_height = height + 2 * self.inner_edge;
        let (width, height) = if show_status {
            (grid_width.max(self.status_width()), grid_height + self.status_height() + GAP)
        } else {
            (grid_width, grid_height)
        };
        (width + 2 * self.outer_inset, height + 2 * self.outer_inset)
    }

    pub fn fullscreen_regions(self, level: usize, size: (i32, i32), show_status: bool) -> FullscreenRegions {
        let (width, height) = self.board_size(level);
        let (frame_width, frame_height) = self.fullscreen_size(level, show_status);
        let frame = Box2((size.0 - frame_width) / 2, (size.1 - frame_height) / 2, frame_width, frame_height);
        let inside = frame.inset(self.outer_inset);
        let grid = Box2(inside.0 + (inside.2 - width) / 2,
                        inside.1 + inside.3 - self.inner_edge - height, width, height);
        let status = show_status.then(|| Box2(inside.0, inside.1, inside.2, self.status_height()));
        FullscreenRegions { frame, grid, status }
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
    fn counter_uses_qt_geometry_and_snaps_dragged_edges() {
        let size = CounterLayout::new(27).size();
        let larger = CounterLayout::new(33).size();
        assert_eq!(size, (272, 532));
        assert_eq!(larger, (325, 644));
        assert_eq!(CounterLayout::nearest(27, (larger.0, size.1), larger, (true, false)), 33);
        assert_eq!(CounterLayout::nearest(27, (size.0, larger.1), larger, (false, true)), 33);
        assert_eq!(CounterLayout::fit(255, larger), 33);
    }

    #[test]
    fn matches_winforms_pixels() {
        for (tile, reference, expected) in [
            (20, 20, (200, 324)), (30, 30, (280, 419)), (50, 50, (440, 609)),
            (70, 50, (608, 811)), (20, 50, (188, 308)),
        ] {
            let layout = Layout::new(tile, reference);
            assert_eq!(layout.size(0, true), expected);
            assert_eq!(Layout::fit(reference, 0, true, expected).tile, tile);
            assert_eq!(layout.size(0, false).1, expected.1 - 41);
        }
    }

    #[test]
    fn fullscreen_keeps_the_frame_and_cell_size_in_both_modes() {
        for tile in [5, 20, 50] {
            let layout = Layout::new(tile, 20);
            for level in 0..PRESETS.len() {
                let (width, height) = layout.board_size(level);
                let border = layout.outer_inset + layout.inner_edge;
                let size = layout.fullscreen_size(level, false);
                let regions = layout.fullscreen_regions(level, size, false);
                assert_eq!(regions.grid, Box2(border, border, width, height));
                assert_eq!(regions.frame.inset(border), regions.grid);
                assert_eq!(regions.status, None);

                let size = layout.fullscreen_size(level, true);
                let regions = layout.fullscreen_regions(level, (size.0 + 12, size.1 + 8), true);
                assert_eq!(regions.frame, Box2(6, 4, size.0, size.1));
                assert_eq!(regions.grid.2, width);
                assert_eq!(regions.grid.3, height);
                let status = regions.status.unwrap();
                assert_eq!(status.1 + status.3 + GAP + layout.inner_edge, regions.grid.1);
                assert_eq!(regions.frame.1 + regions.frame.3 - border, regions.grid.1 + height);
            }
        }
    }

}
