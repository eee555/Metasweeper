use aes_gcm::{
    aead::{rand_core::RngCore, AeadInPlace, OsRng},
    Aes128Gcm, KeyInit,
};
use md5::{Digest, Md5};
use ms_toollib::{videos::base_video::LivePluckSnapshot, BaseVideo};
use std::{
    fs::{File, OpenOptions},
    io::{self, BufReader, Read, Seek, SeekFrom, Take, Write},
    path::Path,
};

const KEY: [u8; 16] = [
    173, 239, 218, 129, 84, 35, 95, 237, 23, 47, 166, 30, 121, 187, 124, 187,
];
const VERSION: u8 = 0;
const PLUCK_OFFSET: usize = 51;
const HEADER_LEN: usize = 84;

#[repr(u8)]
pub(crate) enum GameResult {
    Restart = 0,
    Loss = 5,
    Win = 6,
}

pub(crate) struct Record {
    data: Vec<u8>,
    pluck: LivePluckSnapshot,
}

impl Record {
    pub(crate) fn new(
        video: &BaseVideo<Vec<Vec<i32>>>,
        result: GameResult,
        fair: bool,
        replay: &[u8],
    ) -> Self {
        let board_len = (video.height * video.width).div_ceil(8);
        let mut data = Vec::with_capacity(HEADER_LEN + board_len);
        data.extend([result as u8, video.height as u8, video.width as u8]);
        data.extend((video.mine_num as u16).to_be_bytes());
        for value in [
            video.get_rtime_ms().unwrap_or_default(),
            video.get_left() as u32,
            video.get_right() as u32,
            video.get_double() as u32,
            video.get_rce().unwrap_or_default() as u32,
            video.get_lce().unwrap_or_default() as u32,
            video.get_dce().unwrap_or_default() as u32,
        ] {
            data.extend(value.to_be_bytes());
        }
        for value in [
            video.static_params.bbbv,
            video.get_bbbv_solved().unwrap_or_default(),
            video.static_params.zini,
        ] {
            data.extend((value as u16).to_be_bytes());
        }
        data.extend((video.get_flag() as u32).to_be_bytes());
        data.extend(video.get_path().to_be_bytes());
        debug_assert_eq!(data.len(), PLUCK_OFFSET);
        data.extend(0.0_f64.to_be_bytes());
        data.extend(video.start_time.to_be_bytes());
        data.extend([
            video.mode as u8,
            u8::from(fair && video.is_completed && video.mode == 0),
            u8::from(fair),
        ]);
        data.extend((video.static_params.op as u16).to_be_bytes());
        data.extend((video.static_params.isl as u16).to_be_bytes());
        data.extend(&Md5::digest(replay)[..8]);
        data.extend((board_len as u16).to_be_bytes());
        let mut byte = 0;
        for (index, cell) in video.board.iter().flatten().enumerate() {
            byte |= u8::from(*cell == -1) << (7 - index % 8);
            if index % 8 == 7 {
                data.push(byte);
                byte = 0;
            }
        }
        if video.height * video.width % 8 != 0 {
            data.push(byte);
        }
        Self {
            data,
            pluck: video.live_pluck_snapshot(),
        }
    }

    pub(crate) fn append(mut self, path: &Path) -> io::Result<()> {
        let pluck = self.pluck.wait().unwrap_or(f64::NAN);
        self.data[PLUCK_OFFSET..PLUCK_OFFSET + 8].copy_from_slice(&pluck.to_be_bytes());
        let mut nonce = [0; 12];
        OsRng
            .try_fill_bytes(&mut nonce)
            .map_err(|error| io::Error::other(error.to_string()))?;
        let cipher = Aes128Gcm::new(&KEY.into());
        let tag = cipher
            .encrypt_in_place_detached(&nonce.into(), b"", &mut self.data)
            .map_err(|_| io::Error::other("Could not encrypt stats record"))?;
        let blob_len = u16::try_from(nonce.len() + tag.len() + self.data.len())
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
        let mut file = OpenOptions::new()
            .create(true)
            .read(true)
            .append(true)
            .open(path)?;
        file.lock()?;
        let mut frame = Vec::with_capacity(3 + usize::from(blob_len));
        if file.metadata()?.len() == 0 {
            frame.push(VERSION);
        } else {
            let mut version = [0];
            file.seek(SeekFrom::Start(0))?;
            file.read_exact(&mut version)?;
            if version[0] != VERSION {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    format!("Unsupported stats.dat version {}", version[0]),
                ));
            }
        }
        frame.extend(blob_len.to_be_bytes());
        frame.extend(nonce);
        frame.extend(tag);
        frame.extend(self.data);
        file.write_all(&frame)
    }
}

pub(crate) struct SavedRecord<'a> {
    pub state: u8,
    pub rows: usize,
    pub columns: usize,
    pub mines: u16,
    pub milliseconds: u32,
    pub clicks: [u32; 3],
    pub effective_clicks: [u32; 3],
    pub bbbv: u16,
    pub solved: u16,
    pub zini: u16,
    pub path: f64,
    pub start_time: u64,
    pub mode: u8,
    pub official: bool,
    pub fair: bool,
    pub openings: u16,
    pub islands: u16,
    pub board: &'a [u8],
}

