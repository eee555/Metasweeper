use crate::{
    core::{CounterRows, Round},
    layout::COUNTER_ROWS,
};
use std::{borrow::Cow, fs, io, path::Path};

const MAX_FORMULA_BYTES: usize = 512;
const MAX_ROWS: usize = 24;

#[derive(Default)]
pub struct CounterConfig {
    rows: Vec<MetricRow>,
}

struct MetricRow {
    label: String,
    formula: Option<Formula>,
}

impl CounterConfig {
    pub fn read(root: &Path) -> io::Result<Self> {
        let path = root.join("scoreBoardSetting.ini");
        let source = match fs::read_to_string(&path) {
            Ok(source) => source,
            Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(Self::default()),
            Err(error) => return Err(error),
        };
        Self::parse(&source)
    }

    fn parse(source: &str) -> io::Result<Self> {
        let mut rows = Vec::new();
        let mut in_default = false;
        let mut entry: Option<(&str, String, usize)> = None;
        let mut save = |entry: Option<(&str, String, usize)>| -> io::Result<()> {
            if let Some((label, expression, _)) = entry {
                if rows.len() == MAX_ROWS {
                    return Err(io::Error::new(
                        io::ErrorKind::InvalidData,
                        "scoreBoardSetting.ini supports up to 24 metrics",
                    ));
                }
                rows.push(MetricRow {
                    label: label.into(),
                    formula: Formula::parse(&expression),
                });
            }
            Ok(())
        };
        for raw in source.trim_start_matches('\u{feff}').lines() {
            let line = raw.trim();
            if line.is_empty() || line.starts_with(['#', ';']) {
                continue;
            }
            let indent = raw.len() - raw.trim_start().len();
            if let Some((_, expression, base_indent)) = &mut entry {
                if indent > *base_indent {
                    expression.push('\n');
                    expression.push_str(line);
                    continue;
                }
            }
            save(entry.take())?;
            if line.starts_with('[') && line.ends_with(']') {
                in_default = line == "[DEFAULT]";
            } else if in_default {
                if let Some((name, expression)) = line.split_once(['=', ':']) {
                    entry = Some((name.trim(), expression.trim().into(), indent));
                }
            }
        }
        save(entry)?;
        Ok(Self { rows })
    }

    pub fn len(&self) -> usize {
        if self.rows.is_empty() {
            COUNTER_ROWS
        } else {
            self.rows.len()
        }
    }

    pub fn label(&self, index: usize) -> Option<&str> {
        self.rows.get(index).map(|row| row.label.as_str())
    }

    pub fn values(
        &self,
        round: &Round,
        mode: &'static str,
        unsupported: &'static str,
    ) -> CounterRows {
        if self.rows.is_empty() {
            return round.counter_rows(mode);
        }
        self.rows
            .iter()
            .map(|row| match &row.formula {
                None => unsupported.into(),
                Some(formula) if formula.needs_result && round.metrics.is_none() => "--".into(),
                Some(formula) => formula
                    .eval(&|name| round.counter_variable(name, mode))
                    .map_or(Cow::Borrowed("error"), Cow::Owned),
            })
            .collect()
    }
}

pub enum Value<'a> {
    Number(f64, bool),
    Bool(bool),
    Text(Cow<'a, str>),
}

impl<'a> Value<'a> {
    pub fn count(value: u32) -> Self {
        Self::Number(f64::from(value), true)
    }

    pub fn number(value: f64) -> Self {
        Self::Number(value, false)
    }

    fn numeric(&self) -> Option<(f64, bool)> {
        match self {
            Self::Number(value, integral) => Some((*value, *integral)),
            Self::Bool(value) => Some((f64::from(*value), true)),
            Self::Text(_) => None,
        }
    }

    fn truthy(&self) -> bool {
        match self {
            Self::Text(value) => !value.is_empty(),
            _ => self.numeric().is_some_and(|(value, _)| value != 0.0),
        }
    }

