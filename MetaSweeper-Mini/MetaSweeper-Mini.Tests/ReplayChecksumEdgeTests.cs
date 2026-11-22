using System;
using System.Security.Cryptography;
using System.Threading.Tasks;
using Xunit;

public class ReplayChecksumEdgeTests
{
    [Fact]
    public void SignThenVerify_RoundTripsEveryPayloadLengthFromZeroThroughOneThousand()
    {
        for (int payloadLength = 0; payloadLength <= 1000; payloadLength++)
        {
            var payload = new byte[payloadLength];
            for (int index = 0; index < payload.Length; index++)
                payload[index] = (byte)((index * 37) + payloadLength);

            byte[] evf = CreateEvfWithEmptyChecksumField(payload);
            byte[] signed = ReplayChecksum.Sign(evf);

            Assert.Equal(evf.Length + 32, signed.Length);
            Assert.True(ReplayChecksum.Verify(signed),
                "Signature did not verify for payload length " + payloadLength + ".");
        }
    }

    [Fact]
    public void AllByteValues_ChecksumValidatesAndSignatureRoundTrips()
    {
        var data = new byte[256];
        for (int value = 0; value < data.Length; value++)
            data[value] = (byte)value;

        byte[] checksum = ReplayChecksum.GetChecksum(data);
        Assert.Equal(32, checksum.Length);
        Assert.True(ReplayChecksum.ValidChecksum(data, checksum));

        byte[] evf = CreateEvfWithEmptyChecksumField(data);
        byte[] signed = ReplayChecksum.Sign(evf);
        int payloadLength = evf.Length - 2;

        Assert.Equal(0, signed[payloadLength]);
        Assert.Equal(0x20, signed[payloadLength + 1]);
        Assert.True(ReplayChecksum.Verify(signed));
        Assert.Equal(ReplayChecksum.GetChecksum(CopyEdgeRange(evf, 0, payloadLength)),
            CopyEdgeRange(signed, payloadLength + 2, 32));
    }

    [Fact]
    public void GetChecksum_IsDeterministicUnderParallelCalls()
    {
        const int callCount = 64;
        var data = new byte[4096];
        for (int index = 0; index < data.Length; index++)
            data[index] = (byte)(index * 29);

        byte[] expected = ReplayChecksum.GetChecksum(data);
        var results = new byte[callCount][];
        Parallel.For(0, callCount, index => results[index] = ReplayChecksum.GetChecksum(data));

        for (int index = 0; index < results.Length; index++)
            Assert.Equal(expected, results[index]);
    }

    [Fact]
    public void ValidChecksum_IsDeterministicUnderParallelCalls()
    {
        const int callCount = 128;
        var data = new byte[2048];
        for (int index = 0; index < data.Length; index++)
            data[index] = (byte)(index * 17);

        byte[] validChecksum = ReplayChecksum.GetChecksum(data);
        byte[] invalidChecksum = (byte[])validChecksum.Clone();
        invalidChecksum[0] ^= 0xFF;
        var results = new bool[callCount];

        Parallel.For(0, callCount, index =>
        {
            byte[] checksum = index % 2 == 0 ? validChecksum : invalidChecksum;
            results[index] = ReplayChecksum.ValidChecksum(data, checksum);
        });

        for (int index = 0; index < results.Length; index++)
            Assert.Equal(index % 2 == 0, results[index]);
    }

    [Fact]
    public void Sign_IsDeterministicUnderParallelCalls()
    {
        const int callCount = 64;
        var payload = new byte[4096];
        for (int index = 0; index < payload.Length; index++)
            payload[index] = (byte)(index * 43);

        byte[] evf = CreateEvfWithEmptyChecksumField(payload);
        byte[] expected = ReplayChecksum.Sign(evf);
        var results = new byte[callCount][];
        Parallel.For(0, callCount, index => results[index] = ReplayChecksum.Sign(evf));

        for (int index = 0; index < results.Length; index++)
            Assert.Equal(expected, results[index]);
    }

    [Fact]
    public void Verify_IsDeterministicUnderParallelCalls()
    {
        const int callCount = 128;
        var payload = new byte[4096];
        for (int index = 0; index < payload.Length; index++)
            payload[index] = (byte)(index * 53);

        byte[] validEvf = ReplayChecksum.Sign(CreateEvfWithEmptyChecksumField(payload));
        byte[] invalidEvf = (byte[])validEvf.Clone();
        invalidEvf[invalidEvf.Length - 1] ^= 0xFF;
        var results = new bool[callCount];

        Parallel.For(0, callCount, index =>
        {
            byte[] evf = index % 2 == 0 ? validEvf : invalidEvf;
            results[index] = ReplayChecksum.Verify(evf);
        });

        for (int index = 0; index < results.Length; index++)
            Assert.Equal(index % 2 == 0, results[index]);
    }

    [Fact]
    public void Verify_RejectsSwappedLengthBytes()
    {
        byte[] signed = ReplayChecksum.Sign(CreateEvfWithEmptyChecksumField(new byte[] { 1, 2, 3 }));
        int lengthOffset = signed.Length - 34;
        signed[lengthOffset] = 0x20;
        signed[lengthOffset + 1] = 0x00;

        Assert.False(ReplayChecksum.Verify(signed));
    }

    [Fact]
    public void Verify_RejectsZeroLength()
    {
        byte[] signed = ReplayChecksum.Sign(CreateEvfWithEmptyChecksumField(new byte[] { 1, 2, 3 }));
        int lengthOffset = signed.Length - 34;
        signed[lengthOffset] = 0x00;
        signed[lengthOffset + 1] = 0x00;

        Assert.False(ReplayChecksum.Verify(signed));
    }

