from dialogs import gameScoreBoard


class Board:
    def __init__(self, denominator):
        self.denominator = denominator


class Manager(gameScoreBoard.gameScoreBoardManager):
    def __init__(self, expression):
        self.namespace = {}
        self.score_board_items = [("Test", expression)]
        self.score_board_items_type = [1]

    def update_namespace(self, ms_board, index_type):
        self.namespace["denominator"] = ms_board.denominator


def test_counter_error_does_not_disable_future_evaluation():
    manager = Manager("1 / denominator")

    assert manager.cal_index_value(Board(0), 1) == ["error"]
    assert manager.score_board_items_type == [1]

    assert manager.cal_index_value(Board(2), 1) == ["0.5"]
    assert manager.score_board_items_type == [1]
