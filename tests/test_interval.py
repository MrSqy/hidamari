import os

from playlist import INTERVAL_MAX_SEC, effective_interval

VID = "/videos/a.mp4"


def test_no_override_uses_default():
    assert effective_interval(VID, 4, {}) == 4


def test_override_value_wins_over_default():
    assert effective_interval(VID, 4, {VID: 20}) == 20


def test_override_zero_means_play_to_end():
    assert effective_interval(VID, 4, {VID: 0}) == 0


def test_default_zero_when_no_override():
    assert effective_interval(VID, 0, {}) == 0


def test_invalid_override_falls_back_to_default():
    assert effective_interval(VID, 4, {VID: "abc"}) == 4
    assert effective_interval(VID, 4, {VID: -5}) == 4


def test_invalid_default_falls_back_to_zero():
    assert effective_interval(VID, "oops", {}) == 0


def test_clamp_to_max():
    assert effective_interval(VID, 999999, {}) == INTERVAL_MAX_SEC
    assert effective_interval(VID, 4, {VID: 999999}) == INTERVAL_MAX_SEC


def test_overrides_not_a_dict_is_ignored():
    assert effective_interval(VID, 4, None) == 4
    assert effective_interval(VID, 4, []) == 4


def test_override_matched_by_realpath(tmp_path):
    real = tmp_path / "a.mp4"
    real.write_bytes(b"")
    key = os.path.realpath(str(real))
    messy = str(tmp_path / "." / "a.mp4")  # realpath normalizes the "/./"
    assert effective_interval(messy, 4, {key: 12}) == 12
