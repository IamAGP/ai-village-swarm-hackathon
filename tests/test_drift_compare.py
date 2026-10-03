import json

import pytest

from explorer.drift_compare import LabelSet, compare


def labels(*pairs):
    return LabelSet.from_records({"msg_id": row_id, "agent": "synthetic", "stance": stance}
                                 for row_id, stance in pairs)


def test_join_by_id_and_known_kappa():
    a = labels(("a", "repeats"), ("b", "repeats"), ("c", "flags"), ("d", "flags"))
    b = labels(("d", "flags"), ("c", "repeats"), ("b", "repeats"), ("a", "repeats"))
    r = compare(a, b, bootstrap=50)
    assert r["agreements"] == 3
    assert r["kappa"] == pytest.approx(.5)
    assert r["matrix_primary_rows_reference_columns"]["flags"]["repeats"] == 1
    assert r["disagreements"] == [
        {"msg_id": "c", "primary": "flags", "reference": "repeats", "targeted": True}]
    assert compare(a, b, bootstrap=50) == r


def test_reject_incomplete_duplicate_invalid_and_misattributed_labels():
    with pytest.raises(ValueError, match="Duplicate"):
        labels(("a", "flags"), ("a", "checks"))
    with pytest.raises(ValueError, match="Unknown"):
        labels(("a", "certain"))
    with pytest.raises(ValueError, match="same row IDs"):
        compare(labels(("a", "flags")), labels(("b", "flags")))
    with pytest.raises(ValueError, match="agent mismatch"):
        compare(labels(("a", "flags")), LabelSet.from_records([
            {"msg_id": "a", "agent": "another", "stance": "flags"}]))


def test_degenerate_kappa_and_excerpt_validation(tmp_path):
    a = labels(("a", "neutral"))
    report = compare(a, a, bootstrap=20)
    assert report["kappa"] is None
    assert report["kappa_bootstrap_ci95"] is None
    assert report["undefined_bootstrap_draws"] == 20
    item = tmp_path / "synthetic.jsonl"
    item.write_text(json.dumps({"msg_id": "a", "agent": "synthetic", "text": "synthetic cue"}) + "\n")
    good = LabelSet.from_records([
        {"msg_id": "a", "agent": "synthetic", "stance": "neutral",
         "gist": "Synthetic message", "cue": "synthetic cue"}])
    good.validate_items([item])
    bad = LabelSet.from_records([
        {"msg_id": "a", "agent": "synthetic", "stance": "neutral",
         "gist": "Synthetic message", "cue": "missing cue"}])
    with pytest.raises(ValueError, match="excerpt cue"):
        bad.validate_items([item])
