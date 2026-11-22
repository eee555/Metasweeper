use crate::layout::Box2;
use fontdue::{Font, FontSettings};
use sdl3::{pixels::PixelFormat, surface::Surface, video::Window, EventPump};
use std::{cell::RefCell, path::PathBuf};

pub const CANVAS: u32 = 0xc0c0c0;
pub const INK: u32 = 0x000000;
pub const WHITE: u32 = 0xffffff;
pub const SHADE: u32 = 0xa0a0a0;

fn rgb(color: u32) -> (u8, u8, u8) {
    (((color >> 16) & 255) as u8, ((color >> 8) & 255) as u8, (color & 255) as u8)
}

struct Canvas<'a> {
    data: &'a mut [u8],
    width: i32,
    height: i32,
    stride: usize,
}

impl Canvas<'_> {
    fn blend(&mut self, x: i32, y: i32, r: u8, g: u8, b: u8, a: u8) {
        if a == 0 || x < 0 || y < 0 || x >= self.width || y >= self.height {
            return;
        }
        let o = y as usize * self.stride + x as usize * 4;
        if a == 255 {
            self.data[o] = b;
            self.data[o + 1] = g;
            self.data[o + 2] = r;
            self.data[o + 3] = 255;
            return;
        }
        let sa = a as u32;
        let ia = 255 - sa;
        let db = self.data[o] as u32;
        let dg = self.data[o + 1] as u32;
        let dr = self.data[o + 2] as u32;
        self.data[o] = ((b as u32 * sa + db * ia) / 255) as u8;
        self.data[o + 1] = ((g as u32 * sa + dg * ia) / 255) as u8;
        self.data[o + 2] = ((r as u32 * sa + dr * ia) / 255) as u8;
        self.data[o + 3] = 255;
    }

    fn fill(&mut self, area: Box2, color: u32) {
        if area.2 <= 0 || area.3 <= 0 {
            return;
        }
        let (r, g, b) = rgb(color);
        let x0 = area.0.max(0);
        let y0 = area.1.max(0);
        let x1 = (area.0 + area.2).min(self.width);
        let y1 = (area.1 + area.3).min(self.height);
        for y in y0..y1 {
            for x in x0..x1 {
                self.blend(x, y, r, g, b, 255);
            }
        }
    }

    fn blit(&mut self, image: &Image, x0: i32, y0: i32) {
        for y in 0..image.h {
            for x in 0..image.w {
                let p = image.px[(y * image.w + x) as usize];
                let a = (p >> 24) as u8;
                if a == 0 {
                    continue;
                }
                let r = ((p >> 16) & 255) as u8;
                let g = ((p >> 8) & 255) as u8;
                let b = (p & 255) as u8;
                self.blend(x0 + x, y0 + y, r, g, b, a);
            }
        }
    }
}

struct Image {
    w: i32,
    h: i32,
    px: Vec<u32>,
}

impl Image {
    fn new(w: i32, h: i32) -> Self {
        Self { w, h, px: vec![0; (w.max(0) * h.max(0)) as usize] }
    }

    fn over(&mut self, x: i32, y: i32, r: u8, g: u8, b: u8, coverage: u8) {
        if coverage == 0 || x < 0 || y < 0 || x >= self.w || y >= self.h {
            return;
        }
        let i = (y * self.w + x) as usize;
        let dst = self.px[i];
        let da = (dst >> 24) & 255;
        let sa = coverage as u32;
        if da == 0 {
            self.px[i] = (sa << 24) | ((r as u32) << 16) | ((g as u32) << 8) | b as u32;
            return;
        }
        let sc = 255 - sa;
        let outa = sa + da * sc / 255;
        if outa == 0 {
            return;
        }
        let dr = (dst >> 16) & 255;
        let dg = (dst >> 8) & 255;
        let db = dst & 255;
        let outr = (r as u32 * sa + dr * da * sc / 255) / outa;
        let outg = (g as u32 * sa + dg * da * sc / 255) / outa;
        let outb = (b as u32 * sa + db * da * sc / 255) / outa;
        self.px[i] = (outa.min(255) << 24) | (outr.min(255) << 16) | (outg.min(255) << 8) | outb.min(255);
    }
}