    [Fact]
    public void Verify_RejectsMaximumLength()
    {
        byte[] signed = ReplayChecksum.Sign(CreateEvfWithEmptyChecksumField(new byte[] { 1, 2, 3 }));
        int lengthOffset = signed.Length - 34;
        signed[lengthOffset] = 0xFF;
        signed[lengthOffset + 1] = 0xFF;

        Assert.False(ReplayChecksum.Verify(signed));
    }

    [Fact]
    public void Verify_RejectsTrailingGarbage()
    {
        byte[] signed = ReplayChecksum.Sign(CreateEvfWithEmptyChecksumField(new byte[] { 1, 2, 3 }));
        byte[][] trailingGarbage =
        {
            new byte[] { 0x00 },
            new byte[] { 0xFF },
            new byte[] { 0x00, 0x00 },
            new byte[] { 0x20, 0x00 },
            new byte[] { 0xDE, 0xAD, 0xBE, 0xEF }
        };

        for (int index = 0; index < trailingGarbage.Length; index++)
            Assert.False(ReplayChecksum.Verify(AppendTrailingBytes(signed, trailingGarbage[index])));
    }

    [Fact]
    public void Sign_AllZeroPrefixRoundTrips()
    {
        var payload = new byte[257];
        byte[] evf = CreateEvfWithEmptyChecksumField(payload);
        byte[] signed = ReplayChecksum.Sign(evf);
        int payloadLength = evf.Length - 2;

        Assert.True(ReplayChecksum.Verify(signed));
        Assert.Equal(ReplayChecksum.GetChecksum(CopyEdgeRange(evf, 0, payloadLength)),
            CopyEdgeRange(signed, payloadLength + 2, 32));
    }

    [Fact]
    public void Sign_AllOnesPrefixRoundTrips()
    {
        var payload = new byte[257];
        for (int index = 0; index < payload.Length; index++)
            payload[index] = 0xFF;

        byte[] evf = CreateEvfWithEmptyChecksumField(payload);
        byte[] signed = ReplayChecksum.Sign(evf);
        int payloadLength = evf.Length - 2;

        Assert.True(ReplayChecksum.Verify(signed));
        Assert.Equal(ReplayChecksum.GetChecksum(CopyEdgeRange(evf, 0, payloadLength)),
            CopyEdgeRange(signed, payloadLength + 2, 32));
    }

    [Fact]
    public void SignAndVerify_OneMillionBytePayload()
    {
        const int payloadLength = 1000000;
        var payload = new byte[payloadLength];
        for (int index = 0; index < payload.Length; index++)
            payload[index] = (byte)((index * 131) ^ (index >> 8));

        byte[] evf = CreateEvfWithEmptyChecksumField(payload);
        byte[] signed = ReplayChecksum.Sign(evf);
        int signedPayloadLength = signed.Length - 34;

        Assert.Equal(evf.Length + 32, signed.Length);
        Assert.Equal(0, signed[signedPayloadLength]);
        Assert.Equal(0x20, signed[signedPayloadLength + 1]);
        Assert.True(ReplayChecksum.Verify(signed));
    }

    [Fact]
    public void GetSelfKey_IsStableAcrossCallsAndReturnsDefensiveCopies()
    {
        const int callCount = 32;
        byte[] baseline = ReplayChecksum.GetSelfKey();
        var keys = new byte[callCount][];

        Parallel.For(0, callCount, index => keys[index] = ReplayChecksum.GetSelfKey());

        for (int index = 0; index < keys.Length; index++)
        {
            Assert.Equal(baseline, keys[index]);
            Assert.NotSame(baseline, keys[index]);
            if (index > 0)
                Assert.NotSame(keys[index - 1], keys[index]);
        }

        Array.Clear(keys[0], 0, keys[0].Length);
        Assert.Equal(baseline, ReplayChecksum.GetSelfKey());
        Assert.Equal(baseline, ReplayChecksum.GetSelfKey());
    }

    [Fact]
    public void GetChecksum_EmptyInputMatchesKnownHmacSha256Answer()
    {
        var expected = HexToEdgeBytes(
            "B975EC9AE5A0E85653BBCB68682B4DC289AE50DA399B5AB850536DE39B50421A");
        byte[] empty = new byte[0];
        byte[] actual = ReplayChecksum.GetChecksum(empty);

        Assert.Equal(expected, actual);
        Assert.True(ReplayChecksum.ValidChecksum(empty, expected));

        using (var hmac = new HMACSHA256(ReplayChecksum.GetSelfKey()))
            Assert.Equal(expected, hmac.ComputeHash(empty));
    }

    private static byte[] CreateEvfWithEmptyChecksumField(byte[] payload)
    {
        var evf = new byte[payload.Length + 3];
        Buffer.BlockCopy(payload, 0, evf, 0, payload.Length);
        return evf;
    }

    private static byte[] CopyEdgeRange(byte[] source, int offset, int length)
    {
        var result = new byte[length];
        Buffer.BlockCopy(source, offset, result, 0, length);
        return result;
    }

    private static byte[] AppendTrailingBytes(byte[] source, byte[] trailingBytes)
    {
        var result = new byte[source.Length + trailingBytes.Length];
        Buffer.BlockCopy(source, 0, result, 0, source.Length);
        Buffer.BlockCopy(trailingBytes, 0, result, source.Length, trailingBytes.Length);
        return result;
    }

    private static byte[] HexToEdgeBytes(string value)
    {
        var result = new byte[value.Length / 2];
        for (int index = 0; index < result.Length; index++)
            result[index] = Convert.ToByte(value.Substring(index * 2, 2), 16);
        return result;
    }
}
