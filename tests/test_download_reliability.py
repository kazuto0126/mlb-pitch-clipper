"""M7.2 tests: yt-dlp download reliability (JS runtime, retry, errors,
leftover cleanup). No network: yt-dlp is replaced by a scripted runner."""
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, ".")

FORBIDDEN = ("ERROR: ffmpeg exited with code 3436169992\n"
             "ERROR: unable to download video data: HTTP Error 403: Forbidden\n")


def _runner(script):
    """script: per call (returncode, stderr, writes_output, leftover_names)."""
    calls = []

    def run(cmd, **kw):
        out = Path(cmd[cmd.index("-o") + 1])
        rc, err, write, leftovers = script[len(calls)]
        calls.append(cmd)
        for name in leftovers:
            (out.parent / name).write_bytes(b"x")
        if write:
            out.write_bytes(b"data")
        return SimpleNamespace(returncode=rc, stderr=err, stdout="")

    run.calls = calls
    return run


def _no_sleep(_):
    pass


def test_js_runtime_default_deno_else_node():
    from src.clipper.acquisition.ytdlp import js_runtime_args
    assert js_runtime_args(which=lambda b: "/x" if b == "deno" else None) == []
    assert js_runtime_args(which=lambda b: "/x" if b == "node" else None) \
        == ["--js-runtimes", "node"]
    assert js_runtime_args(which=lambda b: None) == []


def test_download_cmds_enable_node_when_no_deno(monkeypatch):
    from src.clipper.acquisition import ytdlp
    from src.clipper.acquisition.full_acquire import _build_cmd
    monkeypatch.setattr(ytdlp.shutil, "which",
                        lambda b: "/x" if b == "node" else None)
    cmd = _build_cmd("http://x", Path("o.mp4"))
    assert cmd[-2:] == ["--js-runtimes", "node"] and "--print" not in cmd


def test_error_tail_keeps_ytdlp_reason():
    from src.clipper.acquisition.ytdlp import error_tail
    t = error_tail("WARNING: no js runtime\n[download] 10%\n" + FORBIDDEN)
    assert "403" in t and "WARNING" not in t
    assert error_tail("") == ""


def test_full_download_retries_transient_403(tmp_path, monkeypatch):
    from src.clipper.acquisition import full_acquire as fa
    monkeypatch.setattr(fa, "probe_video", lambda p: SimpleNamespace(
        width=1280, height=720, fps=30.0, duration=838.0, codec="h264"))
    run = _runner([(1, FORBIDDEN, False, ["original.f298.mp4.part"]),
                   (0, "", True, [])])
    sleeps = []
    r = fa.acquire_full("http://x", str(tmp_path / "original.mp4"),
                        runner=run, sleep=sleeps.append)
    assert r["ok"] is True and r["method"] == "yt-dlp-full"
    assert r["attempts"] == 2 and len(run.calls) == 2 and len(sleeps) == 1


def test_full_download_failure_keeps_reason_and_cleans_up(tmp_path):
    from src.clipper.acquisition import full_acquire as fa
    from src.clipper.acquisition.ytdlp import DOWNLOAD_ATTEMPTS
    leftovers = ["original.f298.mp4.part", "original.f298.mp4.ytdl"]
    run = _runner([(1, FORBIDDEN, False, leftovers)] * DOWNLOAD_ATTEMPTS)
    (tmp_path / "metadata.json").write_text("{}")  # unrelated: must survive
    r = fa.acquire_full("http://x", str(tmp_path / "original.mp4"),
                        runner=run, sleep=_no_sleep)
    assert r["ok"] is False and r["attempts"] == DOWNLOAD_ATTEMPTS
    assert "HTTP Error 403" in r["error"] and r["error"].startswith("download:")
    assert [p.name for p in tmp_path.iterdir()] == ["metadata.json"]


def test_full_download_timeout_not_retried(tmp_path):
    from src.clipper.acquisition import full_acquire as fa
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))

    r = fa.acquire_full("http://x", str(tmp_path / "original.mp4"),
                        runner=run, sleep=_no_sleep)
    assert r["ok"] is False and "timeout" in r["error"] and len(calls) == 1


def test_exit_zero_without_file_is_failure(tmp_path):
    from src.clipper.acquisition.ytdlp import run_download
    run = _runner([(0, "", False, [])] * 2)
    ok, n, err = run_download(["yt-dlp", "u", "-o", str(tmp_path / "o.mp4")],
                              tmp_path / "o.mp4", 10, attempts=2,
                              runner=run, sleep=_no_sleep)
    assert ok is False and n == 2 and "no output file" in err


def test_section_retry_avoids_full_fallback(tmp_path):
    from src.clipper.acquisition.preview_acquire import download_section
    run = _runner([(1, FORBIDDEN, False, []), (0, "", True, [])])
    plan = download_section("http://x", 100.0, 20.0,
                            str(tmp_path / "seg00_100s.mp4"),
                            runner=run, sleep=_no_sleep)
    assert plan.method == "yt-dlp-section"
    assert len(run.calls) == 2
    assert all("--download-sections" in c for c in run.calls)


def test_section_and_fallback_failure_cleans_partials(tmp_path):
    from src.clipper.acquisition.preview_acquire import download_section
    run = _runner([(1, FORBIDDEN, False, ["seg00_100s.f298.mp4.part"]),
                   (1, FORBIDDEN, False, []),
                   (1, FORBIDDEN, False, ["seg00_100s.full.f398.mp4.part"])])
    (tmp_path / "seg01_300s.mp4").write_bytes(b"other segment")  # untouched
    plan = download_section("http://x", 100.0, 20.0,
                            str(tmp_path / "seg00_100s.mp4"),
                            runner=run, sleep=_no_sleep)
    assert plan.method == "failed" and "403" in plan.error
    # 2 cheap section attempts, then exactly 1 expensive full fallback
    assert len(run.calls) == 3 and "--download-sections" not in run.calls[2]
    assert [p.name for p in tmp_path.iterdir()] == ["seg01_300s.mp4"]