    fn display(&self) -> String {
        match self {
            Self::Number(value, _) if value.is_nan() => "nan".into(),
            Self::Number(value, true) if *value == 0.0 => "0".into(),
            Self::Number(value, true) => format!("{value:.0}"),
            Self::Number(value, false) => format!("{value:?}"),
            Self::Bool(true) => "True".into(),
            Self::Bool(false) => "False".into(),
            Self::Text(text) => text.to_string(),
        }
    }
}

struct Formula {
    parts: Vec<Part>,
    needs_result: bool,
}

enum Part {
    Literal(String),
    Expression(Expr, Format),
}

enum Format {
    Default,
    Integer,
    Fixed(usize),
    Text,
}

impl Formula {
    fn parse(source: &str) -> Option<Self> {
        if source.len() > MAX_FORMULA_BYTES {
            return None;
        }
        let mut needs_result = false;
        let mut expression = |source, format| {
            let mut parser = Parser {
                rest: source,
                needs_result: false,
            };
            let expr = parser.expression(0)?;
            needs_result |= parser.needs_result;
            parser
                .rest
                .trim()
                .is_empty()
                .then_some(Part::Expression(expr, format))
        };
        let mut parts = Vec::new();
        if let Some(body) = source
            .strip_prefix("f'")
            .and_then(|s| s.strip_suffix('\''))
            .or_else(|| source.strip_prefix("f\"").and_then(|s| s.strip_suffix('"')))
        {
            if body.contains(['\\', '\n']) {
                return None;
            }
            let mut literal = String::new();
            let mut rest = body;
            while let Some((offset, brace)) =
                rest.char_indices().find(|(_, ch)| matches!(ch, '{' | '}'))
            {
                literal.push_str(&rest[..offset]);
                rest = &rest[offset + 1..];
                if let Some(escaped) = rest.strip_prefix(brace) {
                    literal.push(brace);
                    rest = escaped;
                    continue;
                }
                if brace != '{' {
                    return None;
                }
                if !literal.is_empty() {
                    parts.push(Part::Literal(std::mem::take(&mut literal)));
                }
                let (field, tail) = rest.split_once('}')?;
                let (source, spec) = field.split_once(':').unwrap_or((field, ""));
                let format = match spec {
                    "" => Format::Default,
                    "s" => Format::Text,
                    "d" => Format::Integer,
                    spec => {
                        let digits = spec.strip_prefix('.')?.strip_suffix('f')?.parse().ok()?;
                        if digits > 12 {
                            return None;
                        }
                        Format::Fixed(digits)
                    }
                };
                parts.push(expression(source, format)?);
                rest = tail;
            }
            literal.push_str(rest);
            if !literal.is_empty() {
                parts.push(Part::Literal(literal));
            }
        } else {
            parts.push(expression(source, Format::Default)?);
        }
        Some(Self {
            parts,
            needs_result,
        })
    }

    fn eval<'a>(&'a self, variable: &impl Fn(&str) -> Option<Value<'a>>) -> Option<String> {
        let mut output = String::new();
        for part in &self.parts {
            match part {
                Part::Literal(text) => output.push_str(text),
                Part::Expression(expr, format) => {
                    let value = expr.eval(variable)?;
                    let text = match format {
                        Format::Default => value.display(),
                        Format::Text => match value {
                            Value::Text(text) => text.into_owned(),
                            _ => return None,
                        },
                        Format::Integer => {
                            let (number, integral) = value.numeric()?;
                            if !integral {
                                return None;
                            }
                            if number == 0.0 {
                                "0".into()
                            } else {
                                format!("{number:.0}")
                            }
                        }
                        Format::Fixed(digits) => {
                            let (number, _) = value.numeric()?;
                            if number.is_finite() {
                                format!("{number:.digits$}")
                            } else {
                                value.display()
                            }
                        }
                    };
                    output.push_str(&text);
                }
            }
        }
        Some(output)
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Op {
    Or,
    And,
    Eq,
    Ne,
    Lt,
    Le,
    Gt,
    Ge,
    Add,
    Sub,
    Mul,
    Div,
    FloorDiv,
    Rem,
    Pow,
}

impl Op {
    fn comparison(self) -> bool {
        matches!(
            self,
            Self::Eq | Self::Ne | Self::Lt | Self::Le | Self::Gt | Self::Ge
        )
    }

