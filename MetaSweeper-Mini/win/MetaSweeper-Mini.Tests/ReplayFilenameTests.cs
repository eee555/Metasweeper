using System;
using System.Globalization;
using System.IO;
using System.Threading;
using Xunit;

public sealed class ReplayFilenameTests : IDisposable
{
    private readonly string root = Path.Combine(Path.GetTempPath(),
        "MetaSweeper-Mini.ReplayFilename.Tests", Guid.NewGuid().ToString("N"));

    public ReplayFilenameTests()
    {
        Directory.CreateDirectory(root);
    }

    public void Dispose()
    {
        if (Directory.Exists(root))
            Directory.Delete(root, true);
    }

    [Theory]
    [InlineData(0, "b_")]
    [InlineData(1, "i_")]
    [InlineData(2, "e_")]
    [InlineData(9, "c_")]
    public void UsesMetaSweeperLevelPrefixes(int level, string prefix)
    {
        string name = ReplayFilename.Create(level, 1.25, 40, 2.5, "Player", false);

        Assert.StartsWith(prefix, name);
    }

    [Fact]
    public void CreatesMetaSweeperStyleCompletedAndFailedNames()
    {
        string completed = ReplayFilename.Create(1, 12.3456, 40, 3.2, "Player", false);
        string failed = ReplayFilename.Create(2, 0.333, 99, double.NaN, "Player", true);

        Assert.Equal("i_0_12.346_40_3.200_Player", completed);
        Assert.Equal("e_0_0.333_99_nan_Player_fail", failed);
    }

    [Fact]
    public void UsesInvariantDecimalSeparator()
    {
        CultureInfo previous = Thread.CurrentThread.CurrentCulture;
        try
        {
            Thread.CurrentThread.CurrentCulture = new CultureInfo("de-DE");
            Assert.Equal("b_0_1.500_10_2.000_Player",
                ReplayFilename.Create(0, 1.5, 10, 2, "Player", false));
        }
        finally
        {
            Thread.CurrentThread.CurrentCulture = previous;
        }
    }

    [Fact]
    public void MakesPlayerIdentifierSafeForAFileName()
    {
        string value = ReplayFilename.SafeIdentifier(" A/B:C*D?E\"F<G>H|I ");

        Assert.Equal("A_B_C_D_E_F_G_H_I", value);
    }

    [Fact]
    public void AddsNumericSuffixWhenReplayAlreadyExists()
    {
        const string name = "b_0_1.000_10_2.000_Player";
        string first = ReplayFilename.UniquePath(root, name);
        File.WriteAllBytes(first, new byte[] { 1 });
        string second = ReplayFilename.UniquePath(root, name);
        File.WriteAllBytes(second, new byte[] { 2 });
        string third = ReplayFilename.UniquePath(root, name);

        Assert.EndsWith(name + ".evf", first);
        Assert.EndsWith(name + "(2).evf", second);
        Assert.EndsWith(name + "(3).evf", third);
    }
}
