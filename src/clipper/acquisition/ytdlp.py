"""Shared yt-dlp download invocation (M7.2 download reliability).

- JS runtime: yt-dlp only enables deno by default; without a JS runtime
  YouTube extraction is deprecated and formats may be missing. When deno
  is absent but node is on PATH, node is enabled explicitly.
- Retry: transient YouTube HTTP 403s are common (RC regression: 5/8 runs);
  a retry usually succeeds (yt-dlp resumes its .part file). Bounded
  attempts with short backoff; a timeout is never retried.
- Errors: keep yt-dlp's own ERROR lines (e.g. "HTTP Error 403"), not a
  truncated argv repr that hides the reason.
- Cleanup: a final failure removes the .part/.ytdl leftovers it produced.

Acquisition only: M1/M2/gate judgments are untouched.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

DOWNLOAD_ATTEMPTS = 3
RETRY_BACKOFF_SEC = (5.0, 15.0)


def js_runtime_args(which=None) -> list[str]:
    which = which or shutil.which
    if which("deno"):
        return []  # yt-dlp default runtime
    if which("node"):
        return ["--js-runtimes", "node"]
    return []


def error_tail(stderr: str, limit: int = 300) -> str:
    lines = [ln.strip() for ln in (stderr or "").splitlines() if ln.strip()]
    errs = [ln for ln in lines if ln.startswith("ERROR")]
    return " | ".join(errs or lines[-3:])[-limit:]


def run_download(cmd: list[str], out: Path, timeout: int,
                 attempts: int = DOWNLOAD_ATTEMPTS, runner=subprocess.run,
                 sleep=time.sleep) -> tuple[bool, int, str]:
    """Run a yt-dlp download until `out` exists non-empty with exit 0.

    Returns (ok, attempts_used, error)."""
    err = ""
    for i in range(attempts):
        if i:
            sleep(RETRY_BACKOFF_SEC[min(i - 1, len(RETRY_BACKOFF_SEC) - 1)])
        try:
            p = runner(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, i + 1, f"timeout after {timeout}s"
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:200]}"
            continue
        if p.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return True, i + 1, ""
        err = error_tail(p.stderr) or f"exit {p.returncode}, no output file"
    return False, attempts, err


def cleanup_partials(out: Path) -> list[str]:
    """Remove leftovers of a failed download of `out`.

    yt-dlp writes `<stem>.f<id>.<ext>[.part|.ytdl|.part-FragN]` and may
    leave an empty `out`; only names starting with `<stem>.` in out's
    folder are touched (pipeline-owned per-source/per-segment folders)."""
    removed = []
    prefix = out.stem + "."
    if not out.parent.exists():
        return removed
    for p in out.parent.iterdir():
        if p.is_file() and p.name.startswith(prefix):
            try:
                p.unlink()
                removed.append(p.name)
            except OSError:
                pass
    return removed