type Pt = (f64, f64);

fn add_interval(row: &mut [f32], bx: i32, w: i32, xa: f64, xb: f64) {
    if xb <= xa {
        return;
    }
    let start = (xa.floor() as i32).max(bx);
    let end = (xb.ceil() as i32).min(bx + w);
    for p in start..end {
        let l = xa.max(p as f64);
        let r = xb.min(p as f64 + 1.0);
        if r > l {
            row[(p - bx) as usize] += (r - l).min(1.0) as f32;
        }
    }
}

fn rasterize(polys: &[Vec<Pt>], bx: i32, by: i32, bw: i32, bh: i32, samples: i32) -> Vec<u8> {
    let (w, h) = (bw.max(0), bh.max(0));
    if w == 0 || h == 0 {
        return Vec::new();
    }
    let ss = samples.max(1);
    let mut acc = vec![0f32; (w * h) as usize];
    for sub in 0..(h * ss) {
        let y = by as f64 + (sub as f64 + 0.5) / ss as f64;
        let mut crossings: Vec<(f64, i32)> = Vec::new();
        for poly in polys {
            let n = poly.len();
            if n < 2 {
                continue;
            }
            for i in 0..n {
                let (x1, y1) = poly[i];
                let (x2, y2) = poly[(i + 1) % n];
                if (y1 <= y && y < y2) || (y2 <= y && y < y1) {
                    let t = (y - y1) / (y2 - y1);
                    crossings.push((x1 + (x2 - x1) * t, if y2 > y1 { 1 } else { -1 }));
                }
            }
        }
        if crossings.is_empty() {
            continue;
        }
        crossings.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));
        let mut rowover = vec![0f32; w as usize];
        let mut wind = 0i32;
        let mut start = 0f64;
        let mut inside = false;
        let mut k = 0;
        while k < crossings.len() {
            let x = crossings[k].0;
            let mut delta = 0;
            while k < crossings.len() && (crossings[k].0 - x).abs() < 1e-7 {
                delta += crossings[k].1;
                k += 1;
            }
            let prev = wind;
            wind += delta;
            if prev == 0 && wind != 0 {
                start = x;
                inside = true;
            } else if prev != 0 && wind == 0 && inside {
                add_interval(&mut rowover, bx, w, start, x);
                inside = false;
            }
        }
        let base = ((sub / ss) * w) as usize;
        for (i, v) in rowover.iter().enumerate() {
            acc[base + i] += *v;
        }
    }
    acc.iter().map(|v| (v / ss as f32 * 255.0).clamp(0.0, 255.0) as u8).collect()
}

fn cubic(p0: Pt, c1: Pt, c2: Pt, p1: Pt, t: f64) -> Pt {
    let u = 1.0 - t;
    let a = u * u * u;
    let b = 3.0 * u * u * t;
    let c = 3.0 * u * t * t;
    let d = t * t * t;
    (a * p0.0 + b * c1.0 + c * c2.0 + d * p1.0, a * p0.1 + b * c1.1 + c * c2.1 + d * p1.1)
}

