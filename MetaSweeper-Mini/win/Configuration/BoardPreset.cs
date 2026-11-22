internal sealed class BoardPreset
{
    internal readonly int Rows, Columns, Mines;
    internal int Pixels;

    internal BoardPreset(int rows, int columns, int mines, int pixels)
    {
        Rows = rows; Columns = columns; Mines = mines; Pixels = pixels;
    }

    internal bool Matches(int rows, int columns, int mines)
    {
        return Rows == rows && Columns == columns && Mines == mines;
    }
}
