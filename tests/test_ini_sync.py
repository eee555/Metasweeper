import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from superGUI import IniConfig


class TestIniSync(TestCase):
    def test_failed_save_preserves_records_and_can_be_retried(self):
        def fail_mid_write(stream):
            stream.write("[B]\n")
            raise OSError("partial write")

        with TemporaryDirectory() as directory:
            path = Path(directory) / "record.ini"
            original = b"[B]\nrtime = 10\n"
            path.write_bytes(original)
            records = IniConfig(path)
            records.set_value("B/rtime", 9)

            for failure in (
                patch.object(records.config, "write", side_effect=fail_mid_write),
                patch.object(os, "fsync", side_effect=OSError("flush failed")),
                patch.object(os, "replace", side_effect=PermissionError("file in use")),
            ):
                with failure, self.assertRaises(OSError):
                    records.sync()
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual(list(path.parent.iterdir()), [path])

            records.sync()
            self.assertEqual(IniConfig(path).value("B/rtime", value_type=int), 9)
