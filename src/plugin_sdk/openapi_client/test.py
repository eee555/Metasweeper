# -*- coding: utf-8 -*-
"""openapi_client 独立测试脚本

手动运行：python test.py；需要网络（访问 https://openms.top）。

不依赖 pytest，纯脚本结构：测试函数列表 + 逐个执行 + PASS/FAIL 统计。
兼容两种运行位置：
  - 项目根目录:  python src/plugin_sdk/openapi_client/test.py
  - src 目录:    python plugin_sdk/openapi_client/test.py
  - 本文件所在目录: python test.py

认证相关端点在 openapi.json 中尚未声明 securitySchemes，
用户明确认证部分日后再处理，故本脚本仅做 skip/TODO 占位，不测登录写操作。
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path 处理：保证 plugin_sdk 可导入（无论从哪个目录运行）
# plugin_sdk 位于 <项目根>/src/plugin_sdk，因此把 src 目录加入 sys.path
# ---------------------------------------------------------------------------
_SRC_DIR = Path(__file__).resolve().parents[2]  # src/plugin_sdk/openapi_client/test.py -> src/
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from plugin_sdk.openapi_client.errors import ApiClientError, SpecError
from plugin_sdk.openapi_client.openms import (
    AccountLinkCompleteOut,
    CustomPluckRecordOut,
    OpenmsApi,
    Tournament,
    TournamentNewsOut,
    TournamentParticipant,
    TournamentUserRankingOut,
    UserMS,
    UserMS2,
    UserProfile,
    VideoModel2,
    VideoSummaryOut,
    create_client,
)

# 默认站点地址（与库内 DEFAULT_BASE_URL 一致）
BASE_URL = "https://openms.top"


def test_create_client_default() -> str:
    """用例 1: create_client() 默认参数构造成功"""
    client = create_client()
    api = OpenmsApi(client)
    assert api is not None
    return "默认参数构造 client + OpenmsApi 门面成功"


def test_userprofile_get_user_info() -> str:
    """用例 2: 匿名获取 user_id=1 的 UserProfile，且 id == 1"""
    api = OpenmsApi(create_client())
    profile = api.userprofile_get_user_info(user_id=1)
    assert isinstance(profile, UserProfile), f"期望 UserProfile，实际 {type(profile).__name__}"
    assert profile.id == 1, f"期望 id == 1，实际 {profile.id!r}"
    return f"UserProfile(id={profile.id}, username={profile.username!r})"


def test_msuser_get_records() -> str:
    """用例 3: 匿名获取 user_id=1 的 UserMS，且含数值字段 b_timems_std"""
    api = OpenmsApi(create_client())
    ms = api.msuser_get_records(user_id=1)
    assert isinstance(ms, UserMS), f"期望 UserMS，实际 {type(ms).__name__}"
    val = ms.b_timems_std
    assert isinstance(val, (int, float)), f"b_timems_std 期望 int/float，实际 {type(val).__name__}"
    return f"UserMS(b_timems_std={val}) 数值字段校验通过"


def test_tournament_list() -> str:
    """用例 4: tournament_get_tournament_list(category='all') 返回 list[Tournament]"""
    api = OpenmsApi(create_client())
    result = api.tournament_get_tournament_list(category="all")
    assert isinstance(result, list), f"期望 list，实际 {type(result).__name__}"
    assert len(result) > 0, "锦标赛列表为空（服务端可能无数据，如实报告）"
    first = result[0]
    assert isinstance(first, Tournament), (
        f"元素期望 Tournament，实际 {type(first).__name__}"
    )
    return f"返回 {len(result)} 个 Tournament，元素类型校验通过"


def test_create_client_custom_params() -> str:
    """用例 5: 自定义 base_url/timeout 构造 + 一次真实请求成功"""
    client = create_client(base_url=BASE_URL, timeout=15.0)
    api = OpenmsApi(client)
    profile = api.userprofile_get_user_info(user_id=1)
    assert isinstance(profile, UserProfile), f"期望 UserProfile，实际 {type(profile).__name__}"
    return "自定义参数构造成功且请求返回 UserProfile"


def test_spec_error_unknown_operation() -> str:
    """用例 6a: 调用不存在的 operationId -> 期望 SpecError"""
    client = create_client()
    raised: Exception | None = None
    try:
        # 绕过门面，直接在底层 client 上调用必然不存在的 operationId
        client.call("__definitely_not_a_valid_operation_id__")
    except SpecError as exc:
        raised = exc
    except Exception as exc:  # noqa: BLE001
        raised = exc
    assert isinstance(raised, SpecError), (
        f"期望 SpecError，实际 {type(raised).__name__}: {raised}"
    )
    return f"未知的 operationId 抛出 SpecError（{raised}）"


def test_api_error_status_code() -> str:
    """用例 6b: 必然 404/500 的已知端点 -> 期望 ApiClientError 且带 status_code

    videomanager_get_video_info_bulk 站点自身 500（裸 requests 同样 500），
    属于服务端故障，客户端应如实抛出带 status_code 的 ApiClientError。
    """
    api = OpenmsApi(create_client())
    raised: Exception | None = None
    try:
        api.videomanager_get_video_info_bulk(first=1, count=1)
    except ApiClientError as exc:
        raised = exc
    except Exception as exc:  # noqa: BLE001
        raised = exc
    assert isinstance(raised, ApiClientError), (
        f"期望 ApiClientError，实际 {type(raised).__name__}: {raised}"
    )
    assert raised.status_code is not None, (
        f"期望携带 status_code，实际为 None（{raised}）"
    )
    return f"服务端故障端点抛出 ApiClientError(status_code={raised.status_code})"


def test_auth_todo_skip() -> str:
    """用例 7: 认证测试占位（TODO）

    TODO: 认证接口 openapi.json 尚未声明，日后补充。
    此用例仅占位跳过，不执行任何登录/写操作。
    """
    return "SKIP: 认证接口 openapi.json 尚未声明，日后补充"


def test_userprofile_get_user_info_bulk() -> str:
    """用例 8: 匿名批量获取 UserProfile（ids='1'），元素类型与 id 校验"""
    api = OpenmsApi(create_client())
    result = api.userprofile_get_user_info_bulk(ids="1")
    assert isinstance(result, list), f"期望 list，实际 {type(result).__name__}"
    assert len(result) >= 1, "批量查询 ids='1' 应至少返回 1 条"
    first = result[0]
    assert isinstance(first, UserProfile), (
        f"元素期望 UserProfile，实际 {type(first).__name__}"
    )
    assert first.id == 1, f"期望 id == 1，实际 {first.id!r}"
    return f"infobulk(ids='1') 返回 {len(result)} 条 UserProfile，id 校验通过"


def test_userprofile_get_user_identifier() -> str:
    """用例 9: 匿名获取 user_id=1 的 identifier 列表，元素均为 str"""
    api = OpenmsApi(create_client())
    result = api.userprofile_get_user_identifier(user_id=1)
    assert isinstance(result, list), f"期望 list，实际 {type(result).__name__}"
    for item in result:
        assert isinstance(item, str), f"元素期望 str，实际 {type(item).__name__}"
    return f"identifier(user_id=1) 返回 {len(result)} 个 str 元素"


def test_userprofile_get_user_info_updated() -> str:
    """用例 10: 匿名查询 since=0 以来的更新用户 id 列表，元素均为 int"""
    api = OpenmsApi(create_client())
    result = api.userprofile_get_user_info_updated(since=0)
    assert isinstance(result, list), f"期望 list，实际 {type(result).__name__}"
    for item in result:
        assert isinstance(item, int), f"元素期望 int，实际 {type(item).__name__}"
    return f"infoupdated(since=0) 返回 {len(result)} 个 int 元素"


def test_userprofile_get_user_videos() -> str:
    """用例 11: 匿名获取 user_id=1 的录像列表，元素类型 VideoModel2"""
    api = OpenmsApi(create_client())
    result = api.userprofile_get_user_videos(user_id=1)
    assert isinstance(result, list), f"期望 list，实际 {type(result).__name__}"
    if result:
        assert isinstance(result[0], VideoModel2), (
            f"元素期望 VideoModel2，实际 {type(result[0]).__name__}"
        )
    return f"videolist(user_id=1) 返回 {len(result)} 条录像，元素类型校验通过"


def test_userprofile_get_user_avatar() -> str:
    """用例 12: 匿名获取 user_id=1 的头像（二进制响应），客户端应正常返回不抛异常"""
    api = OpenmsApi(create_client())
    result = api.userprofile_get_user_avatar(user_id=1)
    # 头像为二进制响应，客户端解码为 None（不抛异常即视为成功）
    assert result is None, f"二进制头像响应期望返回 None，实际 {result!r}"
    return "avatar(user_id=1) 二进制响应正常返回（None），无异常"


def test_msuser_get_records_abstract() -> str:
    """用例 13: 匿名获取 user_id=1 的 UserMS2 摘要，含数值字段 b_timems_std"""
    api = OpenmsApi(create_client())
    ms = api.msuser_get_records_abstract(user_id=1)
    assert isinstance(ms, UserMS2), f"期望 UserMS2，实际 {type(ms).__name__}"
    val = ms.b_timems_std
    assert isinstance(val, (int, float)), f"b_timems_std 期望 int/float，实际 {type(val).__name__}"
    return f"UserMS2(b_timems_std={val}) 数值字段校验通过"


def test_customranking_player_pluck_records() -> str:
    """用例 14: 匿名查询 player_id=1 的 pluck 记录，返回 list（可为空）"""
    api = OpenmsApi(create_client())
    result = api.customranking_player_pluck_records(player_id=1)
    assert isinstance(result, list), f"期望 list，实际 {type(result).__name__}"
    if result:
        assert isinstance(result[0], CustomPluckRecordOut), (
            f"元素期望 CustomPluckRecordOut，实际 {type(result[0]).__name__}"
        )
    return f"pluck/player(player_id=1) 返回 {len(result)} 条记录（空列表亦合法）"


def test_tournament_get_tournament_news() -> str:
    """用例 15: 匿名获取锦标赛新闻，TournamentNewsOut 含 preparing/ongoing 列表"""
    api = OpenmsApi(create_client())
    news = api.tournament_get_tournament_news()
    assert isinstance(news, TournamentNewsOut), (
        f"期望 TournamentNewsOut，实际 {type(news).__name__}"
    )
    assert isinstance(news.preparing, list) and isinstance(news.ongoing, list), (
        "preparing/ongoing 期望 list 字段"
    )
    return f"get_news 返回 preparing={len(news.preparing)} 条 / ongoing={len(news.ongoing)} 条"


def test_tournament_get_tournament_user_ranking() -> str:
    """用例 16: 匿名获取锦标赛用户排行，TournamentUserRankingOut 含 total 与 data"""
    api = OpenmsApi(create_client())
    ranking = api.tournament_get_tournament_user_ranking()
    assert isinstance(ranking, TournamentUserRankingOut), (
        f"期望 TournamentUserRankingOut，实际 {type(ranking).__name__}"
    )
    assert isinstance(ranking.total, int), f"total 期望 int，实际 {type(ranking.total).__name__}"
    assert isinstance(ranking.data, list), f"data 期望 list，实际 {type(ranking.data).__name__}"
    return f"user-ranking 返回 total={ranking.total}，data {len(ranking.data)} 条"


def test_tournament_get_participant_list() -> str:
    """用例 17: 匿名获取 tournament_id=1 的参赛者列表，元素类型 TournamentParticipant"""
    api = OpenmsApi(create_client())
    result = api.tournament_get_participant_list(tournament_id=1)
    assert isinstance(result, list), f"期望 list，实际 {type(result).__name__}"
    if result:
        assert isinstance(result[0], TournamentParticipant), (
            f"元素期望 TournamentParticipant，实际 {type(result[0]).__name__}"
        )
    return f"participants(tid=1) 返回 {len(result)} 名参赛者，元素类型校验通过"


def test_accountlink_get_account_links() -> str:
    """用例 18: 匿名获取 user_id=1 的账号绑定信息，AccountLinkCompleteOut 含 summary"""
    api = OpenmsApi(create_client())
    links = api.accountlink_get_account_links(user_id=1)
    assert isinstance(links, AccountLinkCompleteOut), (
        f"期望 AccountLinkCompleteOut，实际 {type(links).__name__}"
    )
    assert isinstance(links.summary, list), f"summary 期望 list，实际 {type(links.summary).__name__}"
    return f"accountlink/{{user_id}} 返回 summary {len(links.summary)} 条绑定记录"


def test_common_video_summary() -> str:
    """用例 19: 匿名获取全站录像统计，VideoSummaryOut 含 total 计数"""
    api = OpenmsApi(create_client())
    summary = api.common_video_summary()
    assert isinstance(summary, VideoSummaryOut), (
        f"期望 VideoSummaryOut，实际 {type(summary).__name__}"
    )
    assert isinstance(summary.total, int) and summary.total >= 0, (
        f"total 期望非负 int，实际 {summary.total!r}"
    )
    return f"videosummary 返回 total={summary.total}，统计字段校验通过"


def test_query_param_binding() -> str:
    """用例 20: 客户端行为——查询参数绑定正确性

    infobulk 端点的 ids 为 query 参数：传入 '1,2' 应被正确绑定到 URL 并
    成功解码为 2 条 UserProfile（id 集合 == {1, 2}），即参数绑定与响应
    解码链路均正确。
    """
    api = OpenmsApi(create_client())
    result = api.userprofile_get_user_info_bulk(ids="1,2")
    assert isinstance(result, list), f"期望 list，实际 {type(result).__name__}"
    assert len(result) == 2, f"ids='1,2' 期望返回 2 条，实际 {len(result)} 条"
    ids = {profile.id for profile in result}
    assert ids == {1, 2}, f"期望 id 集合 {{1, 2}}，实际 {ids}"
    return "query 参数 ids='1,2' 绑定正确，解码出 id={1, 2} 两条 UserProfile"


# ---------------------------------------------------------------------------
# Qt 传输层用例（PyQt5 惰性导入；缺失时返回 SKIP 占位）
# ---------------------------------------------------------------------------
def _ensure_qt_app():
    """惰性导入 PyQt5 并确保存在 QApplication（offscreen 平台，无需显示器）

    Returns:
        QApplication 实例；PyQt5 缺失/不可用时返回 None（调用方转 SKIP）
    """
    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:
        return None
    # 无显示环境（CI/远程）也可运行：默认 offscreen 平台
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_qt_transport_user_info() -> str:
    """用例 21: QtNetworkTransport 传输——经 Qt 网络栈获取 user_id=1 的 UserProfile"""
    app = _ensure_qt_app()
    if app is None:
        return "SKIP: PyQt5 不可用（未安装或 QtNetwork 模块缺失），Qt 传输用例跳过"
    from plugin_sdk.openapi_client.transport import QtNetworkTransport

    api = OpenmsApi(create_client(transport=QtNetworkTransport()))
    profile = api.userprofile_get_user_info(user_id=1)
    assert isinstance(profile, UserProfile), (
        f"Qt 传输期望 UserProfile，实际 {type(profile).__name__}"
    )
    assert profile.id == 1, f"Qt 传输期望 id == 1，实际 {profile.id!r}"
    return f"QtNetworkTransport UserProfile(id={profile.id}, username={profile.username!r})"


def test_qt_transport_error_path() -> str:
    """用例 22: Qt 传输的错误路径——服务端故障端点 -> ApiClientError 且带 status_code

    与用例 6b 同一端点（站点自身 500），验证 Qt 传输拿到状态码后
    交由上层客户端统一翻译异常，行为与 requests 传输一致。
    """
    app = _ensure_qt_app()
    if app is None:
        return "SKIP: PyQt5 不可用（未安装或 QtNetwork 模块缺失），Qt 传输用例跳过"
    from plugin_sdk.openapi_client.transport import QtNetworkTransport

    api = OpenmsApi(create_client(transport=QtNetworkTransport()))
    raised: Exception | None = None
    try:
        api.videomanager_get_video_info_bulk(first=1, count=1)
    except ApiClientError as exc:
        raised = exc
    except Exception as exc:  # noqa: BLE001
        raised = exc
    assert isinstance(raised, ApiClientError), (
        f"Qt 传输期望 ApiClientError，实际 {type(raised).__name__}: {raised}"
    )
    assert raised.status_code is not None, (
        f"Qt 传输期望携带 status_code，实际为 None（{raised}）"
    )
    return f"Qt 传输错误路径: ApiClientError(status_code={raised.status_code})"


# ---------------------------------------------------------------------------
# 测试注册表：(名称, 函数, 是否可跳过网络类失败)
# 网络失败不算代码 bug，如实报告并计入 NETWORK_FAIL，不影响 PASS/FAIL 统计口径之外单列。
# ---------------------------------------------------------------------------
NETWORK_FAILURE_MARKERS = (
    "ConnectionError", "ConnectTimeout", "ReadTimeout", "Timeout",
    "NewConnectionError", "MaxRetryError", "getaddrinfo failed",
    "Name or service not known", "timed out", "SSLError",
)


def _looks_like_network_failure(exc: BaseException) -> bool:
    """判断异常是否属于网络环境问题（DNS/超时/连接失败等）"""
    text = f"{type(exc).__name__}: {exc}"
    return any(marker in text for marker in NETWORK_FAILURE_MARKERS)


TESTS: list[tuple[str, Callable[[], str], str]] = [
    ("create_client() 默认参数构造", test_create_client_default, "no"),
    ("userprofile_get_user_info(user_id=1)", test_userprofile_get_user_info, "net"),
    ("msuser_get_records(user_id=1)", test_msuser_get_records, "net"),
    ("tournament_get_tournament_list(category='all')", test_tournament_list, "net"),
    ("create_client() 自定义参数 + 请求", test_create_client_custom_params, "net"),
    ("错误路径: 未知 operationId -> SpecError", test_spec_error_unknown_operation, "no"),
    ("错误路径: 500 站点 -> ApiClientError", test_api_error_status_code, "net"),
    ("认证测试占位 (TODO)", test_auth_todo_skip, "no"),
    ("userprofile_get_user_info_bulk(ids='1')", test_userprofile_get_user_info_bulk, "net"),
    ("userprofile_get_user_identifier(user_id=1)", test_userprofile_get_user_identifier, "net"),
    ("userprofile_get_user_info_updated(since=0)", test_userprofile_get_user_info_updated, "net"),
    ("userprofile_get_user_videos(user_id=1)", test_userprofile_get_user_videos, "net"),
    ("userprofile_get_user_avatar(user_id=1)", test_userprofile_get_user_avatar, "net"),
    ("msuser_get_records_abstract(user_id=1)", test_msuser_get_records_abstract, "net"),
    ("customranking_player_pluck_records(player_id=1)", test_customranking_player_pluck_records, "net"),
    ("tournament_get_tournament_news()", test_tournament_get_tournament_news, "net"),
    ("tournament_get_tournament_user_ranking()", test_tournament_get_tournament_user_ranking, "net"),
    ("tournament_get_participant_list(tournament_id=1)", test_tournament_get_participant_list, "net"),
    ("accountlink_get_account_links(user_id=1)", test_accountlink_get_account_links, "net"),
    ("common_video_summary()", test_common_video_summary, "net"),
    ("客户端行为: query 参数绑定 (infobulk ids='1,2')", test_query_param_binding, "net"),
    ("QtNetworkTransport: userprofile_get_user_info(user_id=1)", test_qt_transport_user_info, "net"),
    ("QtNetworkTransport: 错误路径 (video_info_bulk)", test_qt_transport_error_path, "net"),
]


def main() -> int:
    print("=" * 62)
    print("openapi_client 测试脚本  |  手动运行: python test.py  |  需要网络")
    print(f"站点: {BASE_URL}")
    print("=" * 62)

    passed: list[str] = []
    failed: list[tuple[str, str]] = []
    skipped: list[str] = []
    net_failed: list[tuple[str, str]] = []

    for name, func, kind in TESTS:
        print(f"\n[测试] {name}")
        try:
            detail = func()
            # 返回值以 "SKIP:" 开头视为占位跳过，不计入 PASS
            if detail.startswith("SKIP:"):
                skipped.append(name)
                print(f"  SKIP: {detail.removeprefix('SKIP: ').strip()}")
            else:
                passed.append(name)
                print(f"  PASS: {detail}")
        except AssertionError as exc:
            if kind == "net" and _looks_like_network_failure(exc):
                net_failed.append((name, str(exc)))
                print(f"  NETWORK-FAIL（网络环境问题，非代码 bug）: {exc}")
            else:
                failed.append((name, str(exc)))
                print(f"  FAIL: {exc}")
        except Exception as exc:  # noqa: BLE001
            if kind == "net" and _looks_like_network_failure(exc):
                net_failed.append((name, f"{type(exc).__name__}: {exc}"))
                print(f"  NETWORK-FAIL（网络环境问题，非代码 bug）: {type(exc).__name__}: {exc}")
            else:
                failed.append((name, f"{type(exc).__name__}: {exc}"))
                print(f"  FAIL: {type(exc).__name__}: {exc}")
                traceback.print_exc()
        else:
            pass
        # （SKIP 判定已在结果处理分支内完成）
        # 用例间限流间隔：站点多处 1/s、15/m 限流，避免密集请求触发 429
        time.sleep(0.6)

    # 汇总
    print()
    print("=" * 62)
    print(f"汇总: PASS={len(passed)}  FAIL={len(failed)}  "
          f"NETWORK-FAIL={len(net_failed)}  SKIP={len(skipped)}  "
          f"总计={len(TESTS)}")
    if passed:
        print(f"  通过用例: {'; '.join(passed)}")
    for name, err in failed:
        print(f"  失败用例: {name} -> {err}")
    for name, err in net_failed:
        print(f"  网络失败: {name} -> {err}")
    if skipped:
        print(f"  跳过用例: {'; '.join(skipped)}")
    print("=" * 62)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
