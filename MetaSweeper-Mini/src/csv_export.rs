use crate::stats::{decode_frames, GameResult, SavedRecord, StatsReader};
use chrono::{DateTime, Datelike, Local, Timelike};
use std::{
    collections::VecDeque,
    io::{self, BufWriter, Write},
    path::{Path, PathBuf},
    sync::mpsc,
    thread,
};
use tempfile::NamedTempFile;

const STATS_HEADER: &str = "Day,Month,Year,Hour,Min,Sec,mode,Time,BBBV,BBBVs,style,cell0,cell1,cell2,cell3,cell4,cell5,cell6,cell7,cell8,Lcl,Rcl,Dcl,Leff,Reff,Deff,Openings,Islands,Path,GZiNi,HZiNi";
const TEXTSTATS_HEADER: &str = "Mode,Event,Year,Month,Day,Hour,Minute,Second,Level,Width,Height,Mines,Time,Solved 3BV,3BV,ZiNi,HZiNi,Openings,Islands,Left Clicks,Right Clicks,Double Clicks,Left Effective Clicks,Right Effective Clicks,Double Effective Clicks,Path,Ones,Twos,Threes,Fours,Fives,Sixes,Sevens,Eights";
const BATCH_SIZE: usize = 128;
const MODES: [&str; 17] = [
    "classic",
    "",
    "",
    "",
    "win7",
    "classic no guess",
    "strict no guess",
    "weak no guess",
    "blessing no guess",
    "guessable no guess",
    "lucky mode",
    "chord recursive",
    "flag recursive",
    "chord flag recursive",
    "no guess chord recursive",
    "no guess flag recursive",
    "no guess chord flag recursive",
];

pub(crate) fn targets(directory: &Path, player: &str) -> [PathBuf; 2] {
    let sanitized: String = player
        .chars()
        .map(|character| match character {
            '\\' | '/' | ':' | '*' | '?' | '"' | '<' | '>' | '|' | '\0'..='\x1f' => '_',
            valid => valid,
        })
        .collect();
    let name = sanitized.trim_matches([' ', '.']);
    let name = if name.is_empty() { "player" } else { name };
    [
        directory.join(format!("{name}_stats.csv")),
        directory.join(format!("{name}_textstats.csv")),
    ]
}

pub(crate) fn export(
    source: &Path,
    targets: &[PathBuf; 2],
    overwrite: bool,
    mut progress: impl FnMut(u8),
) -> io::Result<()> {
    for target in targets {
        if target.is_dir() || (!overwrite && target.try_exists()?) {
            return Err(io::Error::new(
                io::ErrorKind::AlreadyExists,
                format!("Output path already exists: {}", target.display()),
            ));
        }
    }
    let directory = targets[0].parent().unwrap();
    let mut stats_file = NamedTempFile::new_in(directory)?;
    let mut textstats_file = NamedTempFile::new_in(directory)?;
    let mut stats = BufWriter::new(stats_file.as_file_mut());
    let mut textstats = BufWriter::new(textstats_file.as_file_mut());
    write!(stats, "{STATS_HEADER}\r\n")?;
    write!(textstats, "{TEXTSTATS_HEADER}\r\n")?;
    write_batches(
        StatsReader::open(source)?,
        thread::available_parallelism().map_or(1, usize::from),
        &mut stats,
        &mut textstats,
        &mut progress,
    )?;
    stats.flush()?;
    textstats.flush()?;
    drop((stats, textstats));

    for (file, target) in [stats_file, textstats_file].into_iter().zip(targets) {
        if overwrite {
            file.persist(target)?;
        } else {
            file.persist_noclobber(target)?;
        }
    }
    progress(100);
    Ok(())
}

fn write_batches(
    mut reader: StatsReader,
    worker_count: usize,
    stats: &mut impl Write,
    textstats: &mut impl Write,
    progress: &mut impl FnMut(u8),
) -> io::Result<()> {
    let found = thread::scope(|scope| -> io::Result<bool> {
        let mut active = VecDeque::new();
        for _ in 0..worker_count {
            let batch = reader.read_batch(BATCH_SIZE)?;
            if batch.is_empty() {
                break;
            }
            let (send, jobs) = mpsc::channel::<Vec<Vec<u8>>>();
            let (reply, results) = mpsc::channel();
            send.send(batch).map_err(worker_stopped)?;
            thread::Builder::new().spawn_scoped(scope, move || {
                while let Ok(mut batch) = jobs.recv() {
                    let mut stats_rows = Vec::new();
                    let mut textstats_rows = Vec::new();
                    let result = decode_frames(&mut batch, |record| {
                        write_record(record, &mut stats_rows, &mut textstats_rows)
                    });
                    if reply
                        .send(result.map(|valid| (valid, stats_rows, textstats_rows)))
                        .is_err()
                    {
                        break;
                    }
                }
            })?;
            active.push_back((send, results, reader.progress()));
        }

        let mut found = false;
        let mut reported = 0;
        while let Some((send, results, percent)) = active.pop_front() {
            let (valid, stats_rows, textstats_rows) = results.recv().map_err(worker_stopped)??;
            let batch = reader.read_batch(BATCH_SIZE)?;
            if !batch.is_empty() {
                send.send(batch).map_err(worker_stopped)?;
                active.push_back((send, results, reader.progress()));
            }
            found |= valid;
            stats.write_all(&stats_rows)?;
            textstats.write_all(&textstats_rows)?;
            if percent > reported {
                progress(percent);
                reported = percent;
            }
        }
        Ok(found)
    })?;
    if !found {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "No valid game records",
        ));
    }
    Ok(())
}

fn worker_stopped(_: impl std::fmt::Debug) -> io::Error {
    io::Error::other("CSV export worker stopped")
}

