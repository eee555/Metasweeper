"""命令行录像校验。"""

import json
import os
import sys

from PySide6 import QtWidgets
import mainWindowGUI
import mineSweeperGUI
import ms_toollib as ms
from utils.app_logger import logger


def cli_check_file(file_path: str) -> int:
    result = {"error": "", "data": []}
    if not os.path.exists(file_path):
        result["error"] = "file not found"
    else:
        evf_evfs_files = []
        if os.path.isfile(file_path):
            if file_path.endswith((".evf", ".evfs")):
                evf_evfs_files = [os.path.abspath(file_path)]
        elif os.path.isdir(file_path):
            for root, _, files in os.walk(file_path):
                for file in files:
                    if file.endswith((".evf", ".evfs")):
                        evf_evfs_files.append(
                            os.path.abspath(os.path.join(root, file)))

        if not evf_evfs_files:
            result["error"] = "must be evf or evfs files or directory"
        else:
            app = QtWidgets.QApplication(sys.argv)
            mainWindow = mainWindowGUI.MainWindow()
            ui = mineSweeperGUI.MineSweeperGUI(mainWindow, sys.argv)

            for ide, e in enumerate(evf_evfs_files):
                if not ui.checksum_module_ok():
                    result["error"] = "checksum module error"
                    break
                if e.endswith(".evf"):
                    video = ms.EvfVideo(e)
                    try:
                        video.parse()
                    except Exception:
                        logger.warning(
                            "Failed to parse evf file", exc_info=True)
                        evf_evfs_files[ide] = (e, 2)
                    else:
                        checksum = ui.checksum_guard.get_checksum(
                            video.raw_data[: -(len(video.checksum) + 2)]
                        )
                        evf_evfs_files[ide] = (e, 0 if list(
                            video.checksum) == list(checksum) else 1)
                elif e.endswith(".evfs"):
                    videos = ms.Evfs(e)
                    try:
                        videos.parse()
                    except Exception:
                        logger.warning(
                            "Failed to parse evfs file", exc_info=True)
                        evf_evfs_files[ide] = (e, 2)
                    else:
                        if videos.len() <= 0:
                            evf_evfs_files[ide] = (e, 2)
                            continue
                        checksum = ui.checksum_guard.get_checksum(
                            videos[0].evf_video.raw_data)
                        if list(videos[0].checksum) != list(checksum):
                            evf_evfs_files[ide] = (e, 1)
                            continue
                        for idcell, cell in enumerate(videos[1:]):
                            checksum = ui.checksum_guard.get_checksum(
                                cell.evf_video.raw_data +
                                videos[idcell - 1].checksum
                            )
                            if list(cell.evf_video.checksum) != list(checksum):
                                evf_evfs_files[ide] = (e, 1)
                                break
                        else:
                            evf_evfs_files[ide] = (e, 0)
            if not result["error"]:
                result["data"] = [
                    {"file": item[0], "status": item[1]}
                    for item in evf_evfs_files
                    if isinstance(item, tuple) and len(item) == 2
                ]

    if sys.platform == "win32" or not getattr(sys, "frozen", False):
        output_file = os.path.join(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))), "out.json")
    else:
        output_file = os.path.join(os.getcwd(), "out.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return 0
