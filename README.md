# Crash Traceback Logger for Moleditpy

An optional diagnostic plugin that records Python tracebacks when Moleditpy
crashes in native code. It uses Python's standard-library `faulthandler` and
writes directly to a local file, including when the GUI has no visible terminal.
It does not prevent crashes or recover unsaved work.

## Installation

Copy [`crash_traceback_logger.py`](crash_traceback_logger.py) into
`~/.moleditpy/plugins/Utility/` (create the folder if necessary), then restart
Moleditpy. On Windows, `~` normally means `C:\Users\<username>`.

If you previously installed the diagnostic file `crash_traceback_log.py`, remove
that plugin file before installing this one. Install only one copy.

The plugin runs automatically during plugin initialization and adds no menu.
It requires Moleditpy 5.x and Python 3.9–3.14, supports Windows, macOS and Linux
(including WSL), and has no additional package dependencies.

## Read the log

The log is appended to **`~/.moleditpy/faulthandler.log`**. Each enabled session
adds a timestamp with timezone, process ID, plugin version and Python version.
After a crash, inspect the final session and traceback in this file.

Tracebacks can help locate the Python calls active during faults such as
segmentation faults, access violations and aborts. They do not necessarily
identify the defective native library. Recorded output depends on the fault,
Python version and platform; some failures cannot be recorded. The plugin cannot
capture faults before plugin initialization, and does not record ordinary caught
exceptions or detect GUI freezes. Existing fault handlers (for example,
`PYTHONFAULTHANDLER=1` or `python -X faulthandler`) are left unchanged; in that
case this plugin does not start its own file logging.

Logs can contain user names, local file paths and function names. Review and
redact them before sharing. The plugin never uploads logs or makes network
requests. Logging applies to the current process, not separate worker processes.

## Disable and remove logs

Disable **Crash Traceback Logger** in Moleditpy's plugin manager, or remove
`crash_traceback_logger.py` from the plugin folder, then **restart Moleditpy**.
Removing or disabling a plugin does not undo the handler in an already-running
session. Disable the old `crash_traceback_log.py` too, if present.

The log is not automatically rotated. After closing all Moleditpy processes,
you can archive or delete `faulthandler.log`. Do not move, replace or rotate the
file while logging is active: Python keeps its file descriptor open.

## Development

```sh
python -m unittest discover -s tests -v
```

Tests use only the standard library. Subprocess checks verify actual traceback
output and a controlled fatal exit without crashing the test runner. CI runs
Python 3.9–3.14 on Windows, macOS and Linux.

## License

Copyright (C) 2026 Hiromichi Yokoyama. Licensed under **LGPL-3.0-or-later**;
see [LICENSE](LICENSE) and [COPYING](COPYING). No third-party code or binaries
are bundled. Python and Moleditpy retain their respective licenses.

Reference: [Python faulthandler documentation](https://docs.python.org/3/library/faulthandler.html).
