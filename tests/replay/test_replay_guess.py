import math
from types import SimpleNamespace

import pytest

from replay_analysis.core import ReplayMouseEvent
from replay_analysis.guess import GuessEventManager


class ReplayVideo:
    def __init__(self, states):
        self.states = states
        self.current_event_id = 0

    def analyse_for_features(self, features):
        pass

    @property
    def pluck(self):
        return self.states[self.current_event_id][0]

    @property
    def game_board(self):
        return self.states[self.current_event_id][1].game_board

    @property
    def game_board_poss(self):
        return self.states[self.current_event_id][1].poss


def test_guess_probabilities_use_board_before_each_click():
    initial = SimpleNamespace(
        game_board=[[10, 10, 10, 10], [10, 10, 10, 10]],
        poss=[[0.25] * 4, [0.25] * 4],
    )
    after_safe = SimpleNamespace(
        game_board=[[1, 10, 10, 10], [10, 10, 10, 10]],
        poss=[[0, 0.1, 0.3, 0.3], [0, 0.7, 0.3, 0.3]],
    )
    after_guess = SimpleNamespace(
        game_board=[[1, 1, 10, 10], [10, 10, 10, 10]],
        poss=[[0, 0, 0.2, 0.4], [0, 0.5, 0.2, 0.4]],
    )
    after_second_safe = SimpleNamespace(
        game_board=[[1, 1, 10, 10], [1, 10, 10, 10]],
        poss=[[0, 0, 0.2, 0.4], [0, 0.6, 0.2, 0.4]],
    )
    after_second_guess = SimpleNamespace(
        game_board=[[1, 1, 2, 10], [1, 10, 10, 10]],
        poss=[[0, 0, 0, 0.5], [0, 1, 0, 0.5]],
    )
    first_pluck = -math.log10(0.9)
    final_pluck = first_pluck - math.log10(0.8)
    states = [
        (0, initial),
        (0, after_safe),
        (first_pluck, after_guess),
        (first_pluck, after_second_safe),
        (final_pluck, after_second_guess),
    ]
    video = ReplayVideo(states)
    contexts = [
        SimpleNamespace(
            video=video,
            index=index,
            time=float(index),
            record=SimpleNamespace(prior_game_board=states[max(0, index - 1)][1]),
            mouse=ReplayMouseEvent(None, "lr", column * 16, row * 16, row, column),
        )
        for index, (row, column) in enumerate([(0, 0), (0, 0), (0, 1), (1, 0), (0, 2)])
    ]
    manager = GuessEventManager()
    manager.reset(contexts[0])
    events = [event for context in contexts[1:] for event in manager.handle(context)]

    assert [event.event_index for event in events] == [2, 4]
    assert [event.global_min_probability for event in events] == pytest.approx([0, 0.2])
    assert [event.non_frontier_probability for event in events] == pytest.approx([0.3, 0.4])
    assert [event.pluck_delta for event in events] == pytest.approx([
        -math.log10(0.9), -math.log10(0.8),
    ])
    assert [event.severity() for event in events] == ["warning", "success"]