fn flatten(commands: &[(u8, [f64; 6])]) -> Vec<Vec<Pt>> {
    let mut polys = Vec::new();
    let mut current: Vec<Pt> = Vec::new();
    let mut last = (0.0, 0.0);
    for &(op, v) in commands {
        match op {
            1 => {
                if current.len() > 1 {
                    polys.push(std::mem::take(&mut current));
                } else {
                    current.clear();
                }
                last = (v[0], v[1]);
                current.push(last);
            }
            2 => {
                last = (v[0], v[1]);
                current.push(last);
            }
            3 => {
                let p0 = last;
                let c1 = (v[0], v[1]);
                let c2 = (v[2], v[3]);
                let p1 = (v[4], v[5]);
                for s in 1..=16 {
                    current.push(cubic(p0, c1, c2, p1, s as f64 / 16.0));
                }
                last = p1;
            }
            4 => {
                if current.len() > 1 {
                    polys.push(std::mem::take(&mut current));
                } else {
                    current.clear();
                }
                let (x, y, w, h) = (v[0], v[1], v[2], v[3]);
                polys.push(vec![(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]);
            }
            5 => {
                if current.len() > 1 {
                    polys.push(std::mem::take(&mut current));
                } else {
                    current.clear();
                }
                let (x, y, w, h) = (v[0], v[1], v[2], v[3]);
                let (cx, cy, rx, ry) = (x + w / 2.0, y + h / 2.0, w / 2.0, h / 2.0);
                let mut ellipse = Vec::with_capacity(49);
                for k in 0..=48 {
                    let a = k as f64 / 48.0 * std::f64::consts::TAU;
                    ellipse.push((cx + rx * a.cos(), cy + ry * a.sin()));
                }
                polys.push(ellipse);
            }
            0 => {
                if current.len() > 1 {
                    if current.first() != current.last() {
                        let first = current[0];
                        current.push(first);
                    }
                    polys.push(std::mem::take(&mut current));
                } else {
                    current.clear();
                }
            }
            _ => {}
        }
    }
    if current.len() > 1 {
        polys.push(current);
    }
    polys
}

fn stroke_quads(paths: &[Vec<Pt>], width: f64) -> Vec<Vec<Pt>> {
    let half = width.max(0.5) / 2.0;
    let mut quads = Vec::new();
    for path in paths {
        for seg in path.windows(2) {
            let ((x1, y1), (x2, y2)) = (seg[0], seg[1]);
            let (dx, dy) = (x2 - x1, y2 - y1);
            let len = (dx * dx + dy * dy).sqrt();
            if len < 1e-6 {
                continue;
            }
            let (nx, ny) = (-dy / len * half, dx / len * half);
            quads.push(vec![(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]);
        }
    }
    quads
}

static ART: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/classic-shapes.bin"));
static DIGITS: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/led.bin"));
const OP_ARGS: [usize; 6] = [0, 2, 2, 6, 4, 4];

struct Reader<'a>(&'a [u8]);
impl Reader<'_> {
    fn bytes<const N: usize>(&mut self) -> [u8; N] {
        let (start, rest) = self.0.split_at(N);
        self.0 = rest;
        start.try_into().unwrap()
    }
    fn byte(&mut self) -> u8 {
        self.bytes::<1>()[0]
    }
    fn short(&mut self) -> i16 {
        i16::from_le_bytes(self.bytes())
    }
}

struct Shape {
    fill: u32,
    stroke: u32,
    width: f64,
    commands: Vec<(u8, [f64; 6])>,
}
struct Sprite {
    design: i32,
    shapes: Vec<Shape>,
}

fn render_sprite(sprite: &Sprite, size: i32) -> Image {
    let mut image = Image::new(size, size);
    if size <= 0 || sprite.design <= 0 {
        return image;
    }
    let scale = size as f64 / sprite.design as f64;
    for shape in &sprite.shapes {
        let paths: Vec<Vec<Pt>> = flatten(&shape.commands)
            .into_iter()
            .map(|path| path.iter().map(|&(x, y)| (x * scale, y * scale)).collect())
            .collect();
        if paths.is_empty() {
            continue;
        }
        if shape.fill != 0 {
            let coverage = rasterize(&paths, 0, 0, size, size, 4);
            let (r, g, b) = rgb(shape.fill);
            for (i, &c) in coverage.iter().enumerate() {
                if c > 0 {
                    image.over((i as i32) % size, (i as i32) / size, r, g, b, c);
                }
            }
        }
        if shape.stroke != 0 && shape.width > 0.0 {
            let quads = stroke_quads(&paths, shape.width * scale);
            if !quads.is_empty() {
                let coverage = rasterize(&quads, 0, 0, size, size, 4);
                let (r, g, b) = rgb(shape.stroke);
                for (i, &c) in coverage.iter().enumerate() {
                    if c > 0 {
                        image.over((i as i32) % size, (i as i32) / size, r, g, b, c);
                    }
                }
            }
        }
    }
    image
}

fn scale_edge(index: i32, length: i32, original: i32) -> i32 {
    (index * length + original / 2) / original
}