    fn calculate<'a>(self, left: Value<'a>, right: Value<'a>) -> Option<Value<'a>> {
        use Op::*;
        if matches!(self, Or | And) {
            return Some(right);
        }
        if self.comparison() {
            let order = match (&left, &right) {
                (Value::Text(left), Value::Text(right)) => Some(left.cmp(right)),
                _ => {
                    let (left, _) = left.numeric()?;
                    let (right, _) = right.numeric()?;
                    left.partial_cmp(&right)
                }
            };
            let result = match self {
                Eq => order.is_some_and(|order| order.is_eq()),
                Ne => order.is_none_or(|order| !order.is_eq()),
                Lt => order.is_some_and(|order| order.is_lt()),
                Le => order.is_some_and(|order| order.is_le()),
                Gt => order.is_some_and(|order| order.is_gt()),
                Ge => order.is_some_and(|order| order.is_ge()),
                _ => unreachable!(),
            };
            return Some(Value::Bool(result));
        }
        let (left, left_int) = left.numeric()?;
        let (right, right_int) = right.numeric()?;
        if right == 0.0 && matches!(self, Div | FloorDiv | Rem) {
            return None;
        }
        let integer = left_int && right_int;
        let (value, integral) = match self {
            Add => (left + right, integer),
            Sub => (left - right, integer),
            Mul => (left * right, integer),
            Div => (left / right, false),
            FloorDiv | Rem => {
                let mut remainder = left % right;
                let mut quotient = (left - remainder) / right;
                if remainder == 0.0 {
                    remainder = 0.0_f64.copysign(right);
                } else if remainder.is_sign_negative() != right.is_sign_negative() {
                    remainder += right;
                    quotient -= 1.0;
                }
                let value = if self == Rem {
                    remainder
                } else if quotient == 0.0 {
                    0.0_f64.copysign(left / right)
                } else {
                    quotient.round()
                };
                (value, integer)
            }
            Pow if left != 0.0 || right >= 0.0 => {
                let value = left.powf(right);
                if value.is_nan() || value.is_infinite() {
                    return None;
                }
                (value, integer && right >= 0.0)
            }
            Pow => return None,
            _ => unreachable!(),
        };
        Some(Value::Number(value, integral))
    }
}

enum Expr {
    Number(f64, bool),
    Text(String),
    Bool(bool),
    Variable(String),
    Signed(bool, Box<Expr>),
    Not(Box<Expr>),
    Binary(Op, Box<Expr>, Box<Expr>),
    Conditional(Box<Expr>, Box<Expr>, Box<Expr>),
    Call(Function, Vec<Expr>),
}

impl Expr {
    fn eval<'a>(&'a self, variable: &impl Fn(&str) -> Option<Value<'a>>) -> Option<Value<'a>> {
        Some(match self {
            Self::Number(value, integer) => Value::Number(*value, *integer),
            Self::Text(text) => Value::Text(text.as_str().into()),
            Self::Bool(value) => Value::Bool(*value),
            Self::Variable(name) => return variable(name),
            Self::Signed(negative, expr) => {
                let (value, integer) = expr.eval(variable)?.numeric()?;
                Value::Number(if *negative { -value } else { value }, integer)
            }
            Self::Not(expr) => Value::Bool(!expr.eval(variable)?.truthy()),
            Self::Binary(op, left, right) => {
                let left = left.eval(variable)?;
                if (*op == Op::Or && left.truthy()) || (*op == Op::And && !left.truthy()) {
                    left
                } else {
                    op.calculate(left, right.eval(variable)?)?
                }
            }
            Self::Conditional(condition, yes, no) => {
                return if condition.eval(variable)?.truthy() {
                    yes
                } else {
                    no
                }
                .eval(variable);
            }
            Self::Call(function, args) => return function.eval(args, variable),
        })
    }
}

enum Function {
    Abs,
    Min,
    Max,
    Round,
    Int,
    Float,
    Bool,
    Sin,
    Cos,
    Tan,
    Log,
    Pow,
}

impl Function {
    fn parse(name: &str, count: usize) -> Option<Self> {
        Some(match (name, count) {
            ("abs", 1) => Self::Abs,
            ("min", 2..) => Self::Min,
            ("max", 2..) => Self::Max,
            ("round", 1 | 2) => Self::Round,
            ("int", 1) => Self::Int,
            ("float", 1) => Self::Float,
            ("bool", 1) => Self::Bool,
            ("sin", 1) => Self::Sin,
            ("cos", 1) => Self::Cos,
            ("tan", 1) => Self::Tan,
            ("log", 1 | 2) => Self::Log,
            ("pow", 2) => Self::Pow,
            _ => return None,
        })
    }

