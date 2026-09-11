"""
openms API 客户端（自动生成）

自动生成，勿手改。运行生成脚本重新生成:
    python -m plugin_sdk.openapi_client.generate_openms

用法::

    from plugin_sdk.openapi_client.openms import create_client, OpenmsApi

    client = create_client()                # base_url 默认 https://openms.top
    api = OpenmsApi(client)                 # 端点门面（IDE 补全友好）
    result = api.userprofile_get_user_info(user_id=1)   # 返回 msgspec.Struct 模型实例
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from plugin_sdk.openapi_client.client import SpecDrivenClient, build_model_registry
from plugin_sdk.openapi_client.transport import Transport
from . import models_gen as _models_gen
from .api_endpoints import OpenmsApi
from .models_gen import (
    AccountBilibili,
    AccountLinkCompleteOut,
    AccountLinkCreateIn,
    AccountLinkQueue,
    AccountLinkQueue2,
    AccountMinesweeperGames,
    AccountQQ,
    AccountSaolei,
    AccountWorldOfMinesweeper,
    CustomPluckPlayerOut,
    CustomPluckRankOut,
    CustomPluckRecordOut,
    DBTaskResult,
    DBTaskResult2,
    GSCOrderIn,
    GSCParticipant,
    GSCTournament,
    IdIn,
    LogFileOut,
    LogPollOut,
    LogTailOut,
    NewGSCTournamentIn,
    NewWeeklyTournamentIn,
    NewWeeklyTournamentOut,
    RefreshCustomPluckRankIn,
    RefreshCustomPluckRankOut,
    RegisterGSCParticipantIn,
    RunningTaskHealthOut,
    TaskIdIn,
    Tournament,
    TournamentNewsItemOut,
    TournamentNewsOut,
    TournamentParticipant,
    TournamentSetIn,
    TournamentStaffSetIn,
    TournamentUser,
    TournamentUserRankingOut,
    TournamentValidationIn,
    UpdateUserProfileIn,
    UserMS,
    UserMS2,
    UserProfile,
    VideoModel,
    VideoModel2,
    VideoModel3,
    VideoSummaryOut,
    WeeklyParticipant,
    WeeklyParticipant2,
    WeeklySetIn,
    WeeklyTournament,
)
from .models_requests import (
    AccountlinkCreateAccountLinkIn,
    CustomrankingRefreshPluckRankIn,
    TournamentAllowTournamentIn,
    TournamentCancelTournamentIn,
    TournamentGscCreateGscParticipantIn,
    TournamentGscFinishGscTaskIn,
    TournamentGscNewGscTournamentIn,
    TournamentGscRegisterGscParticipantIdentifierIn,
    TournamentSetTournamentIn,
    TournamentSetTournamentStaffIn,
    TournamentValidateTournamentIn,
    TournamentWeeklyCreateWeeklyParticipantIn,
    TournamentWeeklyNewWeeklyTournamentIn,
    TournamentWeeklySetWeeklyTournamentIn,
    UserprofileUpdateUserAvatarIn,
    UserprofileUpdateUserProfileIn,
)

DEFAULT_BASE_URL = "https://openms.top"

# 缓存的 openapi.json（与本包一起分发，运行期只读）
_SPEC_PATH = Path(__file__).resolve().parent / "openapi.json"


def create_client(
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 10.0,
    user_agent: str = "Metasweeper-Plugin/1.0",
    transport: Transport | None = None,
) -> SpecDrivenClient:
    """创建已就绪的 openms API 客户端

    内部读取随包分发的 openapi.json 缓存、构建模型注册表。

    Args:
        base_url: 站点地址，默认 https://openms.top，可传参覆盖
        timeout: 请求超时秒数
        user_agent: User-Agent 请求头
        transport: 自定义传输层实现（如 QtNetworkTransport）；默认 requests 传输
    """
    spec = json.loads(_SPEC_PATH.read_text(encoding="utf-8"))
    registry = build_model_registry(_models_gen)
    return SpecDrivenClient(
        spec,
        registry,
        base_url=base_url,
        timeout=timeout,
        user_agent=user_agent,
        transport=transport,
    )


__all__ = [
    "create_client",
    "OpenmsApi",
    "AccountBilibili",
    "AccountLinkCompleteOut",
    "AccountLinkCreateIn",
    "AccountLinkQueue",
    "AccountLinkQueue2",
    "AccountMinesweeperGames",
    "AccountQQ",
    "AccountSaolei",
    "AccountWorldOfMinesweeper",
    "CustomPluckPlayerOut",
    "CustomPluckRankOut",
    "CustomPluckRecordOut",
    "DBTaskResult",
    "DBTaskResult2",
    "GSCOrderIn",
    "GSCParticipant",
    "GSCTournament",
    "IdIn",
    "LogFileOut",
    "LogPollOut",
    "LogTailOut",
    "NewGSCTournamentIn",
    "NewWeeklyTournamentIn",
    "NewWeeklyTournamentOut",
    "RefreshCustomPluckRankIn",
    "RefreshCustomPluckRankOut",
    "RegisterGSCParticipantIn",
    "RunningTaskHealthOut",
    "TaskIdIn",
    "Tournament",
    "TournamentNewsItemOut",
    "TournamentNewsOut",
    "TournamentParticipant",
    "TournamentSetIn",
    "TournamentStaffSetIn",
    "TournamentUser",
    "TournamentUserRankingOut",
    "TournamentValidationIn",
    "UpdateUserProfileIn",
    "UserMS",
    "UserMS2",
    "UserProfile",
    "VideoModel",
    "VideoModel2",
    "VideoModel3",
    "VideoSummaryOut",
    "WeeklyParticipant",
    "WeeklyParticipant2",
    "WeeklySetIn",
    "WeeklyTournament",
    "AccountlinkCreateAccountLinkIn",
    "CustomrankingRefreshPluckRankIn",
    "TournamentAllowTournamentIn",
    "TournamentCancelTournamentIn",
    "TournamentGscCreateGscParticipantIn",
    "TournamentGscFinishGscTaskIn",
    "TournamentGscNewGscTournamentIn",
    "TournamentGscRegisterGscParticipantIdentifierIn",
    "TournamentSetTournamentIn",
    "TournamentSetTournamentStaffIn",
    "TournamentValidateTournamentIn",
    "TournamentWeeklyCreateWeeklyParticipantIn",
    "TournamentWeeklyNewWeeklyTournamentIn",
    "TournamentWeeklySetWeeklyTournamentIn",
    "UserprofileUpdateUserAvatarIn",
    "UserprofileUpdateUserProfileIn",
]
