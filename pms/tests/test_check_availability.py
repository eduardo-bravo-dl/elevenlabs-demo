import pytest

from tests.conftest import day


def test_lists_all_fitting_room_types_with_prices(post):
    res = post("check-availability", {"check_in": day(10), "check_out": day(12), "guests": 2})
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is True and body["nights"] == 2
    by_code = {o["room_type"]: o for o in body["options"]}
    assert set(by_code) == {"garden", "terrace", "suite"}
    assert by_code["garden"]["nightly_price_mxn"] == 1850
    assert by_code["garden"]["total_price_mxn"] == 3700


def test_guest_count_filters_small_rooms(post):
    body = post("check-availability", {"check_in": day(10), "check_out": day(11), "guests": 4}).json()
    assert [o["room_type"] for o in body["options"]] == ["suite"]


def test_specific_room_type_by_name(post):
    body = post("check-availability", {"check_in": day(10), "check_out": day(13), "guests": 2,
                                       "room_type": "Jacaranda Suite"}).json()
    assert body["available"] is True
    assert body["options"][0]["total_price_mxn"] == 3 * 4200


def test_sold_out_room_type_returns_alternatives(post):
    body = post("check-availability", {"check_in": day(6), "check_out": day(7), "guests": 2,
                                       "room_type": "suite"}).json()
    assert body["available"] is False
    assert body["options"] == []
    assert "sold out" in body["message"]
    assert {o["room_type"] for o in body["alternatives"]} == {"garden", "terrace"}


def test_sold_out_when_overlapping_partially(post):
    # Stay starts before the sold-out window and ends inside it.
    body = post("check-availability", {"check_in": day(3), "check_out": day(6), "guests": 4}).json()
    assert body["available"] is False


def test_cancelled_booking_does_not_block_inventory(post):
    # Room 101 is occupied on day 2; 102 is free, and 103 only has a cancelled booking.
    body = post("check-availability", {"check_in": day(2), "check_out": day(3), "guests": 2,
                                       "room_type": "garden"}).json()
    assert body["available"] is True
    assert body["options"][0]["rooms_left"] == 2


def test_unknown_room_type_is_business_outcome(post):
    res = post("check-availability", {"check_in": day(10), "check_out": day(11), "guests": 2,
                                      "room_type": "penthouse"})
    assert res.status_code == 200
    assert res.json()["available"] is False
    assert len(res.json()["alternatives"]) == 3


@pytest.mark.parametrize("check_in,check_out,message", [
    (day(5), day(5), "check_out must be after check_in"),
    (day(5), day(4), "check_out must be after check_in"),
    (day(-1), day(2), "check_in cannot be in the past"),
])
def test_invalid_dates_are_rejected(post, check_in, check_out, message):
    res = post("check-availability", {"check_in": check_in, "check_out": check_out, "guests": 2})
    assert res.status_code == 422
    assert message in res.json()["message"]
