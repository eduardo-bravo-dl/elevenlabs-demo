from app import db


def test_creates_open_ticket_linked_to_reservation(post, db_path):
    res = post("create-ticket", {
        "reservation_id": 1, "category": "housekeeping", "priority": "high",
        "summary": "Guest needs extra towels in room.", "guest_phone": "+521 55 5010 0001",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "open"
    assert body["ticket_id"].startswith("T-")
    assert body["reservation_linked"] is True
    assert body["ticket_id"] in body["message"]

    conn = db.connect(db_path)
    row = conn.execute("SELECT * FROM support_tickets").fetchone()
    conn.close()
    assert row["guest_phone"] == "+525550100001"
    assert row["reservation_id"] == 1


def test_ticket_without_reservation(post):
    body = post("create-ticket", {"category": "other", "summary": "Asking about parking.",
                                  "guest_phone": "5550109999"}).json()
    assert body["status"] == "open"
    assert body["reservation_linked"] is False


def test_ticket_ids_are_unique(post):
    payload = {"category": "billing", "summary": "Question about a charge.", "guest_phone": "5550100002"}
    first = post("create-ticket", payload).json()["ticket_id"]
    second = post("create-ticket", payload).json()["ticket_id"]
    assert first != second


def test_unknown_reservation_still_creates_unlinked_ticket(post):
    body = post("create-ticket", {"reservation_id": 9999, "category": "complaint",
                                  "summary": "Noise next door.", "guest_phone": "5550100002"}).json()
    assert body["status"] == "open"
    assert body["reservation_linked"] is False


def test_invalid_category_is_422(post):
    res = post("create-ticket", {"category": "spa", "summary": "Book a massage.",
                                 "guest_phone": "5550100002"})
    assert res.status_code == 422
