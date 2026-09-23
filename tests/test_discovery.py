"""M3 tests: queries, dedup, source_type, scoring, year, schema."""
import sys

sys.path.insert(0, ".")


def test_query_generation():
    from src.clipper.discovery.queries import build_queries
    qs = build_queries("Shohei Ohtani")
    assert len(qs) == 7
    texts = [q["query"] for q in qs]
    assert any("full outing" in t for t in texts)
    assert any("every pitch" in t for t in texts)
    assert all("Shohei Ohtani" in t for t in texts)
    # no pitcher-specific branching: another name, same shape
    qs2 = build_queries("Paul Skenes")
    assert [q["query"].replace("Paul Skenes", "X") for q in qs2] == \
           [q["query"].replace("Shohei Ohtani", "X") for q in qs]


def test_dedup():
    from src.clipper.discovery.dedup import dedup
    hits = [{"id": "a", "_query_source": "q1"}, {"id": "b", "_query_source": "q1"},
            {"id": "a", "_query_source": "q2"}, {"id": "", "_query_source": "q3"}]
    out = dedup(hits)
    assert len(out) == 2
    a = next(h for h in out if h["id"] == "a")
    assert "q1" in a["_query_source"] and "q2" in a["_query_source"]


def test_source_type_classification():
    from src.clipper.discovery.classify import classify_source_type as c
    assert c("Shohei Ohtani Full Outing vs Dbacks") == "full_outing"
    assert c("Every Pitch: Yamamoto vs Yankees") == "every_pitch"
    assert c("Crochet Full Start, 11 Ks") == "full_start"
    assert c("Skenes Full Game Shutout") == "full_game"
    assert c("Ohtani pitching highlights: 10 Ks on the mound") == "pitching_highlights"
    assert c("Top 10 insane moments compilation") == "general_highlights"
    assert c("Ohtani interview on pitching return", duration=600) == "interview"
    assert c("Fans react to Miller's 103mph", duration=300) == "reaction"
    assert c("Skenes highlights #shorts", duration=40) == "short"
    assert c("Skenes top plays of June") == "general_highlights"
    assert c("Skenes SILENCES the crowd", duration=500) == "unknown"


def test_scoring_determinism_and_preference():
    from src.clipper.discovery.scoring import score_candidate
    full = score_candidate("full_outing", "X Full Outing", "MLB", duration=1500)
    high = score_candidate("pitching_highlights", "X pitching highlights",
                           "Fan Channel", duration=400)
    short = score_candidate("short", "X #shorts", "Fan", duration=40)
    assert full["final_score"] > high["final_score"] > short["final_score"]
    assert score_candidate("full_outing", "t", "MLB", duration=1500) == full
    assert set(full) == {"semantic_score", "duration_score", "source_score",
                         "hold_score", "editing_risk", "final_score"}


def test_shorts_interview_penalty():
    from src.clipper.discovery.scoring import score_candidate
    s = score_candidate("short", "X #shorts", "Fan", duration=40)
    assert s["duration_score"] == 0.0 and s["editing_risk"] >= 0.9
    iv = score_candidate("interview", "X interview", "ESPN", duration=900)
    assert iv["semantic_score"] <= 0.1


def test_year_extraction():
    from src.clipper.discovery.year import extract_year as y
    assert y("Ohtani Full Outing vs Dbacks — June 15, 2026") == (2026, "high")
    assert y("Every Pitch from 2026-06-15 start") == (2026, "high")
    assert y("Best of the 2025 season", published_date="2026-01-05") == (2025, "medium")
    assert y("Untitled mix", published_date="2024-11-02") == (2024, "low")
    assert y("Untitled mix") == (None, "null")
    assert y("Ohtani highlights") == (None, "null")
    assert y("EVERY PITCH in the 2023 World Baseball Classic") == (2023, "medium")
    # bare month name without a date must not crash (alternation grouping)
    assert y("Back to a perfect mid-July day at Fenway") == (None, "null")
    assert y("June baseball", "recap episode, you'll see every pitch",
             "2026-07-02") == (2026, "low")


def test_output_schema():
    from src.clipper.discovery.select import enrich
    raw = {"id": "abc123", "title": "X Full Outing vs Y — June 1, 2026",
           "channel": "MLB", "webpage_url": "https://www.youtube.com/watch?v=abc123",
           "duration": 1200, "upload_date": "20260602",
           "description": "full outing footage", "_query_source": "q"}
    r = enrich(raw)
    for k in ["video_id", "title", "channel", "url", "duration", "source_type",
              "game_year", "game_year_confidence", "suitability", "selection_reason",
              "published_date", "description_excerpt", "query_source"]:
        assert k in r, k
    assert r["game_year"] == 2026 and r["game_year_confidence"] == "high"
    assert r["source_type"] == "full_outing"
