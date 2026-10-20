"""Lifecycle, metadata and real subprocess traceback checks."""

import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

SOURCE = Path(__file__).resolve().parents[1] / "crash_traceback_logger.py"


def load_plugin():
    spec = importlib.util.spec_from_file_location("crash_traceback_logger", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.plugin = load_plugin()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        self.addCleanup(patch.stopall)
        patch.object(self.plugin.Path, "home", return_value=self.home).start()
        self.enabled = patch.object(self.plugin.faulthandler, "is_enabled", return_value=False).start()
        self.enable = patch.object(self.plugin.faulthandler, "enable").start()
        self.addCleanup(self.close_file)

    def close_file(self):
        if self.plugin._FD is not None:
            os.close(self.plugin._FD)
            self.plugin._FD = None

    def test_creates_directory_header_and_persistent_handle(self):
        self.plugin.initialize(None)
        descriptor = self.plugin._FD
        self.assertIsInstance(descriptor, int)
        os.fstat(descriptor)  # Descriptor still exists after header writer closes.
        self.enable.assert_called_once_with(file=descriptor, all_threads=True)
        text = (self.home / ".moleditpy/faulthandler.log").read_text(encoding="utf-8")
        self.assertIn("pid=", text)
        self.assertIn("plugin=0.1.0", text)
        self.assertIn("python=", text)

    def test_initializing_twice_does_not_duplicate_handler_or_header(self):
        self.plugin.initialize(None)
        self.plugin.initialize(None)
        self.enable.assert_called_once()
        self.assertEqual((self.home / ".moleditpy/faulthandler.log").read_text().count("=== Moleditpy"), 1)

    def test_preserves_preexisting_handler_without_creating_log(self):
        self.enabled.return_value = True
        self.plugin.initialize(None)
        self.enable.assert_not_called()
        self.assertFalse((self.home / ".moleditpy").exists())

    def test_appends_to_existing_log(self):
        folder = self.home / ".moleditpy"
        folder.mkdir()
        path = folder / "faulthandler.log"
        path.write_text("previous crash\n", encoding="utf-8")
        self.plugin.initialize(None)
        self.assertTrue(path.read_text().startswith("previous crash\n=== Moleditpy"))

    def test_unwritable_directory_is_reported_without_starting_handler(self):
        with patch.object(self.plugin.Path, "mkdir", side_effect=PermissionError("denied")):
            with self.assertLogs(self.plugin._LOGGER, level="WARNING"):
                self.plugin.initialize(None)
        self.assertIsNone(self.plugin._FD)
        self.enable.assert_not_called()

    def test_open_failure_is_reported(self):
        with patch.object(self.plugin.os, "open", side_effect=OSError("denied")):
            with self.assertLogs(self.plugin._LOGGER, level="WARNING"):
                self.plugin.initialize(None)
        self.assertIsNone(self.plugin._FD)
        self.enable.assert_not_called()

    def test_write_and_enable_failures_close_handle_and_allow_retry(self):
        for failing_operation in ("write", "flush", "enable"):
            with self.subTest(operation=failing_operation):
                handle = MagicMock()
                handle.__enter__.return_value = handle
                if failing_operation == "enable":
                    self.enable.side_effect = RuntimeError("unsupported")
                else:
                    getattr(handle, failing_operation).side_effect = OSError("disk full")
                with patch.object(self.plugin.os, "open", return_value=12345):
                    with patch.object(self.plugin.os, "fdopen", return_value=handle):
                        with patch.object(self.plugin.os, "close") as close:
                            with self.assertLogs(self.plugin._LOGGER, level="WARNING"):
                                self.plugin.initialize(None)
                            close.assert_called_once_with(12345)
                self.assertIsNone(self.plugin._FD)
                self.enable.side_effect = None
        self.plugin.initialize(None)
        self.assertIsNotNone(self.plugin._FD)

    def test_cleanup_error_does_not_escape_plugin_initialization(self):
        with patch.object(self.plugin.os, "open", return_value=12345):
            with patch.object(self.plugin.os, "fdopen", side_effect=OSError("failed")):
                with patch.object(self.plugin.os, "close", side_effect=OSError("invalid")):
                    with self.assertLogs(self.plugin._LOGGER, level="WARNING"):
                        self.plugin.initialize(None)
        self.assertIsNone(self.plugin._FD)
        self.enable.assert_not_called()

    def test_metadata_is_literal_and_complete(self):
        metadata = {
            node.targets[0].id: ast.literal_eval(node.value)
            for node in ast.parse(SOURCE.read_text(encoding="utf-8")).body
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id.startswith("PLUGIN_")
        }
        self.assertEqual(metadata["PLUGIN_NAME"], "Crash Traceback Logger")
        self.assertEqual(metadata["PLUGIN_VERSION"], "0.1.0")
        self.assertEqual(metadata["PLUGIN_DEPENDENCIES"], [])
        self.assertEqual(metadata["PLUGIN_LICENSE"], "LGPL-3.0-or-later")
        self.assertEqual(metadata["PLUGIN_SUPPORTED_OS"], ["Windows", "macOS", "Linux", "WSL"])
        self.assertEqual(metadata["PLUGIN_SUPPORTED_MOLEDITPY_VERSION"], ">=5.0.0, <6.0.0")
        self.assertEqual(metadata["PLUGIN_SUPPORTED_PYTHON_VERSION"], ">=3.9, <3.15")
        self.assertEqual(metadata["PLUGIN_CATEGORY"], "Utility")
        self.assertEqual(metadata["PLUGIN_TAGS"], ["Utility"])
        self.assertEqual(metadata["PLUGIN_AUTHOR"], "HiroYokoyama")
        self.assertTrue(metadata["PLUGIN_DESCRIPTION"])


class SubprocessTests(unittest.TestCase):
    def run_session(self, fatal=False, shutdown=False):
        with tempfile.TemporaryDirectory() as folder:
            code = f"""
import atexit, faulthandler, importlib.util, pathlib
faulthandler.disable()
spec = importlib.util.spec_from_file_location('crash_traceback_logger', {str(SOURCE)!r})
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
plugin.Path.home = lambda: pathlib.Path({folder!r})
plugin.initialize(None)
def diagnostic_marker():
    faulthandler.dump_traceback(file=plugin._FD, all_threads=True)
diagnostic_marker()
"""
            if fatal:
                # Suppress OS crash dialogs/core files in this isolated test only.
                code += """
import os
if os.name == 'nt':
    import ctypes
    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
else:
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
"""
                if shutdown:
                    # Register the failing callback BEFORE plugin initialization.
                    # A plugin atexit cleanup would then run before this crash.
                    code = code.replace("\nplugin.initialize(None)\n", "\n")
                    code = code.replace("\ndiagnostic_marker()\n", "\n")
                    code += """
def shutdown_crash_marker():
    os.abort()
atexit.register(shutdown_crash_marker)
# Later callbacks run first; removing Python file objects must not close the FD.
atexit.register(lambda: __import__('gc').collect())
plugin.initialize(None)
diagnostic_marker()
"""
                else:
                    code += "os.abort()\n"
            result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=20)
            text = (Path(folder) / ".moleditpy/faulthandler.log").read_text(encoding="utf-8")
            return result, text

    def test_real_handler_writes_traceback_and_exits_cleanly(self):
        result, text = self.run_session()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("diagnostic_marker", text)
        self.assertIn("plugin=0.1.0", text)

    def test_fatal_abort_is_recorded_in_isolated_process(self):
        result, text = self.run_session(fatal=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Fatal Python error", text)
        self.assertIn("<module>", text)

    def test_shutdown_abort_is_still_recorded(self):
        result, text = self.run_session(fatal=True, shutdown=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Fatal Python error", text)
        self.assertIn("shutdown_crash_marker", text)


if __name__ == "__main__":
    unittest.main()