    fn eval<'a>(
        &self,
        args: &'a [Expr],
        variable: &impl Fn(&str) -> Option<Value<'a>>,
    ) -> Option<Value<'a>> {
        let first = args.first()?.eval(variable)?;
        if matches!(self, Self::Bool) {
            return Some(Value::Bool(first.truthy()));
        }
        let (number, integral) = first.numeric()?;
        let second = || args.get(1)?.eval(variable)?.numeric();
        Some(match self {
            Self::Abs => Value::Number(number.abs(), integral),
            Self::Min | Self::Max => {
                let mut result = first;
                for arg in &args[1..] {
                    let candidate = arg.eval(variable)?;
                    let (value, _) = candidate.numeric()?;
                    let (current, _) = result.numeric()?;
                    if (matches!(self, Self::Min) && value < current)
                        || (matches!(self, Self::Max) && value > current)
                    {
                        result = candidate;
                    }
                }
                result
            }
            Self::Round if args.len() == 2 => {
                let (digits, integer) = second()?;
                if !integer || !(-12.0..=12.0).contains(&digits) {
                    return None;
                }
                let rounded = if digits >= 0.0 {
                    let digits = digits as usize;
                    format!("{number:.digits$}").parse().ok()?
                } else {
                    let factor = 10.0_f64.powi(-digits as i32);
                    (number / factor).round_ties_even() * factor
                };
                Value::Number(rounded, integral)
            }
            Self::Round if number.is_finite() => Value::Number(number.round_ties_even(), true),
            Self::Int if number.is_finite() => Value::Number(number.trunc(), true),
            Self::Float => Value::number(number),
            Self::Sin if number.is_finite() => Value::number(number.sin()),
            Self::Cos if number.is_finite() => Value::number(number.cos()),
            Self::Tan if number.is_finite() => Value::number(number.tan()),
            Self::Log if number > 0.0 && args.len() == 1 => Value::number(number.ln()),
            Self::Log if number > 0.0 => {
                let (base, _) = second()?;
                if base <= 0.0 || base == 1.0 {
                    return None;
                }
                Value::number(number.log(base))
            }
            Self::Pow => return Op::Pow.calculate(first, args[1].eval(variable)?),
            _ => return None,
        })
    }
}

struct Parser<'a> {
    rest: &'a str,
    needs_result: bool,
}

fn identifier(byte: u8) -> bool {
    byte.is_ascii_alphanumeric() || byte == b'_'
}

impl<'a> Parser<'a> {
    fn take(&mut self, text: &str) -> bool {
        self.rest = self.rest.trim_start();
        if let Some(tail) = self.rest.strip_prefix(text) {
            if text.as_bytes()[0].is_ascii_alphabetic()
                && tail.bytes().next().is_some_and(identifier)
            {
                return false;
            }
            self.rest = tail;
            true
        } else {
            false
        }
    }

