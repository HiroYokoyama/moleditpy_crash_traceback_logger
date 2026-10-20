# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 Hiromichi Yokoyama
"""Record crash-time Python tracebacks for an optional Moleditpy diagnostic session."""

import atexit
import datetime
import faulthandler
import logging
import os
from pathlib import Path
import sys

PLUGIN_NAME = "Crash Traceback Logger"
PLUGIN_VERSION = "0.1.0"
PLUGIN_AUTHOR = "Hiromichi Yokoyama"
PLUGIN_DESCRIPTION = "Records crash-time Python tracebacks to a local log for troubleshooting."
PLUGIN_CATEGORY = "Utility"
PLUGIN_TAGS = ["Utility", "Diagnostics"]
PLUGIN_SUPPORTED_MOLEDITPY_VERSION = ">=5.0.0, <6.0.0"
PLUGIN_SUPPORTED_PYTHON_VERSION = ">=3.9, <3.15"
PLUGIN_SUPPORTED_OS = ["Windows", "macOS", "Linux", "WSL"]
PLUGIN_DEPENDENCIES = []
PLUGIN_LICENSE = "LGPL-3.0-or-later"

_LOGGER = logging.getLogger(__name__)
_FH = None


def _shutdown():
    """Disable our handler before closing its file at interpreter shutdown."""
    global _FH
    if _FH is not None:
        faulthandler.disable()
        _FH.close()
        _FH = None


def initialize(context):
    """Enable local logging once, preserving any pre-existing fault handler."""
    global _FH
    if _FH is not None or faulthandler.is_enabled():
        return

    handle = None
    try:
        folder = Path.home() / ".moleditpy"
        folder.mkdir(parents=True, exist_ok=True)
        log_path = folder / "faulthandler.log"
        handle = log_path.open("a", encoding="utf-8")
        timestamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        handle.write(
            f"=== Moleditpy crash logging {timestamp} pid={os.getpid()} "
            f"plugin={PLUGIN_VERSION} python={sys.version.split()[0]} ===\n"
        )
        handle.flush()
        faulthandler.enable(file=handle, all_threads=True)
    except (OSError, RuntimeError, ValueError):
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass  # A failed flush may also fail again during close.
        _LOGGER.warning("Could not enable crash traceback logging.", exc_info=True)
        return

    # faulthandler retains a descriptor, so this object must remain open.
    _FH = handle
    atexit.register(_shutdown)
    _LOGGER.info("Crash traceback logging enabled: %s", log_path)
