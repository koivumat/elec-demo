"""The choices registry is complete and the variant folder names are stable."""

import re

import pytest

import choices


def test_every_choice_is_documented():
    for name, c in choices.CHOICES.items():
        assert c.name == name
        assert c.reason.strip(), f"{name} has no reason"
        assert re.fullmatch(r"\d\d_[a-z_]+", c.first_step), f"{name}: bad first_step"
        assert c.default not in c.alternatives, f"{name}: default listed as alternative"


def test_defaults_give_no_variant():
    assert choices.variant_name(choices.resolve({})) is None


def test_variant_name_is_sorted_and_stable():
    a = choices.resolve({"price_resolution": "hourly", "bidding_zone": "EE"})
    b = choices.resolve({"bidding_zone": "EE", "price_resolution": "hourly"})
    assert choices.variant_name(a) == "bidding_zone-EE__price_resolution-hourly"
    assert choices.variant_name(a) == choices.variant_name(b)


def test_setting_the_default_explicitly_is_still_default():
    assert choices.variant_name(choices.resolve({"bidding_zone": "FI"})) is None


def test_unknown_choice_is_rejected():
    with pytest.raises(ValueError, match="Unknown choice"):
        choices.resolve({"no_such_choice": "x"})


def test_value_outside_alternatives_is_rejected():
    with pytest.raises(ValueError, match="not allowed"):
        choices.resolve({"price_resolution": "5min"})


def test_open_ended_choice_accepts_new_value():
    assert choices.resolve({"sample_start": "2024-01-01"})["sample_start"] == "2024-01-01"
