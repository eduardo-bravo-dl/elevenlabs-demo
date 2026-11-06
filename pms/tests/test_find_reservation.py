import pytest

from tests.conftest import day


@pytest.mark.parametrize("phone", ["5550100001", "+525550100001", "+5215550100001"])
def test_finds_guest_arriving_today_by_any_phone_format(post, phone):
    res = post("find-reservation", {"phone": phone})
    assert res.status_code == 200
    body = res.json()
    assert body["found"] is True and body["multiple"] is False
    r = body["reservation"]
    assert r["confirmation_code"] == "CJ1001"
    assert r["check_in"] == day(0)
    assert r["status"] == "confirmed"


def test_finds_by_code_and_last_name_ignoring_case_and_accents(post):
    body = post("find-reservation", {"confirmation_code": "cj-1002", "last_name": "ramirez"}).json()
    assert body["found"] is True
    assert body["reservation"]["guest_first_name"] == "Mateo"
    assert body["reservation"]["status"] == "checked_in"


def test_does_not_expose_contact_details(post):
    body = post("find-reservation", {"phone": "5550100001"}).json()
    flat = str(body)
    assert "5550100001" not in flat and "@" not in flat
    assert "guest_last_name" not in body["reservation"]


def test_not_found_is_a_200_business_outcome(post):
    res = post("find-reservation", {"phone": "5599999999"})
    assert res.status_code == 200
    assert res.json()["found"] is False


def test_wrong_last_name_is_not_found(post):
    body = post("find-reservation", {"confirmation_code": "CJ1001", "last_name": "Smith"}).json()
    assert body["found"] is False


def test_multiple_active_reservations_returns_list_without_choosing(post):
    body = post("find-reservation", {"phone": "55 5010 0007"}).json()
    assert body["found"] is True and body["multiple"] is True
    assert body["reservation"] is None
    assert [r["confirmation_code"] for r in body["reservations"]] == ["CJ1007", "CJ1009"]
    assert "Which one" in body["message"]


def test_cancelled_reservation_is_reported_as_cancelled(post):
    body = post("find-reservation", {"phone": "5550100006"}).json()
    assert body["found"] is True
    assert body["reservation"]["status"] == "cancelled"
    assert "cancelled" in body["message"]


@pytest.mark.parametrize("payload", [
    {},
    {"confirmation_code": "CJ1001"},
    {"phone": "12345"},
])
def test_invalid_input_is_422(post, payload):
    res = post("find-reservation", payload)
    assert res.status_code == 422
    assert res.json()["error"] == "invalid_request"