impl<'a> SavedRecord<'a> {
    fn decode(data: &'a [u8]) -> Option<Self> {
        if data.len() < HEADER_LEN {
            return None;
        }
        let read_u16 = |offset| u16::from_be_bytes(data[offset..offset + 2].try_into().unwrap());
        let read_u32 = |offset| u32::from_be_bytes(data[offset..offset + 4].try_into().unwrap());
        let rows = usize::from(data[1]);
        let columns = usize::from(data[2]);
        let board = data.get(HEADER_LEN..HEADER_LEN + usize::from(read_u16(82)))?;
        if rows == 0 || columns == 0 {
            return None;
        }
        Some(Self {
            state: data[0],
            rows,
            columns,
            mines: read_u16(3),
            milliseconds: read_u32(5),
            clicks: [read_u32(9), read_u32(13), read_u32(17)],
            effective_clicks: [read_u32(25), read_u32(21), read_u32(29)],
            bbbv: read_u16(33),
            solved: read_u16(35),
            zini: read_u16(37),
            path: f64::from_be_bytes(data[43..51].try_into().unwrap()),
            start_time: u64::from_be_bytes(data[59..67].try_into().unwrap()),
            mode: data[67],
            official: data[68] == 1,
            fair: data[69] == 1,
            openings: read_u16(70),
            islands: read_u16(72),
            board,
        })
    }
}

pub(crate) struct StatsReader {
    reader: Take<BufReader<File>>,
    length: u64,
}

impl StatsReader {
    pub(crate) fn open(path: &Path) -> io::Result<Self> {
        let file = File::open(path)?;
        let length = file.metadata()?.len();
        let mut reader = BufReader::new(file).take(length);
        let mut version = [0];
        reader.read_exact(&mut version)?;
        if version[0] != VERSION {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                format!("Unsupported stats.dat version {}", version[0]),
            ));
        }
        Ok(Self { reader, length })
    }

    pub(crate) fn progress(&self) -> u8 {
        let consumed = self.length - self.reader.limit();
        ((u128::from(consumed) * 100 / u128::from(self.length)) as u8).min(99)
    }

    pub(crate) fn read_batch(&mut self, size: usize) -> io::Result<Vec<Vec<u8>>> {
        let mut frames = Vec::with_capacity(size);
        for _ in 0..size {
            let mut frame_size = [0; 2];
            match self.reader.read_exact(&mut frame_size) {
                Ok(()) => {}
                Err(error) if error.kind() == io::ErrorKind::UnexpectedEof => break,
                Err(error) => return Err(error),
            }
            let mut blob = vec![0; u16::from_be_bytes(frame_size) as usize];
            match self.reader.read_exact(&mut blob) {
                Ok(()) => frames.push(blob),
                Err(error) if error.kind() == io::ErrorKind::UnexpectedEof => break,
                Err(error) => return Err(error),
            }
        }
        Ok(frames)
    }
}

pub(crate) fn decode_frames(
    frames: &mut [Vec<u8>],
    mut visit: impl FnMut(SavedRecord<'_>) -> io::Result<()>,
) -> io::Result<bool> {
    let cipher = Aes128Gcm::new(&KEY.into());
    let mut found = false;
    for blob in frames {
        if blob.len() < 28 {
            continue;
        }
        let (metadata, data) = blob.split_at_mut(28);
        if cipher
            .decrypt_in_place_detached(
                (&metadata[..12]).into(),
                b"",
                data,
                (&metadata[12..]).into(),
            )
            .is_err()
        {
            continue;
        }
        if let Some(record) = SavedRecord::decode(data) {
            found = true;
            visit(record)?;
        }
    }
    Ok(found)
}

#[cfg(test)]
mod tests {
    use super::*;
    use ms_toollib::videos::base_video::NewBaseVideo2;
    use std::{fs, time::Duration};

    #[test]
    fn appends_win_loss_and_restart_as_version_zero_records() {
        let path = std::env::temp_dir().join(format!("mini-stats-{}.dat", std::process::id()));
        fs::write(&path, []).unwrap();
        for result in [GameResult::Win, GameResult::Loss, GameResult::Restart] {
            let mut video = BaseVideo::<Vec<Vec<i32>>>::new(vec![vec![-1, 1], vec![1, 1]], 16);
            video.set_live_pluck_enabled(true);
            let input_at = video.video_start_instant;
            let moves = match result {
                GameResult::Win => &[(17, 17), (1, 17), (17, 1)][..],
                GameResult::Loss => &[(17, 17), (1, 1)][..],
                GameResult::Restart => &[(17, 17)][..],
            };
            for (index, &position) in moves.iter().enumerate() {
                let time = input_at + Duration::from_millis(index as u64 * 100);
                video.step_at("lc", position, time).unwrap();
                video.step_at("lr", position, time).unwrap();
            }
            if matches!(result, GameResult::Restart) {
                video.step_game_state("replay").unwrap();
            }
            Record::new(&video, result, true, b"replay")
                .append(&path)
                .unwrap();
        }
        let data = fs::read(&path).unwrap();
        fs::remove_file(&path).unwrap();
        assert_eq!(data[0], VERSION);
        let cipher = Aes128Gcm::new(&KEY.into());
        let mut frames = &data[1..];
        for (state, time, official) in [(6, Some(200), 1), (5, Some(100), 0), (0, None, 0)] {
            let length = u16::from_be_bytes(frames[..2].try_into().unwrap()) as usize;
            let (blob, rest) = frames[2..].split_at(length);
            frames = rest;
            let mut record = blob[28..].to_vec();
            cipher
                .decrypt_in_place_detached(blob[..12].into(), b"", &mut record, blob[12..28].into())
                .unwrap();
            assert_eq!(&record[..5], &[state, 2, 2, 0, 1]);
            if let Some(time) = time {
                assert_eq!(u32::from_be_bytes(record[5..9].try_into().unwrap()), time);
            }
            assert_eq!(&record[67..70], &[0, official, 1]);
            assert_eq!(&record[74..82], &Md5::digest(b"replay")[..8]);
            assert_eq!(&record[82..], &[0, 1, 0b1000_0000]);
        }
        assert!(frames.is_empty());
    }
}