fn render_digit(digit: usize, width: i32, height: i32) -> Image {
    let mut image = Image::new(width, height);
    if width <= 0 || height <= 0 {
        return image;
    }
    for pixel in image.px.iter_mut() {
        *pixel = 0xff000000;
    }
    for row in 0..23 {
        let i = (digit * 23 + row) * 4;
        let pattern = u32::from_le_bytes(DIGITS[i..i + 4].try_into().unwrap());
        let top = scale_edge(row as i32, height, 23);
        let bottom = scale_edge(row as i32 + 1, height, 23);
        for col in 0..13 {
            let color = match (pattern >> (col * 2)) & 3 {
                1 => 0x800000,
                2 => 0xff0000,
                _ => continue,
            };
            let left = scale_edge(col as i32, width, 13);
            let right = scale_edge(col as i32 + 1, width, 13);
            for y in top..bottom {
                for x in left..right {
                    image.px[(y * width + x) as usize] = 0xff000000 | color;
                }
            }
        }
    }
    image
}

#[derive(Clone, Copy)]
pub enum Align {
    Left = 0,
    Center = 1,
    Right = 2,
}

struct Fonts {
    font: Option<Font>,
}

impl Fonts {
    fn new() -> Self {
        let font = find_font()
            .and_then(|path| std::fs::read(path).ok())
            .and_then(|bytes| Font::from_bytes(bytes, FontSettings { scale: 56.0, ..Default::default() }).ok());
        Self { font }
    }
}

fn find_font() -> Option<PathBuf> {
    #[cfg(windows)]
    const CANDIDATES: &[&str] = &[
        "C:\\Windows\\Fonts\\simhei.ttf",
        "C:\\Windows\\Fonts\\msyh.ttc",
        "C:\\Windows\\Fonts\\simsun.ttc",
        "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ];
    #[cfg(not(windows))]
    const CANDIDATES: &[&str] = &[
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ];
    CANDIDATES.iter().map(PathBuf::from).find(|path| path.exists())
}

fn measure_text(font: &Font, text: &str, px: f32) -> f32 {
    text.chars().map(|ch| font.metrics(ch, px).advance_width).sum()
}

fn draw_line(
    font: &Font,
    canvas: &mut Canvas,
    text: &str,
    px: f32,
    origin_x: f32,
    baseline: f32,
    color: (u8, u8, u8),
    clip: Box2,
) {
    let (cr, cg, cb) = color;
    let mut pen = 0f32;
    for ch in text.chars() {
        let (metrics, bitmap) = font.rasterize(ch, px);
        let gx = (origin_x + pen + metrics.xmin as f32).round() as i32;
        let gy = (baseline - (metrics.ymin as f32 + metrics.height as f32)).round() as i32;
        if metrics.width > 0 && metrics.height > 0 {
            for row in 0..metrics.height {
                let dy = gy + row as i32;
                if dy < clip.1 || dy >= clip.1 + clip.3 {
                    continue;
                }
                for col in 0..metrics.width {
                    let a = bitmap[row * metrics.width + col];
                    if a == 0 {
                        continue;
                    }
                    let dx = gx + col as i32;
                    if dx < clip.0 || dx >= clip.0 + clip.2 {
                        continue;
                    }
                    canvas.blend(dx, dy, cr, cg, cb, a);
                }
            }
        }
        pen += metrics.advance_width;
    }
}

fn wrap_lines(font: &Font, text: &str, px: f32, max_width: f32) -> Vec<String> {
    let mut lines = Vec::new();
    for raw in text.split('\n') {
        if raw.is_empty() {
            lines.push(String::new());
            continue;
        }
        let mut current = String::new();
        let mut width = 0.0;
        for ch in raw.chars() {
            let advance = font.metrics(ch, px).advance_width;
            if width + advance > max_width && !current.is_empty() {
                lines.push(std::mem::take(&mut current));
                width = 0.0;
            }
            current.push(ch);
            width += advance;
        }
        lines.push(current);
    }
    lines
}

pub struct Painter<'a> {
    canvas: RefCell<Canvas<'a>>,
    fonts: &'a Fonts,
}

impl<'a> Painter<'a> {
    fn new(canvas: Canvas<'a>, fonts: &'a Fonts) -> Self {
        Self { canvas: RefCell::new(canvas), fonts }
    }

