using System;
using System.IO;
using System.Security.Cryptography;

internal static class ReplayChecksum
{
    // EVF v4 field 27 stores the checksum length as a big-endian uint16.
    // A fixed length lets a verifier locate the checksum without parsing the
    // whole event stream.
    private const int Size = 32;

    // This key identifies MetaSweeper-Mini (元3.3.4-迷你版). Anyone can extract
    // it from the executable, so this signature detects casual tampering and
    // source confusion. Replace it if it is ever published or leaked.
    private static readonly byte[] Key =
    {
        0x51, 0xF3, 0x48, 0x76, 0x8D, 0x85, 0x78, 0xCF,
        0x38, 0x25, 0x33, 0x90, 0xAD, 0x11, 0xCC, 0x5C,
        0xD1, 0x2C, 0xBC, 0xA6, 0x96, 0x22, 0xDC, 0x0C,
        0x61, 0x57, 0x72, 0xA4, 0xC2, 0x12, 0x67, 0xDE
    };

    internal static byte[] GetSelfKey()
    {
        return (byte[])Key.Clone();
    }

    internal static byte[] GetChecksum(byte[] data)
    {
        if (data == null)
            throw new ArgumentNullException("data");
        using (var hmac = new HMACSHA256(Key))
            return hmac.ComputeHash(data, 0, data.Length);
    }

    internal static bool ValidChecksum(byte[] data, byte[] checksum)
    {
        if (data == null || checksum == null || checksum.Length != Size)
            return false;
        byte[] expected = GetChecksum(data);
        int difference = 0;
        for (int index = 0; index < Size; index++)
            difference |= expected[index] ^ checksum[index];
        return difference == 0;
    }

    internal static byte[] Sign(byte[] evf)
    {
        if (evf == null)
            throw new ArgumentNullException("evf");
        if (LooksSigned(evf))
            throw new InvalidDataException("录像已包含校验码，不能重复签名。");
        // generate_evf_v4_raw_data ends with the event terminator and an empty
        // checksum length, so the last three bytes are all zero.
        if (evf.Length < 3 || evf[evf.Length - 1] != 0
            || evf[evf.Length - 2] != 0 || evf[evf.Length - 3] != 0)
            throw new InvalidDataException("EVF 校验码字段格式不正确。");

        int payloadLength = evf.Length - 2;
        byte[] payload = Copy(evf, 0, payloadLength);
        byte[] checksum = GetChecksum(payload);
        var signed = new byte[payloadLength + 2 + Size];
        Buffer.BlockCopy(payload, 0, signed, 0, payloadLength);
        signed[payloadLength] = (byte)(Size >> 8);
        signed[payloadLength + 1] = (byte)(Size & 0xFF);
        Buffer.BlockCopy(checksum, 0, signed, payloadLength + 2, Size);
        return signed;
    }

    internal static bool Verify(byte[] evf)
    {
        if (evf == null || evf.Length < 2 + Size)
            return false;
        int payloadLength = evf.Length - 2 - Size;
        // EVF v4 field 26 is the event terminator, which must be the last byte
        // of the authenticated payload.
        if (payloadLength < 1 || evf[payloadLength - 1] != 0)
            return false;
        int declared = (evf[payloadLength] << 8) | evf[payloadLength + 1];
        if (declared != Size)
            return false;
        return ValidChecksum(Copy(evf, 0, payloadLength),
            Copy(evf, payloadLength + 2, Size));
    }

    private static byte[] Copy(byte[] source, int offset, int length)
    {
        var result = new byte[length];
        Buffer.BlockCopy(source, offset, result, 0, length);
        return result;
    }

    private static bool LooksSigned(byte[] evf)
    {
        if (evf.Length < 2 + Size + 1)
            return false;
        int lengthOffset = evf.Length - Size - 2;
        return evf[lengthOffset] == 0 && evf[lengthOffset + 1] == Size;
    }
}
