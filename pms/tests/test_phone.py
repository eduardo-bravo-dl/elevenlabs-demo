import pytest

from app.phone import mask_phone, normalize_mx_phone

EXPECTED = "+525550100001"


@pytest.mark.parametrize("raw", [
    "5550100001",           # 10-digit national
    "55 5010 0001",
    "(55) 5010-0001",
    "+525550100001",        # E.164
    "+52 55 5010 0001",
    "525550100001",
    "+5215550100001",       # legacy mobile format
    "+52 1 55 5010 0001",
])
def test_all_formats_normalize_to_same_e164(raw):
    assert normalize_mx_phone(raw) == EXPECTED


@pytest.mark.parametrize("raw", ["", "12345", "+15550100001", "+52555010000", "99 5550100001"])
def test_invalid_numbers_raise(raw):
    with pytest.raises(ValueError):
        normalize_mx_phone(raw)


def test_mask_keeps_last_four_digits():
    assert mask_phone(EXPECTED) == "***0001"
