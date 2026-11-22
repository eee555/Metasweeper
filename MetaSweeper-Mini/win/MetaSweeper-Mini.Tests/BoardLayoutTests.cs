using System.Drawing;
using Xunit;

public sealed class BoardLayoutTests
{
    // Qt windowsvista layout measurements for the 8 by 8 board.
    [Theory]
    [InlineData(20, 0, true, 200, 324, 48, 30, 16, 6, 4)]
    [InlineData(30, 30, true, 280, 419, 63, 45, 25, 6, 4)]
    [InlineData(50, 50, true, 440, 609, 93, 75, 42, 6, 4)]
    [InlineData(70, 50, true, 608, 811, 127, 105, 59, 8, 6)]
    [InlineData(5, 50, false, 81, 118, 19, 7, 4, 1, 1)]
    public void GeometryMatchesOriginalBoardLayout(int tile, int initialTile, bool showIdentity,
        int width, int height, int statusHeight, int sprite, int digit, int outerEdge, int innerEdge)
    {
        var layout = new BoardLayout(tile, initialTile);
        Assert.Equal(new Size(width, height), layout.ClientSize(8, 8, showIdentity));
        Assert.Equal(statusHeight, layout.StatusHeight);
        Assert.Equal(sprite, layout.SpriteHeight);
        Assert.Equal(digit, layout.DigitWidth);
        Assert.Equal(outerEdge, layout.OuterEdge);
        Assert.Equal(innerEdge, layout.InnerEdge);
        Assert.Equal(10, layout.OuterInset - layout.OuterEdge);
        Assert.Equal(5, layout.StatusInset - layout.InnerEdge);
    }

    [Fact]
    public void HidingIdentityOnlyRemovesItsFixedHeight()
    {
        var layout = new BoardLayout(50, 20);
        Size visible = layout.ClientSize(16, 30, true);
        Size hidden = layout.ClientSize(16, 30, false);
        Assert.Equal(visible.Width, hidden.Width);
        Assert.Equal(41, visible.Height - hidden.Height);
    }
}
