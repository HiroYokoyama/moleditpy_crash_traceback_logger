# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 Hiromichi Yokoyama
"""Record crash-time Python tracebacks for an optional Moleditpy diagnostic session."""

import datetime
import faulthandler
import logging
import os
from pathlib import Path
import sys

PLUGIN_NAME = "Crash Traceback Logger"
PLUGIN_VERSION = "0.1.0"
PLUGIN_AUTHOR = "HiroYokoyama"
PLUGIN_DESCRIPTION = "Records crash-time Python tracebacks to a local log for troubleshooting."
PLUGIN_CATEGORY = "Utility"
PLUGIN_TAGS = ["Utility"]
PLUGIN_SUPPORTED_MOLEDITPY_VERSION = ">=5.0.0, <6.0.0"
PLUGIN_SUPPORTED_PYTHON_VERSION = ">=3.9, <3.15"
PLUGIN_SUPPORTED_OS = ["Windows", "macOS", "Linux", "WSL"]
PLUGIN_DEPENDENCIES = []
PLUGIN_LICENSE = "LGPL-3.0-or-later"

_LOGGER = logging.getLogger(__name__)
_FD = None


def initialize(context):
    """Enable local logging once, preserving any pre-existing fault handler."""
    global _FD
    if _FD is not None or faulthandler.is_enabled():
        return

    descriptor = None
    try:
        folder = Path.home() / ".moleditpy"
        folder.mkdir(parents=True, exist_ok=True)
        log_path = folder / "faulthandler.log"
        descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        timestamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        with os.fdopen(descriptor, "a", encoding="utf-8", closefd=False) as handle:
            handle.write(
                f"=== Moleditpy crash logging {timestamp} pid={os.getpid()} "
                f"plugin={PLUGIN_VERSION} python={sys.version.split()[0]} ===\n"
            )
            handle.flush()
        faulthandler.enable(file=descriptor, all_threads=True)
    except (OSError, RuntimeError, ValueError):
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        _LOGGER.warning("Could not enable crash traceback logging.", exc_info=True)
        return

    # Deliberately retain one descriptor until OS process cleanup. Closing it or
    # disabling the handler in atexit would miss later finalization crashes.
    _FD = descriptor
    _LOGGER.info("Crash traceback logging enabled: %s", log_path)
