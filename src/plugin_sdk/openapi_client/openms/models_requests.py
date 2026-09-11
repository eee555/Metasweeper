"""合成请求模型（自动生成）

自动生成，勿手改。运行生成脚本重新生成。
"""
from __future__ import annotations

from msgspec import Struct


class AccountlinkCreateAccountLinkIn(Struct):
    platform: str
    identifier: str


class CustomrankingRefreshPluckRankIn(Struct):
    startid: int
    endid: int


class TournamentAllowTournamentIn(Struct):
    id: int


class TournamentCancelTournamentIn(Struct):
    id: int


class TournamentSetTournamentIn(Struct):
    id: int
    start_time: str | None = None
    end_time: str | None = None
    order: int | None = None
    token: str | None = None


class TournamentSetTournamentStaffIn(Struct):
    tournament_id: int
    weight: int | None = None
    host_id: int | None = None


class TournamentValidateTournamentIn(Struct):
    id: int
    valid: bool


class TournamentGscCreateGscParticipantIn(Struct):
    order: int


class TournamentGscFinishGscTaskIn(Struct):
    order: int


class TournamentGscNewGscTournamentIn(Struct):
    id: int
    start_time: str | None = None
    end_time: str | None = None


class TournamentGscRegisterGscParticipantIdentifierIn(Struct):
    identifier: str
    order: int


class TournamentWeeklyCreateWeeklyParticipantIn(Struct):
    id: int


class TournamentWeeklyNewWeeklyTournamentIn(Struct):
    tournament_format: str | None = None


class TournamentWeeklySetWeeklyTournamentIn(Struct):
    id: int
    state: str


class UserprofileUpdateUserAvatarIn(Struct):
    avatar: str


class UserprofileUpdateUserProfileIn(Struct):
    realname: str | None = None
    signature: str | None = None
    firstname: str | None = None
    lastname: str | None = None
