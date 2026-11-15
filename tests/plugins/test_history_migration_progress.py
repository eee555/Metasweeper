"""历史记录插件：旧数据迁移进度条 UI 行为。

覆盖范围：
- 无旧数据迁移时进度条默认隐藏；
- 有界/不确定进度显示；
- 完成/失败/取消（active=False）后隐藏并复位；
- 重译界面时保留进度与阶段状态；
- 输入夹取（clamp）与未知 phase token 兜底。
"""
from __future__ import annotations

import json
import sqlite3

import pytest

import plugins.history.main_widget as main_widget_module
from plugins.history.main_widget import HistoryMainWidget

PHASE_LABELS = {
    "replays": "迁移旧录像数据",
    "verify": "校验迁移数据",
    "boards": "压缩雷图数据",
    "cleanup": "清理低完成率录像",
}
FALLBACK_LABEL = "正在迁移旧数据"


@pytest.fixture
def widget(qtbot, tmp_path):
    db_path = tmp_path / "history.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE history (replay_id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO history (replay_id) VALUES (1)")
    config_path = tmp_path / "columns.json"
    config_path.write_text(json.dumps(["replay_id"]), encoding="utf-8")
    w = HistoryMainWidget(db_path, config_path, page_size="10")
    qtbot.addWidget(w)
    return w


def _is_shown(row_widget) -> bool:
    """未显示父窗口时用 isVisibleTo 判断逻辑可见性。"""
    return not row_widget.isHidden()


def test_progress_hidden_by_default(widget):
    assert _is_shown(widget.migration_progress_row) is False
    assert _is_shown(widget.migration_progress) is False
    assert widget._migration_active is False


def test_determinate_progress_is_shown(widget):
    widget.set_migration_progress(True, done=3, total=10, phase="replays")

    assert _is_shown(widget.migration_progress_row) is True
    assert _is_shown(widget.migration_progress) is True
    assert widget.migration_progress.minimum() == 0
    assert widget.migration_progress.maximum() == 10
    assert widget.migration_progress.value() == 3
    assert widget.migration_progress.format() == "%p%"
    assert widget.migration_label.text() == PHASE_LABELS["replays"]


@pytest.mark.parametrize("phase", ["replays", "verify", "boards", "cleanup"])
def test_each_phase_token_maps_to_label(widget, phase):
    widget.set_migration_progress(True, done=1, total=4, phase=phase)
    assert widget.migration_label.text() == PHASE_LABELS[phase]


def test_unknown_or_empty_phase_uses_fallback_label(widget):
    widget.set_migration_progress(True, done=1, total=4, phase="unknown-token")
    assert widget.migration_label.text() == FALLBACK_LABEL

    widget.set_migration_progress(True, done=1, total=4, phase="")
    assert widget.migration_label.text() == FALLBACK_LABEL


@pytest.mark.parametrize("total", [0, -5])
def test_non_positive_total_is_indeterminate(widget, total):
    widget.set_migration_progress(True, done=7, total=total, phase="boards")

    assert _is_shown(widget.migration_progress_row) is True
    assert widget.migration_progress.minimum() == 0
    assert widget.migration_progress.maximum() == 0
    # 不确定进度不显示百分比文本
    assert widget.migration_progress.format() == ""


def test_done_is_clamped_to_total(widget):
    widget.set_migration_progress(True, done=99, total=10, phase="replays")
    assert widget.migration_progress.value() == 10

    widget.set_migration_progress(True, done=-3, total=10, phase="replays")
    assert widget.migration_progress.value() == 0


def test_deactivating_hides_and_resets_progress(widget):
    widget.set_migration_progress(True, done=5, total=8, phase="verify")
    assert _is_shown(widget.migration_progress_row) is True

    # 成功、失败、取消都由父插件以 active=False 通知
    widget.set_migration_progress(False)

    assert _is_shown(widget.migration_progress_row) is False
    assert _is_shown(widget.migration_progress) is False
    assert widget._migration_active is False
    assert widget._migration_phase == ""
    assert widget.migration_progress.value() == 0
    assert widget.migration_progress.format() == ""
    assert widget.migration_label.text() == ""


