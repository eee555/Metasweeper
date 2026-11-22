using System;
using System.IO;
using System.Security.Cryptography;
using Xunit;

public class ReplayChecksumTests
{
    [Fact]
    public void GetSelfKey_Returns32Bytes()
    {
        Assert.Equal(32, ReplayChecksum.GetSelfKey().Length);
    }

    [Fact]
    public void GetSelfKey_ReturnsDefensiveCopy()
    {
        byte[] data = { 1, 2, 3, 4 };
        byte[] before = ReplayChecksum.GetChecksum(data);
        byte[] key = ReplayChecksum.GetSelfKey();
        key[0] ^= 0xFF;
        Assert.Equal(before, ReplayChecksum.GetChecksum(data));
    }

    [Fact]
    public void GetSelfKey_EachCallReturnsIndependentCopy()
    {
        byte[] first = ReplayChecksum.GetSelfKey();
        byte[] second = ReplayChecksum.GetSelfKey();
        Assert.NotSame(first, second);
        first[0] ^= 0xFF;
        Assert.Equal(ReplayChecksum.GetSelfKey(), second);
    }

    [Fact]
    public void GetChecksum_NullThrows()
    {
        Assert.Throws<ArgumentNullException>(() => ReplayChecksum.GetChecksum(null));
    }

    [Fact]
    public void GetChecksum_EmptyDataReturns32Bytes()
    {
        Assert.Equal(32, ReplayChecksum.GetChecksum(new byte[0]).Length);
    }

    [Fact]
    public void GetChecksum_IsDeterministic()
    {
        byte[] data = { 1, 2, 3, 4 };
        Assert.Equal(ReplayChecksum.GetChecksum(data), ReplayChecksum.GetChecksum(data));
    }

    [Fact]
    public void GetChecksum_ReturnsIndependentArray()
    {
        byte[] data = { 1, 2, 3 };
        byte[] first = ReplayChecksum.GetChecksum(data);
        byte[] second = ReplayChecksum.GetChecksum(data);
        Assert.NotSame(first, second);
        first[0] ^= 0xFF;
        Assert.Equal(ReplayChecksum.GetChecksum(data), second);
    }

    [Fact]
    public void GetChecksum_MatchesKnownAnswerVector()
    {
        byte[] data = { 4, 0, 0, 3, 3, 10, 16, 1, 2, 3, 4, 5, 0 };
        byte[] expected = Hex("8dc128859f3e18c0fec1c2e2b07b6e077f27dbb167a7a8a575be36fe45d4756f");
        Assert.Equal(expected, ReplayChecksum.GetChecksum(data));
    }

    [Fact]
    public void GetChecksum_UsesHmacSha256WithSelfKey()
    {
        byte[] data = { 9, 8, 7, 6 };
        using (var hmac = new HMACSHA256(ReplayChecksum.GetSelfKey()))
            Assert.Equal(hmac.ComputeHash(data), ReplayChecksum.GetChecksum(data));
    }

    [Fact]
    public void GetChecksum_DifferentInputsDiffer()
    {
        Assert.NotEqual(ReplayChecksum.GetChecksum(new byte[] { 1 }),
            ReplayChecksum.GetChecksum(new byte[] { 2 }));
    }

    [Fact]
    public void ValidChecksum_NullDataReturnsFalse()
    {
        Assert.False(ReplayChecksum.ValidChecksum(null, new byte[32]));
    }

    [Fact]
    public void ValidChecksum_NullChecksumReturnsFalse()
    {
        Assert.False(ReplayChecksum.ValidChecksum(new byte[] { 1 }, null));
    }

    [Theory]
    [InlineData(0)]
    [InlineData(1)]
    [InlineData(31)]
    [InlineData(33)]
    public void ValidChecksum_WrongLengthReturnsFalse(int length)
    {
        Assert.False(ReplayChecksum.ValidChecksum(new byte[] { 1 }, new byte[length]));
    }

    [Fact]
    public void ValidChecksum_AcceptsCorrectChecksum()
    {
        byte[] data = { 1, 2, 3 };
        Assert.True(ReplayChecksum.ValidChecksum(data, ReplayChecksum.GetChecksum(data)));
    }

