"""Tests for application behavior."""

import pytest

from app.services.weights import redistribute


def offer(share: int = 0, pinned: bool = False, removed: bool = False) -> dict:
    return {"share": share, "pinned": pinned, "removed": removed}


def test_equal_distribution_sums_to_hundred():
    result = redistribute([offer(), offer(), offer()])
    assert [item["share"] for item in result] == [34, 33, 33]


def test_pin_and_archive():
    result = redistribute([offer(25, True), offer(), offer(), offer(10, removed=True)])
    assert [item["share"] for item in result] == [25, 38, 37, 0]


def test_invalid_pinned_total():
    with pytest.raises(ValueError):
        redistribute([offer(70, True), offer(40, True)])


def test_input_is_unchanged():
    original = [offer(), offer()]
    redistribute(original)
    assert original[0]["share"] == 0


@pytest.mark.parametrize(
    ("items", "expected"),
    [
        ([], []),
        ([offer()], [100]),
        ([offer(100, True)], [100]),
        ([offer(100, True), offer()], [100, 0]),
        ([offer(40, removed=True)], [0]),
    ],
)
def test_boundaries(items, expected):
    assert [item["share"] for item in redistribute(items)] == expected


@pytest.mark.parametrize("items", [[offer(-1, True)], [offer(101, True)], [offer(50, True)]])
def test_invalid_pinned_values(items):
    with pytest.raises(ValueError):
        redistribute(items)