    pub fn fill(&self, area: Box2, color: u32) {
        self.canvas.borrow_mut().fill(area, color);
    }

    fn polygon(&self, points: &[(i32, i32)], color: u32) {
        if points.len() < 3 {
            return;
        }
        let (mut min_x, mut max_x, mut min_y, mut max_y) = (i32::MAX, i32::MIN, i32::MAX, i32::MIN);
        for &(x, y) in points {
            min_x = min_x.min(x);
            max_x = max_x.max(x);
            min_y = min_y.min(y);
            max_y = max_y.max(y);
        }
        if max_x <= min_x || max_y <= min_y {
            return;
        }
        let poly: Vec<Pt> = points.iter().map(|&(x, y)| (x as f64, y as f64)).collect();
        let coverage = rasterize(&[poly], min_x, min_y, max_x - min_x, max_y - min_y, 2);
        let (r, g, b) = rgb(color);
        let mut canvas = self.canvas.borrow_mut();
        for y in 0..(max_y - min_y) {
            for x in 0..(max_x - min_x) {
                let a = coverage[(y * (max_x - min_x) + x) as usize];
                if a > 0 {
                    canvas.blend(min_x + x, min_y + y, r, g, b, a);
                }
            }
        }
    }

    pub fn bevel(&self, area: Box2, edge: i32, raised: bool) {
        if area.2 <= edge * 2 || area.3 <= edge * 2 {
            return;
        }
        let Box2(x, y, w, h) = area;
        let (right, bottom) = (x + w, y + h);
        let (top, low) = if raised { (WHITE, SHADE) } else { (SHADE, WHITE) };
        self.polygon(
            &[(x, y), (right, y), (right - edge, y + edge), (x + edge, y + edge), (x + edge, bottom - edge), (x, bottom)],
            top,
        );
        self.polygon(
            &[(right, bottom), (x, bottom), (x + edge, bottom - edge), (right - edge, bottom - edge), (right - edge, y + edge), (right, y)],
            low,
        );
    }

    pub fn border(&self, area: Box2, color: u32) {
        let Box2(x, y, w, h) = area;
        self.fill(Box2(x, y, w, 1), color);
        self.fill(Box2(x, y + h - 1, w, 1), color);
        self.fill(Box2(x, y, 1, h), color);
        self.fill(Box2(x + w - 1, y, 1, h), color);
    }

    fn blit(&self, image: &Image, x: i32, y: i32) {
        self.canvas.borrow_mut().blit(image, x, y);
    }

    pub fn measure(&self, text: &str, size: i32) -> i32 {
        let Some(font) = self.fonts.font.as_ref() else { return 0 };
        measure_text(font, text, size as f32).ceil() as i32
    }

    pub fn text(&self, area: Box2, text: &str, size: i32, align: Align, color: u32) {
        self.draw_text(area, text, size, align, color, false);
    }

    pub fn paragraph(&self, area: Box2, text: &str, size: i32, color: u32) {
        self.draw_text(area, text, size, Align::Left, color, true);
    }

    fn draw_text(&self, area: Box2, text: &str, size: i32, align: Align, color: u32, wrap: bool) {
        if area.2 <= 0 || area.3 <= 0 || text.is_empty() {
            return;
        }
        let Some(font) = self.fonts.font.as_ref() else { return };
        let px = size as f32;
        let line = font.horizontal_line_metrics(px);
        let ascent = line.map(|m| m.ascent).unwrap_or(px * 0.8);
        let line_height = line.map(|m| m.new_line_size).unwrap_or(px * 1.2);
        let (r, g, b) = rgb(color);
        let mut canvas = self.canvas.borrow_mut();
        if wrap {
            let lines = wrap_lines(font, text, px, area.2 as f32);
            let mut baseline = area.1 as f32 + ascent;
            for line in lines {
                if baseline - ascent >= (area.1 + area.3) as f32 {
                    break;
                }
                draw_line(font, &mut canvas, &line, px, area.0 as f32, baseline, (r, g, b), area);
                baseline += line_height;
            }
        } else {
            let width = measure_text(font, text, px);
            let origin = match align {
                Align::Left => area.0 as f32,
                Align::Center => area.0 as f32 + (area.2 as f32 - width) / 2.0,
                Align::Right => area.0 as f32 + area.2 as f32 - width,
            };
            let baseline = area.1 as f32 + (area.3 as f32 - line_height) / 2.0 + ascent;
            draw_line(font, &mut canvas, text, px, origin, baseline, (r, g, b), area);
        }
    }
}

