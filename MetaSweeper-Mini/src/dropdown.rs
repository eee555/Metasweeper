use crate::{
    layout::Box2,
    paint::{Align, Painter, INK, WHITE},
};

const ITEM_HEIGHT: i32 = 25;
const VISIBLE_ITEMS: usize = 6;
pub const ARROW_WIDTH: i32 = 25;

pub struct Dropdown {
    choices: Vec<&'static str>,
    first: usize,
    selected: Option<usize>,
}

impl Dropdown {
    pub fn new(choices: Vec<&'static str>, selected: Option<usize>) -> Option<Self> {
        if choices.is_empty() {
            return None;
        }
        let selected = selected.filter(|&index| index < choices.len());
        let first = selected.map_or(0, |index| (index + 1).saturating_sub(VISIBLE_ITEMS));
        Some(Self {
            choices,
            first,
            selected,
        })
    }

    fn rect(&self, Box2(x, y, width, height): Box2) -> Box2 {
        Box2(
            x,
            y + height,
            width,
            self.choices.len().min(VISIBLE_ITEMS) as i32 * ITEM_HEIGHT,
        )
    }

    pub fn item_at(&self, anchor: Box2, (x, y): (i32, i32)) -> Option<usize> {
        let rect = self.rect(anchor);
        if !rect.contains(x, y) {
            return None;
        }
        let index = self.first + ((y - rect.1) / ITEM_HEIGHT) as usize;
        (index < self.choices.len()).then_some(index)
    }

    pub fn selected(&self) -> Option<usize> {
        self.selected
    }

    pub fn first_visible(&self) -> usize {
        self.first
    }

    pub fn label(&self, index: usize) -> &'static str {
        self.choices[index]
    }

    pub fn step(&mut self, step: i32) {
        let last = self.choices.len() - 1;
        let index = match self.selected {
            Some(index) => index.saturating_add_signed(step as isize).min(last),
            None if step < 0 => self.first.saturating_sub(1),
            None => self.first,
        };
        self.selected = Some(index);
        self.first = self
            .first
            .min(index)
            .max((index + 1).saturating_sub(VISIBLE_ITEMS));
    }

    pub fn scroll(&mut self, direction: i32) {
        self.first = self
            .first
            .saturating_add_signed(direction as isize)
            .min(self.choices.len().saturating_sub(VISIBLE_ITEMS));
        self.selected = None;
    }

    pub fn draw(
        &self,
        painter: &Painter,
        anchor: Box2,
        font: i32,
        hovered: Option<usize>,
        is_current: impl Fn(usize, &str) -> bool,
    ) {
        let rect = self.rect(anchor);
        for (offset, &choice) in self.choices[self.first..]
            .iter()
            .take(VISIBLE_ITEMS)
            .enumerate()
        {
            let index = self.first + offset;
            let row = Box2(
                rect.0,
                rect.1 + offset as i32 * ITEM_HEIGHT,
                rect.2,
                ITEM_HEIGHT,
            );
            painter.fill(
                row,
                if self.selected == Some(index) {
                    0xd5e9ff
                } else if hovered == Some(index) {
                    0xe4eef8
                } else {
                    WHITE
                },
            );
            if is_current(index, choice) {
                painter.fill(Box2(row.0 + 2, row.1 + 4, 2, row.3 - 8), 0x467eac);
            }
            let label = Box2(row.0 + 7, row.1, row.2 - 14, row.3);
            painter.text(label, choice, font, Align::Left, INK);
        }
        painter.border(rect, 0x467eac);
    }
}

pub fn trigger_area(anchor: Box2, editable: bool) -> Box2 {
    if editable {
        Box2(
            anchor.0 + anchor.2 - ARROW_WIDTH,
            anchor.1,
            ARROW_WIDTH,
            anchor.3,
        )
    } else {
        anchor
    }
}

pub fn draw_trigger(painter: &Painter, anchor: Box2, editable: bool, open: bool, hovered: bool) {
    if open || hovered {
        painter.fill(
            trigger_area(anchor, editable).inset(1),
            if open { 0xd5e5f4 } else { 0xe4eef8 },
        );
    }
    if open {
        painter.border(anchor, 0x467eac);
    }
    let arrow_x = anchor.0 + anchor.2 - (ARROW_WIDTH + 1) / 2;
    let arrow_y = anchor.1 + (anchor.3 - 4) / 2;
    for (step, width) in [9, 7, 5, 3, 1].into_iter().enumerate() {
        painter.fill(
            Box2(arrow_x - width / 2, arrow_y + step as i32, width, 1),
            INK,
        );
    }
}
