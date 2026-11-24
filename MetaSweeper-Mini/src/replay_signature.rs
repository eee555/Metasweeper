use std::io;

#[cfg(mini_custom_replay_signer)]
include!(concat!(env!("OUT_DIR"), "/replay_signer_module.rs"));

#[cfg(not(mini_custom_replay_signer))]
mod signer {
    use hmac::{Hmac, Mac};
    use sha2::Sha256;

    pub(super) fn sign_payload(payload: &[u8]) -> Result<[u8; 32], String> {
        let mut hmac = Hmac::<Sha256>::new_from_slice(include_bytes!("../assets/replay-key.bin"))
            .expect("valid embedded HMAC key");
        hmac.update(payload);
        Ok(hmac.finalize().into_bytes().into())
    }
}

pub(crate) fn sign(data: &mut Vec<u8>) -> io::Result<()> {
    if !data.ends_with(&[0, 0, 0]) {
        return Err(io::Error::other("Invalid unsigned EVF trailer"));
    }
    let payload_len = data.len() - 2;
    let sign_payload: fn(&[u8]) -> Result<[u8; 32], String> = signer::sign_payload;
    let checksum = sign_payload(&data[..payload_len]).map_err(io::Error::other)?;
    data.truncate(payload_len);
    data.extend_from_slice(&[0, 32]);
    data.extend_from_slice(&checksum);
    Ok(())
}