pub struct Art {
    sprites: Vec<Sprite>,
    images: Vec<Option<(i32, Image)>>,
    digits: Vec<Option<((i32, i32), Image)>>,
}

impl Art {
    pub fn new() -> Self {
        let mut reader = Reader(ART);
        let count = reader.byte();
        let colors: Vec<u32> = (0..count).map(|_| u32::from_le_bytes(reader.bytes())).collect();
        let sprites = (0..22)
            .map(|_| {
                let design = reader.short() as i32;
                let shapes = (0..reader.byte())
                    .map(|_| {
                        let fill = colors[reader.byte() as usize];
                        let stroke = colors[reader.byte() as usize];
                        let width = reader.short() as f64 / 3.0;
                        let commands = (0..reader.byte())
                            .map(|_| {
                                let op = reader.byte();
                                let mut values = [0.0; 6];
                                for value in &mut values[..OP_ARGS[op as usize]] {
                                    *value = reader.short() as f64 / 3.0;
                                }
                                (op, values)
                            })
                            .collect();
                        Shape { fill, stroke, width, commands }
                    })
                    .collect();
                Sprite { design, shapes }
            })
            .collect();
        Self { sprites, images: (0..22).map(|_| None).collect(), digits: (0..10).map(|_| None).collect() }
    }

    pub fn sprite(&mut self, painter: &Painter, x: i32, y: i32, size: i32, id: usize) {
        if id >= self.sprites.len() || self.sprites[id].design == 0 {
            return;
        }
        if !self.images[id].as_ref().is_some_and(|(side, _)| *side == size) {
            let image = render_sprite(&self.sprites[id], size);
            self.images[id] = Some((size, image));
        }
        if let Some((_, image)) = &self.images[id] {
            painter.blit(image, x, y);
        }
    }

    pub fn number(&mut self, painter: &Painter, x: i32, y: i32, width: i32, height: i32, value: u32) {
        let value = value.min(999);
        for (pos, divisor) in [100, 10, 1].into_iter().enumerate() {
            let digit = (value / divisor % 10) as usize;
            if !self.digits[digit].as_ref().is_some_and(|((w, h), _)| *w == width && *h == height) {
                self.digits[digit] = Some(((width, height), render_digit(digit, width, height)));
            }
            if let Some((_, image)) = &self.digits[digit] {
                painter.blit(image, x + pos as i32 * width, y);
            }
        }
    }
}

pub struct Buffer {
    surface: Option<Surface<'static>>,
    fonts: Fonts,
}

impl Default for Buffer {
    fn default() -> Self {
        Self { surface: None, fonts: Fonts::new() }
    }
}

impl Buffer {
    pub fn present(
        &mut self,
        window: &Window,
        events: &EventPump,
        draw: impl FnOnce(&Painter, i32, i32),
    ) -> Result<(), String> {
        let mut screen = window.surface(events).map_err(|e| e.to_string())?;
        let (width, height) = (screen.width(), screen.height());
        if !self.surface.as_ref().is_some_and(|s| (s.width(), s.height()) == (width, height)) {
            self.surface = Some(Surface::new(width, height, PixelFormat::ARGB8888).map_err(|e| e.to_string())?);
        }
        let fonts = &self.fonts;
        let surface = self.surface.as_mut().unwrap();
        let pitch = surface.pitch() as usize;
        surface.with_lock_mut(|data| {
            let canvas = Canvas { data, width: width as i32, height: height as i32, stride: pitch };
            let painter = Painter::new(canvas, fonts);
            draw(&painter, width as i32, height as i32);
        });
        surface.blit(None, &mut screen, None).map_err(|e| e.to_string())?;
        screen.update_window().map_err(|e| e.to_string())
    }
}
