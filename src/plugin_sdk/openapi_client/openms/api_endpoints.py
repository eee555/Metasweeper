"""openms API 端点门面（自动生成）

自动生成，勿手改。运行生成脚本重新生成。
"""
from __future__ import annotations

from typing import Any

from .models_gen import AccountLinkCompleteOut, AccountLinkQueue, CustomPluckRankOut, CustomPluckRecordOut, DBTaskResult, GSCParticipant, GSCTournament, LogFileOut, LogPollOut, LogTailOut, NewWeeklyTournamentOut, RefreshCustomPluckRankOut, RunningTaskHealthOut, TaskIdIn, Tournament, TournamentNewsOut, TournamentParticipant, TournamentUserRankingOut, UserMS, UserMS2, UserProfile, VideoModel, VideoModel2, VideoModel3, VideoSummaryOut, WeeklyParticipant, WeeklyParticipant2
from plugin_sdk.openapi_client.client import SpecDrivenClient


class OpenmsApi:
    """API 端点门面（补全友好层）

    所有方法委托给 SpecDrivenClient 执行实际网络请求。
    """

    def __init__(self, client: SpecDrivenClient) -> None:
        self._client = client

    def accountlink_get_account_link_queue(self) -> list[AccountLinkQueue]:
        """Get Account Link Queue

GET /api/accountlink/admin/queue"""
        return self._client.call("accountlink_api_get_account_link_queue")


    def accountlink_create_account_link(self, body: dict[str, Any]) -> AccountLinkQueue:
        """Create Account Link

POST /api/accountlink/create/"""
        return self._client.call("accountlink_api_create_account_link", body=body)


    def accountlink_get_account_links(self, user_id: int) -> AccountLinkCompleteOut:
        """Get Account Links

GET /api/accountlink/{user_id}"""
        return self._client.call("accountlink_api_get_account_links", user_id=user_id)


    def common_disk_usage(self) -> None:
        """Disk Usage

GET /api/common/diskusage"""
        return self._client.call("common_api_disk_usage")


    def common_poll_log_tail(self, filename: str, offset: int | None = None, tail_bytes: int | None = None) -> LogPollOut:
        """Poll Log Tail

GET /api/common/staff/logpoll"""
        return self._client.call("common_api_poll_log_tail", filename=filename, offset=offset, tail_bytes=tail_bytes)


    def common_list_logs(self) -> list[LogFileOut]:
        """List Logs

GET /api/common/staff/logs"""
        return self._client.call("common_api_list_logs")


    def common_get_log_tail(self, filename: str, tail_bytes: int | None = None) -> LogTailOut:
        """Get Log Tail

GET /api/common/staff/logtail"""
        return self._client.call("common_api_get_log_tail", filename=filename, tail_bytes=tail_bytes)


    def common_download_log(self, filename: str) -> None:
        """Download Log

GET /api/common/staff/logview"""
        return self._client.call("common_api_download_log", filename=filename)


    def common_cleanup_tasks(self) -> int:
        """Cleanup Tasks

POST /api/common/tasks/cleanup"""
        return self._client.call("common_api_cleanup_tasks")


    def common_delete_task(self, body: TaskIdIn) -> None:
        """Delete Task

POST /api/common/tasks/delete"""
        return self._client.call("common_api_delete_task", body=body)


    def common_task_detail(self) -> list[DBTaskResult]:
        """Task Detail

GET /api/common/tasks/detail"""
        return self._client.call("common_api_task_detail")


    def common_restart_task(self, body: TaskIdIn) -> DBTaskResult:
        """Restart Task

POST /api/common/tasks/restart"""
        return self._client.call("common_api_restart_task", body=body)


    def common_running_task_health(self, stale_after_seconds: int | None = None) -> list[RunningTaskHealthOut]:
        """Running Task Health

GET /api/common/tasks/running/health"""
        return self._client.call("common_api_running_task_health", stale_after_seconds=stale_after_seconds)


    def common_task_summary(self) -> None:
        """Task Summary

GET /api/common/tasksummary"""
        return self._client.call("common_api_task_summary")


    def common_video_summary(self) -> VideoSummaryOut:
        """Video Summary

GET /api/common/videosummary"""
        return self._client.call("common_api_video_summary")


    def customranking_pluck_rank(self, level: str, start: int | None = None, end: int | None = None) -> CustomPluckRankOut:
        """Pluck Rank

GET /api/customranking/pluck"""
        return self._client.call("customranking_api_pluck_rank", level=level, start=start, end=end)


    def customranking_player_pluck_records(self, player_id: int) -> list[CustomPluckRecordOut]:
        """Player Pluck Records

GET /api/customranking/pluck/player"""
        return self._client.call("customranking_api_player_pluck_records", player_id=player_id)


    def customranking_refresh_pluck_rank(self, body: dict[str, Any]) -> RefreshCustomPluckRankOut:
        """Refresh Pluck Rank

POST /api/customranking/pluck/refresh"""
        return self._client.call("customranking_api_refresh_pluck_rank", body=body)


    def msuser_get_records(self, user_id: int) -> UserMS:
        """Get Records

GET /api/msuser/records"""
        return self._client.call("msuser_api_get_records", user_id=user_id)


    def msuser_get_records_abstract(self, user_id: int) -> UserMS2:
        """Get Records Abstract

GET /api/msuser/records_abstract"""
        return self._client.call("msuser_api_get_records_abstract", user_id=user_id)


    def tournament_allow_tournament(self, body: dict[str, Any]) -> None:
        """Allow Tournament

POST /api/tournament/allow"""
        return self._client.call("tournament_api_allow_tournament", body=body)


    def tournament_cancel_tournament(self, body: dict[str, Any]) -> None:
        """Cancel Tournament

POST /api/tournament/cancel"""
        return self._client.call("tournament_api_cancel_tournament", body=body)


    def tournament_download_all_videos(self, tournament_id: int) -> None:
        """Download All Videos

GET /api/tournament/download"""
        return self._client.call("tournament_api_download_all_videos", tournament_id=tournament_id)


    def tournament_download_videos_participant(self, tournament_id: int, user_id: int) -> None:
        """Download Videos Participant

GET /api/tournament/download/participant"""
        return self._client.call("tournament_api_download_videos_participant", tournament_id=tournament_id, user_id=user_id)


    def tournament_get_tournament(self, tournament_id: int) -> Tournament:
        """Get Tournament

GET /api/tournament/get"""
        return self._client.call("tournament_api_get_tournament", tournament_id=tournament_id)


    def tournament_get_tournament_list(self, category: str | None = None) -> list[Tournament]:
        """Get Tournament List

GET /api/tournament/get_list"""
        return self._client.call("tournament_api_get_tournament_list", category=category)


    def tournament_get_tournament_news(self) -> TournamentNewsOut:
        """Get Tournament News

GET /api/tournament/get_news"""
        return self._client.call("tournament_api_get_tournament_news")


    def tournament_get_participant_videos(self, tournament_id: int, user_id: int) -> list[VideoModel]:
        """Get Participant Videos

GET /api/tournament/get_videos/participant"""
        return self._client.call("tournament_api_get_participant_videos", tournament_id=tournament_id, user_id=user_id)


    def tournament_get_tournament_videos(self, tournament_id: int) -> list[VideoModel]:
        """Get Tournament Videos

GET /api/tournament/get_videos/tournament"""
        return self._client.call("tournament_api_get_tournament_videos", tournament_id=tournament_id)


    def tournament_gsc_get_GSC_tournament(self, order: int) -> GSCTournament:
        """Get Gsc Tournament

GET /api/tournament/gsc/admin-info"""
        return self._client.call("tournament_gsc_api_get_GSC_tournament", order=order)


    def tournament_gsc_new_GSC_tournament(self, body: dict[str, Any]) -> None:
        """New Gsc Tournament

POST /api/tournament/gsc/new"""
        return self._client.call("tournament_gsc_api_new_GSC_tournament", body=body)


    def tournament_gsc_create_gsc_participant(self, body: dict[str, Any]) -> None:
        """Create Gsc Participant

POST /api/tournament/gsc/participant"""
        return self._client.call("tournament_gsc_api_create_gsc_participant", body=body)


    def tournament_gsc_register_gsc_participant_identifier(self, body: dict[str, Any]) -> None:
        """Register Gsc Participant Identifier

POST /api/tournament/gsc/participant/identifier"""
        return self._client.call("tournament_gsc_api_register_gsc_participant_identifier", body=body)


    def tournament_gsc_get_results(self, tournament_id: int) -> list[GSCParticipant]:
        """Get Results

GET /api/tournament/gsc/results"""
        return self._client.call("tournament_gsc_api_get_results", tournament_id=tournament_id)


    def tournament_gsc_get_gsc_task(self, order: int) -> Any:
        """Get Gsc Task

GET /api/tournament/gsc/task"""
        return self._client.call("tournament_gsc_api_get_gsc_task", order=order)


    def tournament_gsc_finish_gsc_task(self, body: dict[str, Any]) -> None:
        """Finish Gsc Task

POST /api/tournament/gsc/task/finish"""
        return self._client.call("tournament_gsc_api_finish_gsc_task", body=body)


    def tournament_get_participant_list(self, tournament_id: int) -> list[TournamentParticipant]:
        """Get Participant List

GET /api/tournament/participants"""
        return self._client.call("tournament_api_get_participant_list", tournament_id=tournament_id)


    def tournament_set_tournament(self, body: dict[str, Any]) -> None:
        """Set Tournament

POST /api/tournament/set"""
        return self._client.call("tournament_api_set_tournament", body=body)


    def tournament_set_tournament_staff(self, body: dict[str, Any]) -> Tournament:
        """Set Tournament Staff

POST /api/tournament/set_staff"""
        return self._client.call("tournament_api_set_tournament_staff", body=body)


    def tournament_get_tournament_user_ranking(self, sort_by: str | None = None, start: int | None = None, end: int | None = None) -> TournamentUserRankingOut:
        """Get Tournament User Ranking

GET /api/tournament/user-ranking"""
        return self._client.call("tournament_api_get_tournament_user_ranking", sort_by=sort_by, start=start, end=end)


    def tournament_validate_tournament(self, body: dict[str, Any]) -> None:
        """Validate Tournament

POST /api/tournament/validate"""
        return self._client.call("tournament_api_validate_tournament", body=body)


    def tournament_weekly_new_weekly_tournament(self, body: dict[str, Any]) -> NewWeeklyTournamentOut:
        """New Weekly Tournament

POST /api/tournament/weekly/new"""
        return self._client.call("tournament_weekly_api_new_weekly_tournament", body=body)


    def tournament_weekly_create_weekly_participant(self, body: dict[str, Any]) -> WeeklyParticipant2:
        """Create Weekly Participant

POST /api/tournament/weekly/participant"""
        return self._client.call("tournament_weekly_api_create_weekly_participant", body=body)


    def tournament_weekly_get_results(self, tournament_id: int) -> list[WeeklyParticipant]:
        """Get Results

GET /api/tournament/weekly/results"""
        return self._client.call("tournament_weekly_api_get_results", tournament_id=tournament_id)


    def tournament_weekly_set_weekly_tournament(self, body: dict[str, Any]) -> None:
        """Set Weekly Tournament

POST /api/tournament/weekly/set"""
        return self._client.call("tournament_weekly_api_set_weekly_tournament", body=body)


    def userprofile_get_user_avatar(self, user_id: int) -> None:
        """Get User Avatar

GET /api/userprofile/avatar/{user_id}"""
        return self._client.call("userprofile_api_get_user_avatar", user_id=user_id)


    def userprofile_get_user_identifier(self, user_id: int) -> list[str]:
        """Get User Identifier

GET /api/userprofile/identifier"""
        return self._client.call("userprofile_api_get_user_identifier", user_id=user_id)


    def userprofile_get_user_info(self, user_id: int) -> UserProfile:
        """Get User Info

GET /api/userprofile/info/{user_id}"""
        return self._client.call("userprofile_api_get_user_info", user_id=user_id)


    def userprofile_get_user_info_bulk(self, ids: str) -> list[UserProfile]:
        """Get User Info Bulk

GET /api/userprofile/infobulk"""
        return self._client.call("userprofile_api_get_user_info_bulk", ids=ids)


    def userprofile_get_user_info_updated(self, since: int) -> list[int]:
        """Get User Info Updated

GET /api/userprofile/infoupdated"""
        return self._client.call("userprofile_api_get_user_info_updated", since=since)


    def userprofile_update_user_avatar(self, body: dict[str, Any]) -> None:
        """Update User Avatar

POST /api/userprofile/update_avatar"""
        return self._client.call("userprofile_api_update_user_avatar", body=body)


    def userprofile_update_user_profile(self, body: dict[str, Any]) -> None:
        """Update User Profile

POST /api/userprofile/update_profile"""
        return self._client.call("userprofile_api_update_user_profile", body=body)


    def userprofile_get_user_videos(self, user_id: int) -> list[VideoModel2]:
        """Get User Videos

GET /api/userprofile/videolist"""
        return self._client.call("userprofile_api_get_user_videos", user_id=user_id)


    def videomanager_get_video_detail_bulk(self, first: int, count: int) -> list[VideoModel3]:
        """Get Video Detail Bulk

GET /api/video/detailbulk"""
        return self._client.call("videomanager_api_get_video_detail_bulk", first=first, count=count)


    def videomanager_get_video_info_bulk(self, first: int, count: int) -> list[VideoModel]:
        """Get Video Info Bulk

GET /api/video/infobulk"""
        return self._client.call("videomanager_api_get_video_info_bulk", first=first, count=count)


    def videomanager_get_review_queue(self) -> list[VideoModel]:
        """Get Review Queue

GET /api/video/review_queue"""
        return self._client.call("videomanager_api_get_review_queue")
