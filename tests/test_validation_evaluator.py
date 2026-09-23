def test_evaluator_metrics_and_splits():
    import sys
    sys.path.insert(0, ".")
    from tools.evaluate_validation import evaluate, lopo_splits, loso_splits
    gt = [
        {"start": 0, "end": 10, "view": "center_field_good", "pitcher": "A", "broadcast_source": "ESPN"},
        {"start": 10, "end": 20, "view": "closeup_bad", "pitcher": "A", "broadcast_source": "ESPN"},
        {"start": 20, "end": 30, "view": "center_field_good", "pitcher": "B", "broadcast_source": "FOX"},
    ]
    preds = [
        {"start": 0, "end": 10, "view_class": "center_field_good"},
        {"start": 10, "end": 20, "view_class": "center_field_good"},  # FP
        {"start": 20, "end": 30, "view_class": "batter_bad"},  # FN
    ]
    out = evaluate(gt, preds)
    assert out["tp"] == 1 and out["fp"] == 1 and out["fn"] == 1
    assert out["center_field_precision"] == 0.5
    assert out["center_field_recall"] == 0.5
    assert "A" in out["per_pitcher"] and "B" in out["per_pitcher"]
    assert "ESPN" in out["per_source"]
    assert set(lopo_splits(gt).keys()) == {"A", "B"}
    assert set(loso_splits(gt).keys()) == {"ESPN", "FOX"}
