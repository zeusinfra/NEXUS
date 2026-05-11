"""Tests for Temporal Context logic."""

from nexus_core.cognitive.user_profile_engine import _period_label, TemporalContext


def test_period_labels():
    assert _period_label(8) == "morning"
    assert _period_label(13) == "afternoon_early"
    assert _period_label(15) == "afternoon"
    assert _period_label(19) == "evening"
    assert _period_label(22) == "night"
    assert _period_label(2) == "late_night"


def test_temporal_context_serialization():
    ctx = TemporalContext(
        current_hour=14,
        current_weekday=1,
        is_work_hours=True,
        is_deep_focus=False,
        period_label="afternoon",
    )
    d = ctx.to_dict()
    assert d["current_hour"] == 14
    assert d["period_label"] == "afternoon"
    assert d["is_work_hours"] is True
