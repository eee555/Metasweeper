"""命令行录像合法性校验。

用法：
    metasweeper.exe -c replay.evf
    metasweeper.exe -c replay.evfs
    metasweeper.exe -c replay目录

本工具用于为主进程提供无头命令行用法，以确认录像文件结构完整、内容有效且校验码正确。校验通过即表示录像经过安全模块的有效性检验，可上传至排行网站。

校验结果写入 out.json：status=0 表示文件结构与校验码均通过检查；
status=1 表示校验码不匹配，文件可能被修改或与当前版本不兼容；
status=2 表示录像结构解析失败。进程退出码为 0 仅表示检查流程已经执行，
单文件结论一律以 out.json 为准。

可对单个文件执行检查，也可传入目录批量检查其中的全部 evf/evfs 录像；
每个文件的检查结果都会独立列出，互不影响。
"""

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
                        checksum_ok = ui.checksum_guard.valid_checksum(
                            video.raw_data[: -(len(video.checksum) + 2)],
                            video.checksum,
                        )
                        evf_evfs_files[ide] = (e, 0 if checksum_ok else 1)
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
                        checksum_ok = ui.checksum_guard.valid_checksum(
                            videos[0].evf_video.raw_data, videos[0].checksum)
                        if not checksum_ok:
                            evf_evfs_files[ide] = (e, 1)
                            continue
                        for idcell, cell in enumerate(videos[1:]):
                            checksum_ok = ui.checksum_guard.valid_checksum(
                                cell.evf_video.raw_data +
                                videos[idcell - 1].checksum,
                                cell.evf_video.checksum,
                            )
                            if not checksum_ok:
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
