pub const MENU: i32 = 27;
pub const FOOTER: i32 = 41;
pub const GAP: i32 = 8;
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
        let width = (cols * self.tile + 2 * self.inner_edge)
            .max(6 * self.digit + self.sprite + 2 * self.status_inset + 16);
        let height = rows * self.tile + 2 * self.inner_edge + self.status_height() + GAP;
        (width + 2 * self.outer_inset,
         MENU + height + 2 * self.outer_inset + if footer { FOOTER } else { 0 })
    }

    pub fn status_height(self) -> i32 {
        self.sprite + 2 * self.status_inset
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

}
