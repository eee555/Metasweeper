# 重写QMainWindow
from mineSweeperVideoPlayer import MineSweeperVideoPlayer
from mainWindowGUI import MainWindow

from PyQt5.QtCore import QTimer, QCoreApplication, Qt, QRect, QUrl
import utils
import ms_toollib as ms
import hashlib
import subprocess
import json, re
from pathlib import Path
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import csv
from datetime import datetime
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QApplication
from mainWindowGUI import MainWindow
from ui.ui_import import Ui_Form as Ui_Import
from ui.uiComponents import RoundQDialog
import superGUI

_translate = QCoreApplication.translate

# 已知的验证程序 MD5（元扫雷 3.2.2）
_KNOWN_IMPORT_MD5S = {
    "3271d11bab9afc8b0a2b9546e13d46cd",
}

# 主进程中导入导出各种格式的逻辑
class MainWindowGUIImportExport(MineSweeperVideoPlayer):
    def __init__(self, MainWindow: MainWindow, args):
        super(MainWindowGUIImportExport, self).__init__(MainWindow, args)

        self.action_stats_csv.triggered.connect(lambda: self._export_csv())
        self.action_textstats_csv.triggered.connect(lambda: self._export_csv(True))
        self.action_meta_dat.triggered.connect(lambda: self._export_meta_dat())
        self.action_meta_all_dat.triggered.connect(lambda: self._export_meta_dat(True))
        self.action_import_3_2_2.triggered.connect(self._import_replays)
        self.action_import_dat.triggered.connect(self._import_stat_dat)

        self.action_copy_array.triggered.connect(lambda: self._copy_board(0))
        self.action_copy_board_file_ascii.triggered.connect(lambda: self._copy_board(2, "ascii"))
        self.action_copy_board_file_emoji.triggered.connect(lambda: self._copy_board(2, "emoji"))
        self.action_copy_image_png.triggered.connect(self._copy_board_image)
        self.action_copy_image_svg.triggered.connect(self._copy_board_svg)

    # ═══════════════════════════════════════════════════════════
    # 复制局面到剪贴板
    # ═══════════════════════════════════════════════════════════

    def _get_board_data(self):
        if self.game_state in ("playing", "ready"):
            return None
        try:
            board = self.label.ms_board.board
            if isinstance(board, ms.SafeBoard):
                board = board.into_vec_vec()
            game_board = self.label.ms_board.game_board
        except AttributeError:
            return None
        if not board:
            return None
        return board, game_board

    def _copy_board(self, copy_format: int, render: str = "ascii"):
        from utils.board_format import copy_board_to_clipboard
        data = self._get_board_data()
        if data is None:
            return
        board, game_board = data
        copy_board_to_clipboard(
            board, game_board,
            self.row, self.column, self.minenum,
            self.gameMode, copy_format,
            author=self.player_identifier, render=render,
        )

    def _copy_board_image(self):
        if self.game_state in ("playing", "ready"):
            return
        import tempfile, os
        from PyQt5.QtCore import QMimeData, QUrl
        from PyQt5.QtGui import QPixmap, QPainter
        from PyQt5.QtWidgets import QApplication
        pixmap = QPixmap(self.centralwidget.size())
        pixmap.fill(self.centralwidget.palette().window().color())
        painter = QPainter(pixmap)
        self.centralwidget.render(painter)
        painter.end()
        path = os.path.join(tempfile.gettempdir(), "metasweeper_board.png")
        pixmap.save(path, "PNG")
        mime = QMimeData()
        mime.setImageData(pixmap.toImage())
        mime.setUrls([QUrl.fromLocalFile(path)])
        QApplication.clipboard().setMimeData(mime)

    def _copy_board_svg(self):
        if self.game_state in ("playing", "ready"):
            return
        import tempfile, os
        from PyQt5.QtCore import QBuffer, QUrl, QRectF, QMimeData, QPoint
        from PyQt5.QtSvg import QSvgGenerator, QSvgRenderer
        from PyQt5.QtGui import QPainter, QPixmap
        from PyQt5.QtWidgets import QApplication
        label = self.label
        pix_size = label.pixSize
        game_board = label.ms_board.game_board
        rows = len(game_board)
        cols = len(game_board[0])
        cell_paths = {
            0: label.celldown_path, 1: label.cell1_path, 2: label.cell2_path,
            3: label.cell3_path, 4: label.cell4_path, 5: label.cell5_path,
            6: label.cell6_path, 7: label.cell7_path, 8: label.cell8_path,
            10: label.cellup_path, 11: label.cellflag_path,
            14: label.falsemine_path, 15: label.blast_path,
            16: label.cellmine_path, 100: label.mine_path,
        }
        renderers = {}
        for val, path in cell_paths.items():
            if os.path.exists(path):
                renderers[val] = QSvgRenderer(path)
        board_origin = label.mapTo(self.centralwidget, QPoint(0, 0))
        buf = QBuffer()
        buf.open(QBuffer.WriteOnly)
        gen = QSvgGenerator()
        gen.setOutputDevice(buf)
        gen.setSize(self.centralwidget.size())
        gen.setViewBox(self.centralwidget.rect())
        painter = QPainter(gen)
        painter.fillRect(self.centralwidget.rect(), self.centralwidget.palette().window())
        self.centralwidget.render(painter)
        for i in range(rows):
            for j in range(cols):
                cell = game_board[i][j]
                r = renderers.get(cell)
                if r:
                    x = board_origin.x() + j * pix_size
                    y = board_origin.y() + i * pix_size
                    r.render(painter, QRectF(x, y, pix_size, pix_size))
        painter.end()
        svg_bytes = bytes(buf.data())
        buf.close()
        svg_text = svg_bytes.decode("utf-8")
        svg_path = os.path.join(tempfile.gettempdir(), "metasweeper_board.svg")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_text)
        preview = QPixmap(self.centralwidget.size())
        preview.fill(self.centralwidget.palette().window().color())
        painter = QPainter(preview)
        self.centralwidget.render(painter)
        painter.end()
        mime = QMimeData()
        mime.setText(svg_text)
        mime.setImageData(preview.toImage())
        mime.setUrls([QUrl.fromLocalFile(svg_path)])
        QApplication.clipboard().setMimeData(mime)

    # ═══════════════════════════════════════════════════════════
    # 导入录像（从其他版本导入历史记录到 stats.dat）
    # ═══════════════════════════════════════════════════════════

    def _import_replays(self):
        """导入其他版本录像"""
        dialog = ImportDialog(self.mainWindow)
        dialog.set_import_callback(self._import_workflow)
        dialog.exec_()

    def _import_workflow(self, exe_path: str, replay_path: str,
                         progress_bar, label) -> bool:
        """完整导入流程（在对话框内执行，带进度条）"""

        exe = Path(exe_path)
        rp = Path(replay_path)
        if not exe.exists() or not rp.exists():
            QMessageBox.warning(self.mainWindow, _translate("MainWindow", "导入失败"),
                                _translate("MainWindow", "路径不存在"))
            return False

        progress_bar.setRange(0, 1)
        progress_bar.setValue(0)
        label.setText(_translate("Form", "正在验证程序..."))
        label.setVisible(True)
        QApplication.processEvents()

        try:
            actual_md5 = hashlib.md5(exe.read_bytes()).hexdigest()
        except Exception:
            QMessageBox.warning(self.mainWindow, _translate("MainWindow", "导入失败"),
                                _translate("MainWindow", "无法读取验证程序"))
            return False

        if actual_md5 not in _KNOWN_IMPORT_MD5S:
            QMessageBox.warning(self.mainWindow, _translate("MainWindow", "导入失败"),
                                _translate("MainWindow", "未知的验证程序版本"))
            return False

        label.setText(_translate("Form", "正在验证录像..."))
        QApplication.processEvents()

        def on_parse_progress(cur, total):
            progress_bar.setRange(0, total)
            progress_bar.setValue(cur)
            label.setText(_translate("Form", "正在解析录像 {cur}/{total}...")
                          .replace("{cur}", str(cur)).replace("{total}", str(total)))
            QApplication.processEvents()

        preview = self._validate_with_exe(exe, replay_path,
                                          progress_callback=on_parse_progress)
        if preview is None:
            QMessageBox.warning(self.mainWindow, _translate("MainWindow", "导入失败"),
                                _translate("MainWindow", "验证失败"))
            return False

        if not preview["entries"]:
            QMessageBox.information(self.mainWindow, _translate("MainWindow", "导入"),
                                    _translate("MainWindow", "没有新的录像需要导入"))
            return True

        entries = preview["entries"]

        def on_write_progress(cur, total):
            progress_bar.setRange(0, total)
            progress_bar.setValue(cur)
            label.setText(_translate("Form", "正在写入 stats.dat  {cur}/{total}...")
                          .replace("{cur}", str(cur)).replace("{total}", str(total)))
            QApplication.processEvents()

        count = self._do_import_replays(preview, progress_callback=on_write_progress)

        label.setText(_translate("Form", "完成！"))
        progress_bar.setValue(progress_bar.maximum())
        QApplication.processEvents()

        msg = _translate("MainWindow", "成功导入 {n} 条录像").replace("{n}", str(count))
        QMessageBox.information(self.mainWindow, _translate("MainWindow", "导入成功"), msg)
        return True

    def _validate_with_exe(self, exe: Path, replay_path: str,
                           progress_callback: callable = None) -> dict | None:
        """运行验证程序并解析结果"""
        try:
            cmd = [str(exe), "-c", replay_path]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode != 0:
                return None

            out_path = exe.parent / "_internal" / "out.json"
            if not out_path.exists():
                return None

            report = json.loads(out_path.read_bytes())
            if report.get("error"):
                return None

            stats_md5s = self._read_stats_dat_short_md5s()

            data = report.get("data", [])
            total_valid = sum(1 for d in data if d.get("status") == 0)
            processed = 0
            entries = []
            for d in data:
                if d.get("status") != 0:
                    continue
                processed += 1
                if progress_callback:
                    progress_callback(processed, total_valid)
                fp = d["file"]
                fp_path = Path(fp)
                if not fp_path.is_absolute():
                    rp = Path(replay_path)
                    fp_path = (rp if rp.is_dir() else rp.parent) / fp
                try:
                    v = ms.EvfVideo(str(fp_path))
                    v.parse()
                    v.analyse()

                    with open(str(fp_path), "rb") as fh:
                        file_bytes = fh.read()
                    short_md5 = hashlib.md5(file_bytes).digest()[:8]

                    if short_md5 in stats_md5s:
                        continue

                    entries.append({
                        "short_md5": short_md5,
                        "record": utils.StatsRecord(
                            game_state=6,
                            row=v.row,
                            column=v.column,
                            mine_num=v.mine_num,
                            rtime_ms=int(v.rtime * 1000),
                            left=getattr(v, "left", 0),
                            right=getattr(v, "right", 0),
                            double=getattr(v, "double", 0),
                            rce=getattr(v, "rce", 0),
                            lce=getattr(v, "lce", 0),
                            dce=getattr(v, "dce", 0),
                            bbbv=getattr(v, "bbbv", 0),
                            bbbv_solved=getattr(v, "bbbv_solved", 0),
                            zini=getattr(v, "zini", 0),
                            flag=getattr(v, "flag", 0),
                            path=getattr(v, "path", 0.0),
                            start_time=v.start_time,
                            mode=getattr(v, "mode", 0),
                            is_official=getattr(v, "is_official", True),
                            is_fair=getattr(v, "is_fair", True),
                            op=getattr(v, "op", 0),
                            isl=getattr(v, "isl", 0),
                            pluck=getattr(v, "pluck", 0.0),
                            short_md5=short_md5,
                            board_bytes=utils.board_list_to_bytes(v.board),
                        ),
                    })
                except Exception:
                    continue

            return {"entries": entries}
        except subprocess.TimeoutExpired:
            return None
        except Exception:
            return None


    def _do_import_replays(self, preview: dict, progress_callback: callable = None) -> int:
        """将验证通过的录像写入 stats.dat，返回成功条数"""
        entries = preview["entries"]
        count = 0
        dat_path = self.setting_path / "stats.dat"

        for i, entry in enumerate(entries):
            if progress_callback:
                progress_callback(i + 1, len(entries))
            record = entry["record"]
            binary_data = record.encode()
            nonce = get_random_bytes(12)
            cipher = AES.new(superGUI.STATS_DAT_KEY, AES.MODE_GCM, nonce=nonce)
            ciphertext, tag = cipher.encrypt_and_digest(binary_data)

            if (not dat_path.exists()) or dat_path.stat().st_size == 0:
                with open(dat_path, "wb") as f:
                    f.write((0).to_bytes(1, byteorder="big"))

            with open(dat_path, "ab") as f:
                blob = nonce + tag + ciphertext
                f.write(len(blob).to_bytes(2, byteorder="big", signed=False))
                f.write(blob)

            count += 1

        return count



    # ═══════════════════════════════════════════════════════════
    # 导入 stats.dat（从旧版本导入记录合并到当前 stats.dat）
    # ═══════════════════════════════════════════════════════════

    def _import_stat_dat(self):
        """导入旧版 stats.dat 并合并到当前"""
        file_path, _ = QFileDialog.getOpenFileName(
            self.mainWindow, _translate("MainWindow", "选择旧版 stats.dat"),
            str(self.setting_path),
            _translate("MainWindow", "DAT 文件 (stats.dat *.dat);;所有文件 (*)")
        )
        if not file_path:
            return

        old_path = Path(file_path)
        if old_path == self.setting_path / "stats.dat":
            QMessageBox.warning(self.mainWindow, _translate("MainWindow", "导入失败"), _translate("MainWindow", "不能导入当前正在使用的 stats.dat"))
            return

        records = self._read_dat_records(old_path)
        if records is None:
            return

        if not records:
            QMessageBox.information(self.mainWindow, _translate("MainWindow", "导入"), _translate("MainWindow", "旧版 stats.dat 中没有有效记录"))
            return

        existing_md5s = self._read_stats_dat_short_md5s()
        new_records = [r for r in records if r.short_md5 not in existing_md5s]

        if not new_records:
            QMessageBox.information(self.mainWindow, _translate("MainWindow", "导入"),
                                    _translate("MainWindow", "共 {n} 条记录，全部与当前重复").replace("{n}", str(len(records))))
            return

        count = self._do_import_entries(new_records)

        msg = _translate("MainWindow", "成功导入 {n} 条记录").replace("{n}", str(count))
        if len(records) != len(new_records):
            msg += _translate("MainWindow", "，跳过 {n} 条重复").replace("{n}", str(len(records) - len(new_records)))
        QMessageBox.information(self.mainWindow, _translate("MainWindow", "导入成功"), msg)

    def _read_dat_records(self, path: Path) -> list | None:
        """读取 stats.dat 所有记录，根据版本号派发；返回 None 表示版本不支持"""
        if not path.exists() or path.stat().st_size == 0:
            return []

        try:
            with open(path, "rb") as f:
                version = f.read(1)
            if not version:
                return []
            version = version[0]
        except Exception:
            return None

        if version == 0:
            return self._read_dat_records_v0(path, superGUI.STATS_DAT_KEY)
        else:
            QMessageBox.warning(self.mainWindow, _translate("MainWindow", "导入失败"),
                                _translate("MainWindow", "不支持的 stats.dat 版本 (v{ver})，请升级程序").replace("{ver}", str(version)))
            return None

    def _read_dat_records_v0(self, path: Path, key) -> list:
        """读取 v0 格式 stats.dat"""
        records = []
        with open(path, "rb") as f:
            f.read(1)
            while True:
                len_bytes = f.read(2)
                if not len_bytes or len(len_bytes) < 2:
                    break
                blob_length = int.from_bytes(len_bytes, 'big')
                blob = f.read(blob_length)
                if not blob or len(blob) < blob_length:
                    break

                nonce = blob[:12]
                tag = blob[12:28]
                ciphertext = blob[28:]

                try:
                    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
                    plaintext = cipher.decrypt_and_verify(ciphertext, tag)
                    records.append(utils.StatsRecord.decode(plaintext))
                except Exception:
                    continue
        return records

    def _do_import_entries(self, records: list) -> int:
        """将记录列表写入当前 stats.dat，返回成功条数"""
        dat_path = self.setting_path / "stats.dat"
        count = 0
        for rec in records:
            binary_data = rec.encode()
            nonce = get_random_bytes(12)
            cipher = AES.new(superGUI.STATS_DAT_KEY, AES.MODE_GCM, nonce=nonce)
            ciphertext, tag = cipher.encrypt_and_digest(binary_data)

            if (not dat_path.exists()) or dat_path.stat().st_size == 0:
                with open(dat_path, "wb") as f:
                    f.write((0).to_bytes(1, byteorder="big"))

            with open(dat_path, "ab") as f:
                blob = nonce + tag + ciphertext
                f.write(len(blob).to_bytes(2, byteorder="big", signed=False))
                f.write(blob)

            count += 1
        return count


    def _export_csv(self, all=False):
        '''
        # 导出 Arbiter Stats CSV，只导出胜利、标准、正式、公平、非自定义的记录
        '''
        dat_path = self.setting_path / 'stats.dat'
        if not dat_path.exists() or dat_path.stat().st_size == 0:
            QMessageBox.warning(self.mainWindow, _translate("MainWindow", "导出失败"), _translate("MainWindow", "stats.dat 不存在或为空"))
            return

        safe_name = re.sub(r'[\\/:*?"<>|] ', '_', self.player_identifier)
        if all:
            default_name = f"{safe_name}_textstats.csv"
            save_path, _ = QFileDialog.getSaveFileName(
                self.mainWindow, _translate("MainWindow", "导出 Arbiter Textstats CSV（全部）"),
                str(self.setting_path / default_name),
                _translate("MainWindow", "Textstats CSV 文件 (*.csv)")
            )
        else:
            default_name = f"{safe_name}_stats.csv"
            save_path, _ = QFileDialog.getSaveFileName(
                self.mainWindow, _translate("MainWindow", "导出 Arbiter Stats CSV"),
                str(self.setting_path / default_name),
                _translate("MainWindow", "Stats CSV 文件 (*.csv)")
            )
        if not save_path:
            return

        records = []
        with open(dat_path, 'rb') as f:
            f.read(1)  # version byte
            while True:
                len_bytes = f.read(2)
                if not len_bytes or len(len_bytes) < 2:
                    break
                blob_length = int.from_bytes(len_bytes, 'big')
                blob = f.read(blob_length)
                if not blob or len(blob) < blob_length:
                    break

                nonce = blob[:12]
                tag = blob[12:28]
                ciphertext = blob[28:]

                try:
                    cipher = AES.new(superGUI.STATS_DAT_KEY, AES.MODE_GCM, nonce=nonce)
                    plaintext = cipher.decrypt_and_verify(ciphertext, tag)
                    records.append(utils.StatsRecord.decode(plaintext))
                except Exception:
                    continue

        if not records:
            QMessageBox.warning(self.mainWindow, _translate("MainWindow", "导出失败"), _translate("MainWindow", "未找到有效的记录"))
            return

        if all:
            headers = [
                "Mode", "Event", "Year", "Month", "Day", "Hour", "Minute", "Second", "Level", "Width", "Height", "Mines", "Time", "Solved 3BV", "3BV", "ZiNi", "HZiNi", "Openings", "Islands", "Left Clicks", "Right Clicks", "Double Clicks", "Left Effective Clicks", "Right Effective Clicks", "Double Effective Clicks", "Path", "Ones", "Twos", "Threes", "Fours", "Fives", "Sixes", "Sevens", "Eights"
            ]
        else:
            headers = [
                "Day", "Month", "Year", "Hour", "Min", "Sec", "mode", "Time", "BBBV", "BBBVs", "style", "cell0", "cell1", "cell2", "cell3", "cell4", "cell5", "cell6", "cell7", "cell8", "Lcl", "Rcl", "Dcl", "Leff", "Reff", "Deff", "Openings", "Islands", "Path", "GZiNi", "HZiNi"
            ]

        with open(save_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            record_num = 0
            for rec in records:
                if not rec.is_fair:
                    continue  # 只导出公平的记录
                if not all:
                    if rec.game_state != 6 or rec.mode != 0:
                        continue  # 只导出胜利的标准记录
                    if not (rec.is_official):
                        continue  # 只导出正式的记录

                if (rec.row, rec.column, rec.mine_num) == (8, 8, 10):
                    mode = "BEG"
                elif (rec.row, rec.column, rec.mine_num) == (16, 16, 40):
                    mode = "INT"
                elif (rec.row, rec.column, rec.mine_num) == (16, 30, 99):
                    mode = "EXP"
                else:
                    mode = "CUS"
                if not all and mode == "CUS":
                    continue  # 非标准模式不导出

                dt = datetime.fromtimestamp(rec.start_time / 1_000_000 + rec.rtime_ms / 1000.0)

                style = "NF" if rec.rce == 0 else "Flag"
                list_board = utils.board_bytes_to_board(rec.row, rec.column, rec.board_bytes)
                board = ms.Board(list_board)

                if all:
                    # 标准0、win74、经典无猜5、强无猜6、弱无猜7、准无猜8、强可猜9、弱可猜10
                    game_mode = ["classic", "", "", "", "win7", "classic no guess", "strict no guess", "weak no guess", "blessing no guess", "guessable no guess", "lucky mode"][rec.mode]

                if all:
                    writer.writerow([
                        game_mode, "win" if rec.game_state == 6 else "blast", dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second,
                        mode, rec.column, rec.row, rec.mine_num, rec.rtime_ms / 1000.0, rec.bbbv_solved, rec.bbbv, rec.zini, board.hzini,
                        board.op, board.isl, rec.left, rec.right, rec.double, rec.lce, rec.rce, rec.dce, rec.path, board.cell1, board.cell2, board.cell3, board.cell4, board.cell5, board.cell6, board.cell7, board.cell8
                    ])
                else:
                    writer.writerow([
                        dt.day, dt.month, dt.year, dt.hour, dt.minute, dt.second,
                        mode, rec.rtime_ms / 1000.0, rec.bbbv, rec.bbbv_solved, style,
                        board.cell0, board.cell1, board.cell2, board.cell3, board.cell4, 
                        board.cell5, board.cell6, board.cell7, board.cell8,
                        rec.left, rec.right, rec.double,
                        rec.lce, rec.rce, rec.dce,
                        board.op, board.isl, rec.path, rec.zini, board.hzini,
                    ])
                record_num += 1

        QMessageBox.information(self.mainWindow, _translate("MainWindow", "导出成功"),
                                _translate("MainWindow", "已导出 {n} 条记录到\n{path}").replace("{n}", str(record_num)).replace("{path}", save_path))

    def _export_meta_dat(self, all = False):
        dat_path = self.setting_path / 'stats.dat'
        if not dat_path.exists() or dat_path.stat().st_size == 0:
            QMessageBox.warning(self.mainWindow, _translate("MainWindow", "导出失败"), _translate("MainWindow", "stats.dat 不存在或为空"))
            return

        safe_name = self.player_identifier.replace(' ', '_')
        if all:
            default_name = f"{safe_name}_meta_all.dat"
            save_path, _ = QFileDialog.getSaveFileName(
                self.mainWindow, _translate("MainWindow", "导出 meta.all.dat"),
                str(self.setting_path / default_name),
                _translate("MainWindow", "Meta All DAT 文件 (*.all.dat)")
            )
        else:
            default_name = f"{safe_name}_meta.dat"
            save_path, _ = QFileDialog.getSaveFileName(
                self.mainWindow, _translate("MainWindow", "导出 meta.dat"),
                str(self.setting_path / default_name),
                _translate("MainWindow", "Meta DAT 文件 (*.dat)")
            )
        if not save_path:
            return

        records = []
        with open(dat_path, 'rb') as f:
            f.read(1)  # version byte
            while True:
                len_bytes = f.read(2)
                if not len_bytes or len(len_bytes) < 2:
                    break
                blob_length = int.from_bytes(len_bytes, 'big')
                blob = f.read(blob_length)
                if not blob or len(blob) < blob_length:
                    break

                nonce = blob[:12]
                tag = blob[12:28]
                ciphertext = blob[28:]

                try:
                    cipher = AES.new(superGUI.STATS_DAT_KEY, AES.MODE_GCM, nonce=nonce)
                    plaintext = cipher.decrypt_and_verify(ciphertext, tag)
                    records.append(utils.StatsRecord.decode(plaintext))
                except Exception:
                    continue

        if not records:
            QMessageBox.warning(self.mainWindow, _translate("MainWindow", "导出失败"), _translate("MainWindow", "未找到有效的记录"))
            return

        if not all:
            export_records = [r for r in records if r.game_state == 6]
        else:
            export_records = records
        if not export_records:
            QMessageBox.warning(self.mainWindow, _translate("MainWindow", "导出失败"), _translate("MainWindow", "未找到记录"))
            return

        with open(save_path, 'wb') as f:
            for record in export_records:
                binary_data = record.encode()
                nonce = get_random_bytes(12)
                cipher = AES.new(superGUI.STATS_DAT_KEY, AES.MODE_GCM, nonce=nonce)
                ciphertext, tag = cipher.encrypt_and_digest(binary_data)
                blob = nonce + tag + ciphertext
                blob_length = len(blob)
                len_bytes = blob_length.to_bytes(2, byteorder="big", signed=False)
                f.write(len_bytes)
                f.write(blob)

        QMessageBox.information(self.mainWindow, _translate("MainWindow", "导出成功"),
                                _translate("MainWindow", "已导出 {n} 条记录到\n{path}").replace("{n}", str(len(export_records))).replace("{path}", save_path))




class ImportDialog(Ui_Import):
    """导入录像对话框：选择验证程序+录像路径，带进度条"""

    def __init__(self, parent=None):
        self.Dialog = RoundQDialog(parent)
        self.setupUi(self.Dialog)
        self.pushButton_browse_exe.clicked.connect(self._browse_exe)
        self.pushButton_browse_file.clicked.connect(self._browse_replay_file)
        self.pushButton_browse_folder.clicked.connect(self._browse_replay_folder)
        self.pushButton_ok.clicked.connect(self._on_ok)
        self.pushButton_cancel.clicked.connect(self.Dialog.close)
        self._callback = None
        self.progressBar.setVisible(False)
        self.label_progress.setVisible(False)

    def set_import_callback(self, cb):
        self._callback = cb

    def _browse_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self.Dialog, _translate("Form", "选择验证程序"), "",
            _translate("Form", "程序 (*.exe);;所有文件 (*)"))
        if path:
            self.lineEdit_exe.setText(path)

    def _browse_replay_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self.Dialog, _translate("Form", "选择录像"), "",
            _translate("Form", "录像文件 (*.evf *.evfs);;所有文件 (*)"))
        if path:
            self.lineEdit_replay.setText(path)

    def _browse_replay_folder(self):
        path = QFileDialog.getExistingDirectory(
            self.Dialog, _translate("Form", "选择录像文件夹"))
        if path:
            self.lineEdit_replay.setText(path)

    def _on_ok(self):
        exe_path = self.lineEdit_exe.text().strip()
        replay_path = self.lineEdit_replay.text().strip()
        if not exe_path or not replay_path:
            QMessageBox.warning(
                self.Dialog, _translate("Form", "提示"),
                _translate("Form", "请选择验证程序和录像路径"))
            return
        self.lineEdit_exe.setEnabled(False)
        self.lineEdit_replay.setEnabled(False)
        self.pushButton_browse_exe.setEnabled(False)
        self.pushButton_browse_file.setEnabled(False)
        self.pushButton_browse_folder.setEnabled(False)
        self.pushButton_ok.setEnabled(False)
        self.pushButton_cancel.setEnabled(False)
        self.progressBar.setVisible(True)
        self.label_progress.setVisible(True)
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()
        self._callback(exe_path, replay_path, self.progressBar, self.label_progress)
        self.Dialog.close()

    def exec_(self):
        return self.Dialog.exec_()