fn write_record(
    record: SavedRecord<'_>,
    stats: &mut impl Write,
    textstats: &mut impl Write,
) -> io::Result<()> {
    if !record.fair {
        return Ok(());
    }
    let level = match (record.rows, record.columns, record.mines) {
        (8, 8, 10) => "BEG",
        (16, 16, 40) => "INT",
        (16, 30, 99) => "EXP",
        _ => "CUS",
    };
    let won = record.state == GameResult::Win as u8;
    let mode = MODES.get(usize::from(record.mode)).ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            format!("Unknown game mode {}", record.mode),
        )
    })?;
    let mut board = vec![vec![0; record.columns]; record.rows];
    for (index, cell) in board.iter_mut().flatten().enumerate() {
        if record
            .board
            .get(index / 8)
            .is_some_and(|byte| byte & (0x80 >> (index % 8)) != 0)
        {
            *cell = -1;
        }
    }
    ms_toollib::cal_board_numbers(&mut board);
    let counts = ms_toollib::cal_cell_nums(&board);
    let hzini = ms_toollib::cal_hzini(&board);

    let elapsed = f64::from(record.milliseconds) / 1000.0;
    let timestamp = record.start_time as f64 / 1_000_000.0 + elapsed;
    let utc =
        DateTime::from_timestamp_micros((timestamp * 1_000_000.0).round_ties_even() as i64)
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "Invalid game timestamp"))?;
    let date = utc.with_timezone(&Local);
    let [year, month, day, hour, minute, second] = [
        date.year(),
        date.month() as i32,
        date.day() as i32,
        date.hour() as i32,
        date.minute() as i32,
        date.second() as i32,
    ];
    let [left, right, double] = record.clicks;
    let [left_eff, right_eff, double_eff] = record.effective_clicks;
    let path = csv_float(record.path);
    let event = if won { "win" } else { "blast" };
    write!(
        textstats,
        "{mode},{event},{year},{month},{day},{hour},{minute},{second},{level},{},{},{},{elapsed:?},{},{},{},{hzini},{},{},{left},{right},{double},{left_eff},{right_eff},{double_eff},{path}",
        record.columns, record.rows, record.mines, record.solved, record.bbbv, record.zini,
        record.openings, record.islands,
    )?;
    for count in &counts[1..] {
        write!(textstats, ",{count}")?;
    }
    textstats.write_all(b"\r\n")?;
    if won && record.mode == 0 && record.official && level != "CUS" {
        let style = if right_eff == 0 { "NF" } else { "Flag" };
        write!(
            stats,
            "{day},{month},{year},{hour},{minute},{second},{level},{elapsed:?},{},{},{style}",
            record.bbbv, record.solved,
        )?;
        for count in counts {
            write!(stats, ",{count}")?;
        }
        write!(
            stats,
            ",{left},{right},{double},{left_eff},{right_eff},{double_eff},{},{},{path},{},{hzini}\r\n",
            record.openings, record.islands, record.zini,
        )?;
    }
    Ok(())
}

fn csv_float(value: f64) -> String {
    if value.is_nan() {
        return "nan".to_owned();
    }
    let text = format!("{value:?}");
    if let Some((mantissa, exponent)) = text.split_once('e') {
        let exponent = exponent.parse::<i32>().unwrap();
        format!("{mantissa}e{exponent:+03}")
    } else {
        text
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::stats::Record;
    use ms_toollib::{videos::base_video::NewBaseVideo2, BaseVideo};

    #[test]
    fn parallel_batches_preserve_both_csvs_and_report_ordered_progress() {
        let directory = tempfile::tempdir().unwrap();
        let source = directory.path().join("stats.dat");
        let mut board = vec![vec![0; 8]; 8];
        for cell in board.iter_mut().flatten().take(10) {
            *cell = -1;
        }
        ms_toollib::cal_board_numbers(&mut board);
        let mut video = BaseVideo::<Vec<Vec<i32>>>::new(board, 16);
        let input = video.video_start_instant;
        video.step_at("lc", (113, 113), input).unwrap();
        video.step_at("lr", (113, 113), input).unwrap();
        video.is_completed = true;
        let count = BATCH_SIZE * 5 + 3;
        for index in 0..count {
            video.start_time = 1_700_000_000_000_000 + index as u64 * 1_000_000;
            Record::new(&video, GameResult::Win, true, b"")
                .append(&source)
                .unwrap();
        }

        let run = |workers| {
            let (mut stats, mut textstats, mut progress) = (Vec::new(), Vec::new(), Vec::new());
            write_batches(
                StatsReader::open(&source).unwrap(),
                workers,
                &mut stats,
                &mut textstats,
                &mut |percent| progress.push(percent),
            )
            .unwrap();
            (stats, textstats, progress)
        };
        let serial = run(1);
        let parallel = run(3);
        assert_eq!(serial, parallel);
        assert_eq!(
            parallel.0.iter().filter(|&&byte| byte == b'\n').count(),
            count
        );
        assert_eq!(
            parallel.1.iter().filter(|&&byte| byte == b'\n').count(),
            count
        );
        assert!(parallel.2.len() > 1);
        assert!(parallel.2.windows(2).all(|pair| pair[0] < pair[1]));
        assert_eq!(parallel.2.last(), Some(&99));

        let files = targets(directory.path(), "test");
        let mut progress = Vec::new();
        export(&source, &files, false, |percent| progress.push(percent)).unwrap();
        assert_eq!(progress.last(), Some(&100));
        for (file, (header, records)) in files
            .into_iter()
            .zip([(STATS_HEADER, serial.0), (TEXTSTATS_HEADER, serial.1)])
        {
            let contents = std::fs::read(file).unwrap();
            assert_eq!(contents, [header.as_bytes(), b"\r\n", &records].concat());
        }
    }
}