    [Fact]
    public void ValidChecksum_RejectsTamperedChecksum()
    {
        byte[] data = { 1, 2, 3 };
        byte[] checksum = ReplayChecksum.GetChecksum(data);
        checksum[0] ^= 0xFF;
        Assert.False(ReplayChecksum.ValidChecksum(data, checksum));
    }

    [Fact]
    public void ValidChecksum_RejectsTamperedData()
    {
        byte[] data = { 1, 2, 3 };
        byte[] checksum = ReplayChecksum.GetChecksum(data);
        data[0] ^= 0xFF;
        Assert.False(ReplayChecksum.ValidChecksum(data, checksum));
    }

    [Fact]
    public void Sign_NullThrows()
    {
        Assert.Throws<ArgumentNullException>(() => ReplayChecksum.Sign(null));
    }

    [Fact]
    public void Sign_RejectsMalformedTail()
    {
        byte[][] cases =
        {
            new byte[0],
            new byte[] { 0 },
            new byte[] { 0, 0 },
            new byte[] { 0, 0, 1 },
            new byte[] { 0, 1, 0 },
            new byte[] { 1, 0, 0 }
        };
        foreach (byte[] evf in cases)
            Assert.Throws<InvalidDataException>(() => ReplayChecksum.Sign(evf));
    }

    [Fact]
    public void Sign_MinimalEvfProduces35Bytes()
    {
        byte[] signed = ReplayChecksum.Sign(new byte[] { 0, 0, 0 });
        Assert.Equal(35, signed.Length);
        Assert.True(ReplayChecksum.Verify(signed));
    }

    [Fact]
    public void Sign_AppendsBigEndianLengthAndChecksum()
    {
        byte[] input = Evf(0xAA, 0xBB);
        byte[] signed = ReplayChecksum.Sign(input);
        int payloadLength = input.Length - 2;
        Assert.Equal(input.Length + 32, signed.Length);
        Assert.Equal(0x00, signed[payloadLength]);
        Assert.Equal(0x20, signed[payloadLength + 1]);
        Assert.Equal(ReplayChecksum.GetChecksum(Slice(signed, 0, payloadLength)),
            Slice(signed, payloadLength + 2, 32));
    }

    [Fact]
    public void Sign_PreservesPayloadPrefixAndInput()
    {
        byte[] input = Evf(1, 2, 3, 4, 5);
        byte[] original = (byte[])input.Clone();
        byte[] signed = ReplayChecksum.Sign(input);
        int payloadLength = input.Length - 2;
        Assert.Equal(Slice(input, 0, payloadLength), Slice(signed, 0, payloadLength));
        Assert.Equal(original, input);
    }

    [Fact]
    public void Sign_IsDeterministic()
    {
        byte[] input = Evf(1, 2, 3);
        Assert.Equal(ReplayChecksum.Sign(input), ReplayChecksum.Sign(input));
    }

    [Fact]
    public void Sign_HandlesLargePayload()
    {
        var payload = new byte[10000];
        for (int i = 0; i < payload.Length; i++)
            payload[i] = (byte)(i * 31);
        byte[] input = Evf(payload);
        byte[] signed = ReplayChecksum.Sign(input);
        Assert.Equal(input.Length + 32, signed.Length);
        Assert.True(ReplayChecksum.Verify(signed));
    }

    [Fact]
    public void Sign_RejectsAlreadySignedInput()
    {
        byte[] signed = ReplayChecksum.Sign(Evf(1, 2, 3));
        Assert.Throws<InvalidDataException>(() => ReplayChecksum.Sign(signed));
    }

    [Fact]
    public void Sign_RejectsSignedShapedInput()
    {
        var signedShaped = new byte[35];
        signedShaped[2] = 32;
        Assert.Throws<InvalidDataException>(() => ReplayChecksum.Sign(signedShaped));
    }

    [Fact]
    public void Verify_NullReturnsFalse()
    {
        Assert.False(ReplayChecksum.Verify(null));
    }

    [Theory]
    [InlineData(0)]
    [InlineData(1)]
    [InlineData(33)]
    public void Verify_TooShortReturnsFalse(int length)
    {
        Assert.False(ReplayChecksum.Verify(new byte[length]));
    }

