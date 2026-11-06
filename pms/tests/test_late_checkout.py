from datetime import time, timedelta

import pytest

from app import db, services
from app.config import today_in_hotel
from app.schemas import LateCheckoutRequest


@pytest.fixture
def res_id(post):
    def _lookup(code, last_name):
        body = post("find-reservation", {"confirmation_code": code, "last_name": last_name}).json()
        return body["reservation"]["reservation_id"]
    return _lookup


def late(post, reservation_id, requested_time):
    res = post("request-late-checkout",
               {"reservation_id": reservation_id, "requested_time": requested_time})
    assert res.status_code == 200
    return res.json()


def count_requests(db_path):
    conn = db.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM late_checkout_requests").fetchone()[0]
    finally:
        conn.close()


def test_approved_when_checking_out_tomorrow_and_room_is_free(post, res_id):
    body = late(post, res_id("CJ1003", "Castillo"), "13:30")
    assert body["status"] == "approved" and body["approved"] is True
    assert body["checkout_time"] == "13:30"
    assert body["already_requested"] is False


def test_approved_on_checkout_day_itself(db_path):
    conn = db.connect(db_path)
    row = db.reservation_by_code(conn, "CJ1003")
    checkout_day = today_in_hotel() + timedelta(days=1)
    req = LateCheckoutRequest(reservation_id=row["id"], requested_time=time(14, 0))
    assert services.request_late_checkout(conn, req, today=checkout_day).approved is True
    conn.close()


def test_repeating_same_request_does_not_duplicate(post, res_id, db_path):
    rid = res_id("CJ1003", "Castillo")
    first = late(post, rid, "14:00")
    second = late(post, rid, "14:00")
    assert first["approved"] and second["approved"]
    assert second["already_requested"] is True
    assert "already confirmed" in second["message"]
    assert count_requests(db_path) == 1


def test_changing_the_time_updates_the_single_request(post, res_id, db_path):
    rid = res_id("CJ1003", "Castillo")
    assert late(post, rid, "15:00")["approved"] is False
    assert late(post, rid, "13:00")["approved"] is True
    assert count_requests(db_path) == 1


def test_after_14_is_rejected_with_latest_time(post, res_id):
    body = late(post, res_id("CJ1003", "Castillo"), "16:00")
    assert body["status"] == "rejected" and body["approved"] is False
    assert body["latest_available_time"] == "14:00"
    assert body["checkout_time"] == "12:00"


def test_rejected_when_next_guest_arrives_in_same_room(post, res_id):
    body = late(post, res_id("CJ1004", "Morales"), "13:00")
    assert body["approved"] is False
    assert "Another guest" in body["reason"]
    assert body["latest_available_time"] == "12:00"


def test_rejected_when_checkout_is_not_today_or_tomorrow(post, res_id):
    body = late(post, res_id("CJ1002", "Ramirez"), "13:00")  # checks out in 2 days
    assert body["approved"] is False
    assert body["latest_available_time"] == "12:00"


def test_rejected_for_cancelled_reservation(post, res_id):
    body = late(post, res_id("CJ1006", "Navarro"), "13:00")
    assert body["approved"] is False
    assert "cancelled" in body["reason"]
    assert body["latest_available_time"] is None


def test_unknown_reservation_is_not_found(post):
    body = late(post, 9999, "13:00")
    assert body["status"] == "not_found" and body["approved"] is False


def test_time_at_or_before_noon_needs_no_request(post, res_id, db_path):
    body = late(post, res_id("CJ1003", "Castillo"), "11:00")
    assert body["status"] == "not_needed" and body["approved"] is True
    assert count_requests(db_path) == 0


def test_invalid_time_is_422(post):
    res = post("request-late-checkout", {"reservation_id": 1, "requested_time": "25:00"})
    assert res.status_code == 422


def test_rejected_follow_up_keeps_earlier_approval(post, res_id, db_path):
    rid = res_id("CJ1003", "Castillo")
    assert late(post, rid, "13:30")["approved"] is True

    body = late(post, rid, "16:00")
    assert body["approved"] is False
    assert body["checkout_time"] == "13:30"
    assert "stays at 13:30" in body["message"]

    conn = db.connect(db_path)
    row = db.late_checkout_request(conn, rid)
    conn.close()
    assert row["approved"] == 1 and row["requested_time"] == "13:30"


def test_approved_request_can_move_to_a_later_allowed_time(post, res_id):
    rid = res_id("CJ1003", "Castillo")
    late(post, rid, "13:00")
    body = late(post, rid, "14:00")
    assert body["approved"] is True and body["checkout_time"] == "14:00"