def test_retranslate_keeps_progress_and_cached_phase(widget, monkeypatch):
    widget.set_migration_progress(True, done=4, total=9, phase="boards")

    calls: list[str] = []

    def fake_translate(context: str, source: str) -> str:
        calls.append(source)
        return f"[{source}]"

    monkeypatch.setattr(main_widget_module, "_translate", fake_translate)

    widget.retranslateUi()

    # 进度与总量不变
    assert widget.migration_progress.maximum() == 9
    assert widget.migration_progress.value() == 4
    assert _is_shown(widget.migration_progress_row) is True
    # 文案按缓存的 phase token 重新生成
    assert widget._migration_phase == "boards"
    assert widget.migration_label.text() == f"[{PHASE_LABELS['boards']}]"
    assert PHASE_LABELS["boards"] in calls


def test_positional_call_matches_parent_cached_tuple(widget):
    # 父插件缓存的 (active, done, total, phase) 以 *cached 形式投递
    cached = (True, 2, 6, "verify")
    widget.set_migration_progress(*cached)

    assert _is_shown(widget.migration_progress_row) is True
    assert widget.migration_progress.maximum() == 6
    assert widget.migration_progress.value() == 2
    assert widget.migration_label.text() == PHASE_LABELS["verify"]


def test_recreated_widget_applies_parent_cached_state(qtbot, tmp_path, widget):
    # 旧窗口已显示迁移中；父插件持有缓存状态，重建窗口后重新投递
    widget.set_migration_progress(True, done=1, total=5, phase="replays")
    cached = (True, 3, 5, "replays")

    db_path = widget._db_path
    config_path = widget._config_path
    recreated = HistoryMainWidget(db_path, config_path, page_size="10")
    qtbot.addWidget(recreated)
    # 新窗口默认隐藏，直到父插件投递缓存
    assert _is_shown(recreated.migration_progress_row) is False

    recreated.set_migration_progress(*cached)

    assert _is_shown(recreated.migration_progress_row) is True
    assert recreated.migration_progress.maximum() == 5
    assert recreated.migration_progress.value() == 3
    assert recreated.migration_label.text() == PHASE_LABELS["replays"]


def test_repeated_updates_keep_progress_visible(widget):
    # 连续进度更新不应在两次更新之间隐藏进度条
    for done in range(1, 5):
        widget.set_migration_progress(True, done=done, total=4, phase="boards")
        assert _is_shown(widget.migration_progress_row) is True
        assert widget.migration_progress.value() == done

    widget.set_migration_progress(False)
    assert _is_shown(widget.migration_progress_row) is False


def test_non_numeric_counts_do_not_crash(widget):
    # 后端误传字符串/None 时降级为不确定进度而不是抛异常
    widget.set_migration_progress(  # type: ignore[arg-type]
        True, done="abc", total=None, phase="verify")
    assert _is_shown(widget.migration_progress_row) is True
    assert widget.migration_progress.maximum() == 0
    assert widget.migration_progress.value() == 0

    widget.set_migration_progress(True, done="7", total="10",  # type: ignore[arg-type]
                                  phase="verify")
    assert widget.migration_progress.maximum() == 10
    assert widget.migration_progress.value() == 7


def test_shown_widget_visibility_follows_migration_state(widget):
    # 真实 show 之后用 isVisible 验证（父窗口可见时才是真正可见）
    widget.show()
    assert widget.migration_progress.isVisible() is False

    widget.set_migration_progress(True, done=1, total=2, phase="replays")
    assert widget.migration_progress_row.isVisible() is True
    assert widget.migration_progress.isVisible() is True

    widget.set_migration_progress(False)
    assert widget.migration_progress.isVisible() is False
    assert widget.migration_progress_row.isVisible() is False


def test_progress_bar_placed_near_top_of_layout(widget):
    layout = widget.layout()
    assert layout.indexOf(widget.migration_progress_row) == 1


def test_retranslate_does_not_show_hidden_progress(widget, monkeypatch):
    monkeypatch.setattr(
        main_widget_module, "_translate", lambda context, source: source
    )
    widget.retranslateUi()

    assert _is_shown(widget.migration_progress_row) is False
    assert widget.migration_label.text() == ""
