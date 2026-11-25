use aes_gcm::{
    aead::{rand_core::RngCore, AeadInPlace, OsRng},
    Aes128Gcm, KeyInit,
};
use md5::{Digest, Md5};
use ms_toollib::{videos::base_video::LivePluckSnapshot, BaseVideo};
use std::{
    fs::OpenOptions,
    io::{self, Read, Seek, SeekFrom, Write},
    path::Path,
};

const KEY: [u8; 16] = [
    173, 239, 218, 129, 84, 35, 95, 237, 23, 47, 166, 30, 121, 187, 124, 187,
];
const VERSION: u8 = 0;
const PLUCK_OFFSET: usize = 51;

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
        let mut data = Vec::with_capacity(84 + board_len);
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
