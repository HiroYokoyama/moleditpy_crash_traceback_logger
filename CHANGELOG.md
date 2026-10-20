# Changelog

## 0.1.0 — 2026-10-21

- Publish the local crash diagnostic as **Crash Traceback Logger**.
- Record crash-time Python tracebacks in `~/.moleditpy/faulthandler.log`.
- Create the log directory, append session metadata and retain a descriptor
  through interpreter shutdown.
- Preserve pre-existing fault handlers and report initialization failures.
- Document installation, disabling, log privacy and diagnostic limits.
- Test lifecycle behavior and real traceback/fatal-abort output in subprocesses.