    fn expression(&mut self, minimum: u8) -> Option<Expr> {
        let mut left = self.prefix()?;
        let mut compared = false;
        loop {
            let before = self.rest;
            let candidate = [
                ("or", Op::Or, 1),
                ("and", Op::And, 2),
                ("==", Op::Eq, 3),
                ("!=", Op::Ne, 3),
                ("<=", Op::Le, 3),
                (">=", Op::Ge, 3),
                ("<", Op::Lt, 3),
                (">", Op::Gt, 3),
                ("+", Op::Add, 4),
                ("-", Op::Sub, 4),
                ("**", Op::Pow, 7),
                ("//", Op::FloorDiv, 5),
                ("*", Op::Mul, 5),
                ("/", Op::Div, 5),
                ("%", Op::Rem, 5),
            ]
            .into_iter()
            .find(|(token, _, _)| self.take(token));
            let Some((_, op, precedence)) = candidate else {
                break;
            };
            if precedence < minimum {
                self.rest = before;
                break;
            }
            if op.comparison() {
                if compared {
                    return None;
                }
                compared = true;
            }
            let right = self.expression(precedence + u8::from(op != Op::Pow))?;
            left = Expr::Binary(op, Box::new(left), Box::new(right));
        }
        if minimum == 0 && self.take("if") {
            let condition = self.expression(1)?;
            if !self.take("else") {
                return None;
            }
            return Some(Expr::Conditional(
                Box::new(condition),
                Box::new(left),
                Box::new(self.expression(0)?),
            ));
        }
        Some(left)
    }

    fn prefix(&mut self) -> Option<Expr> {
        if self.take("+") {
            return Some(Expr::Signed(false, Box::new(self.expression(6)?)));
        }
        if self.take("-") {
            return Some(Expr::Signed(true, Box::new(self.expression(6)?)));
        }
        if self.take("not") {
            return Some(Expr::Not(Box::new(self.expression(3)?)));
        }
        if self.take("(") {
            let expr = self.expression(0)?;
            return self.take(")").then_some(expr);
        }
        let first = self.rest.as_bytes().first().copied()?;
        if matches!(first, b'\'' | b'"') {
            let (text, tail) = self.rest[1..].split_once(char::from(first))?;
            if text.contains('\\') {
                return None;
            }
            self.rest = tail;
            return Some(Expr::Text(text.into()));
        }
        if first.is_ascii_digit() || first == b'.' {
            return self.number();
        }
        let end = self
            .rest
            .bytes()
            .take_while(|&byte| identifier(byte))
            .count();
        if end == 0 {
            return None;
        }
        let (name, rest) = self.rest.split_at(end);
        self.rest = rest;
        if self.take("(") {
            let mut args = vec![self.expression(0)?];
            while self.take(",") {
                args.push(self.expression(0)?);
            }
            return self
                .take(")")
                .then(|| Function::parse(name, args.len()))?
                .map(|function| Expr::Call(function, args));
        }
        match name {
            "True" => Some(Expr::Bool(true)),
            "False" => Some(Expr::Bool(false)),
            "mode" | "race_designator" | "time" | "left" | "right" | "double" | "cl" | "left_s"
            | "right_s" | "double_s" | "cl_s" | "path" | "flag" | "flag_s" => {
                Some(Expr::Variable(name.into()))
            }
            "rtime" | "etime" | "bbbv" | "bbbv_solved" | "bbbv_s" | "zini" | "op" | "isl"
            | "stnb" | "ioe" | "thrp" | "corr" | "pluck" | "lce" | "rce" | "dce" | "ce"
            | "ce_s" | "rqp" | "qg" => {
                self.needs_result = true;
                Some(Expr::Variable(name.into()))
            }
            _ => None,
        }
    }