    [Fact]
    public void Verify_RejectsEmptyPayloadSignature()
    {
        var signed = new byte[34];
        signed[1] = 32;
        Buffer.BlockCopy(ReplayChecksum.GetChecksum(new byte[0]), 0, signed, 2, 32);
        Assert.False(ReplayChecksum.Verify(signed));
    }

    [Fact]
    public void Verify_AcceptsMinimalValidSignedEvf()
    {
        var signed = new byte[35];
        signed[2] = 32;
        Buffer.BlockCopy(ReplayChecksum.GetChecksum(new byte[] { 0 }), 0, signed, 3, 32);
        Assert.True(ReplayChecksum.Verify(signed));
    }

    [Fact]
    public void Verify_RejectsSignedPayloadWithoutEventTerminator()
    {
        byte[] payload = { 1 };
        var signed = new byte[payload.Length + 2 + 32];
        Buffer.BlockCopy(payload, 0, signed, 0, payload.Length);
        signed[payload.Length + 1] = 32;
        Buffer.BlockCopy(ReplayChecksum.GetChecksum(payload), 0, signed, payload.Length + 2, 32);
        Assert.False(ReplayChecksum.Verify(signed));
    }

    [Fact]
    public void Verify_DoesNotMutateInput()
    {
        byte[] signed = ReplayChecksum.Sign(Evf(1, 2, 3));
        byte[] original = (byte[])signed.Clone();
        Assert.True(ReplayChecksum.Verify(signed));
        Assert.Equal(original, signed);
    }

    [Fact]
    public void Verify_RejectsEmptyChecksumEvf()
    {
        Assert.False(ReplayChecksum.Verify(Evf(new byte[40])));
    }

    [Fact]
    public void Verify_RejectsTamperedPayload()
    {
        byte[] signed = ReplayChecksum.Sign(Evf(1, 2, 3, 4));
        signed[0] ^= 0xFF;
        Assert.False(ReplayChecksum.Verify(signed));
    }

    [Fact]
    public void Verify_RejectsTamperedChecksum()
    {
        byte[] signed = ReplayChecksum.Sign(Evf(1, 2, 3, 4));
        signed[signed.Length - 1] ^= 0xFF;
        Assert.False(ReplayChecksum.Verify(signed));
    }

    [Fact]
    public void Verify_RejectsTamperedLength()
    {
        byte[] signed = ReplayChecksum.Sign(Evf(1, 2, 3, 4));
        int payloadLength = signed.Length - 34;
        signed[payloadLength + 1] = 31;
        Assert.False(ReplayChecksum.Verify(signed));
    }

    [Fact]
    public void Verify_RejectsTruncatedSignature()
    {
        byte[] signed = ReplayChecksum.Sign(Evf(1, 2, 3, 4));
        Assert.False(ReplayChecksum.Verify(Slice(signed, 0, signed.Length - 1)));
    }

    [Fact]
    public void Verify_RejectsAppendedByte()
    {
        byte[] signed = ReplayChecksum.Sign(Evf(1, 2, 3, 4));
        var extended = new byte[signed.Length + 1];
        Buffer.BlockCopy(signed, 0, extended, 0, signed.Length);
        Assert.False(ReplayChecksum.Verify(extended));
    }

    [Fact]
    public void SignThenVerify_RoundTrips()
    {
        byte[] signed = ReplayChecksum.Sign(Evf(10, 20, 30, 40, 50));
        Assert.True(ReplayChecksum.Verify(signed));
        Assert.True(ReplayChecksum.Verify(signed));
    }

    private static byte[] Evf(params byte[] prefix)
    {
        var result = new byte[prefix.Length + 3];
        Buffer.BlockCopy(prefix, 0, result, 0, prefix.Length);
        return result;
    }

    private static byte[] Slice(byte[] source, int offset, int length)
    {
        var result = new byte[length];
        Buffer.BlockCopy(source, offset, result, 0, length);
        return result;
    }

    private static byte[] Hex(string value)
    {
        var result = new byte[value.Length / 2];
        for (int i = 0; i < result.Length; i++)
            result[i] = Convert.ToByte(value.Substring(i * 2, 2), 16);
        return result;
    }
}