    fn number(&mut self) -> Option<Expr> {
        let start = self.rest;
        let mut end = self.rest.bytes().take_while(u8::is_ascii_digit).count();
        let mut integer = true;
        if start[end..].starts_with('.') {
            integer = false;
            end += 1 + start[end + 1..]
                .bytes()
                .take_while(u8::is_ascii_digit)
                .count();
        }
        if start[end..].starts_with(['e', 'E']) {
            integer = false;
            end += 1;
            if start[end..].starts_with(['+', '-']) {
                end += 1;
            }
            end += start[end..].bytes().take_while(u8::is_ascii_digit).count();
        }
        let value = start[..end].parse::<f64>().ok()?;
        if integer && value >= (1_u64 << 53) as f64 {
            return None;
        }
        self.rest = &start[end..];
        Some(Expr::Number(value, integer))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn python_default_formulas_keep_order_and_format_the_same_snapshot() {
        let definitions = r#"[DEFAULT]
游戏模式 = mode
RTime = f'{time:.3f}'
Est RTime = f'{etime:.3f}'
3BV = f'{bbbv_solved}/{bbbv}'
3BV/s = f'{bbbv_s:.3f}'
ZiNi = f'{zini}@{zini/max(etime,1e-6):.3f}'
Ops = op
Isls = isl
Left = f'{left}@{left_s:.3f}'
Right = f'{right}@{right_s:.3f}'
Double = f'{double}@{double_s:.3f}'
STNB = f'{stnb:.3f}'
IOE = f'{ioe:.3f}'
Thrp = f'{thrp:.3f}'
Corr = f'{corr:.3f}'
Path = f'{path:.1f}'
Pluck = f'{pluck:.3f}'
"#;
        let rows = CounterConfig::parse(definitions).unwrap();
        assert_eq!(rows.len(), 17);
        assert_eq!(rows.label(0), Some("游戏模式"));
        assert_eq!(rows.label(16), Some("Pluck"));
        let variable = |name: &str| {
            Some(match name {
                "mode" => Value::Text("Standard".into()),
                "bbbv_solved" | "left" => Value::count(12),
                "bbbv" => Value::count(16),
                "zini" => Value::count(20),
                "op" | "right" => Value::count(3),
                "isl" | "double" => Value::count(2),
                "time" => Value::number(4.25),
                "etime" => Value::number(5.0),
                "left_s" => Value::number(3.4567),
                "path" => Value::number(109.28),
                _ => Value::number(0.5),
            })
        };
        let actual: Vec<_> = rows
            .rows
            .iter()
            .map(|row| row.formula.as_ref().unwrap().eval(&variable).unwrap())
            .collect();
        assert_eq!(
            actual,
            [
                "Standard", "4.250", "5.000", "12/16", "0.500", "20@4.000", "3", "2", "12@3.457",
                "3@0.500", "2@0.500", "0.500", "0.500", "0.500", "0.500", "109.3", "0.500",
            ]
        );
    }

    #[test]
    fn imported_rows_keep_pregame_values_and_isolate_formula_errors() {
        let root = tempfile::tempdir().unwrap();
        fs::write(
            root.path().join("scoreBoardSetting.ini"),
            concat!(
                "\u{feff}[DEFAULT]\n点击 = (\n    left + right + double)\n",
                "倒数 = 1 / time if time > 0 else 0\n难度 = f'{bbbv}'\n",
                "复杂表达式 = sum([v for v in [1, 2]])\n计算错误 = left / right\n",
                "[other]\nignored = 5\n",
            ),
        )
        .unwrap();
        let settings = crate::config::Settings::read(root.path()).unwrap();
        let mut round = Round::new(&settings);
        let config = &settings.counter_config;
        assert_eq!(config.label(0), Some("点击"));
        assert_eq!(
            config.values(&round, "Standard", "unsupported"),
            ["0", "0", "--", "unsupported", "error"]
        );
        round.status.phase = 1;
        round.status.seconds = 4.0;
        round.status.left = 5;
        round.status.right = 2;
        assert_eq!(
            config.values(&round, "Standard", "unsupported"),
            ["7", "0.25", "--", "unsupported", "2.5"]
        );
    }

    #[test]
    fn arithmetic_and_rounding_follow_python_for_supported_values() {
        for (source, expected) in [
            ("-2**2 + 2**3**2", "508"),
            ("7 // -3", "-3"),
            ("1.0 // 0.1", "9.0"),
            ("7 % -3", "-2"),
            ("round(-1.25, 1)", "-1.2"),
            ("1 if False and 0 / 0 else 2", "2"),
            ("f'{{{round(2.675, 2):.2f}}}'", "{2.67}"),
        ] {
            assert_eq!(
                Formula::parse(source).unwrap().eval(&|_| None).as_deref(),
                Some(expected)
            );
        }
    }
}
