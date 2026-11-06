import sqlite3
from datetime import date, timedelta
from typing import Optional

from app import db
from app.config import load_settings, today_in_hotel

ROOM_TYPES = [
    # code, name, max_guests, nightly_price_mxn
    ("garden", "Garden Room", 2, 1850),
    ("terrace", "Terrace Double", 3, 2650),
    ("suite", "Jacaranda Suite", 4, 4200),
]

ROOMS = [
    ("101", "garden"), ("102", "garden"), ("103", "garden"),
    ("201", "terrace"), ("202", "terrace"),
    ("301", "suite"), ("302", "suite"),
]

# Dates are offsets from today, so the demo never goes stale.
# code, first name, last name, phone, room, check-in offset, nights, guests, status
RESERVATIONS = [
    ("CJ1001", "Lucía", "Hernández", "+525550100001", "101", 0, 3, 2, "confirmed"),
    ("CJ1002", "Mateo", "Ramírez", "+525550100002", "201", -2, 4, 2, "checked_in"),
    ("CJ1003", "Sofía", "Castillo", "+525550100003", "102", -3, 4, 1, "checked_in"),
    # Checks out tomorrow, the same day CJ1005 arrives in room 202.
    ("CJ1004", "Diego", "Morales", "+525550100004", "202", -1, 2, 2, "checked_in"),
    ("CJ1005", "Valentina", "Ortiz", "+525550100005", "202", 1, 3, 3, "confirmed"),
    ("CJ1006", "Andrés", "Navarro", "+525550100006", "103", 2, 2, 2, "cancelled"),
    # CJ1007 and CJ1008 fill both suites, so suites are sold out 5 to 8 days from today.
    ("CJ1007", "Carmen", "Flores", "+525550100007", "301", 5, 3, 2, "confirmed"),
    ("CJ1008", "Javier", "Mendoza", "+525550100008", "302", 5, 3, 4, "confirmed"),
    ("CJ1009", "Carmen", "Flores", "+525550100007", "103", 20, 2, 2, "confirmed"),
]


def seed(conn: sqlite3.Connection, today: Optional[date] = None) -> None:
    today = today or today_in_hotel()
    db.init_schema(conn)
    with conn:
        conn.execute("DELETE FROM support_tickets")
        conn.execute("DELETE FROM late_checkout_requests")
        conn.execute("DELETE FROM reservations")
        conn.execute("DELETE FROM rooms")
        conn.execute("DELETE FROM room_types")
        conn.executemany("INSERT INTO room_types VALUES (?, ?, ?, ?)", ROOM_TYPES)
        conn.executemany("INSERT INTO rooms VALUES (?, ?)", ROOMS)
        for code, first, last, phone, room, offset, nights, guests, status in RESERVATIONS:
            check_in = today + timedelta(days=offset)
            check_out = check_in + timedelta(days=nights)
            email = f"{first.lower()}.{code.lower()}@example.com"
            conn.execute(
                """INSERT INTO reservations
                       (confirmation_code, guest_first_name, guest_last_name, guest_phone,
                        guest_email, room_number, check_in, check_out, guests, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (code, first, last, phone, email, room, check_in.isoformat(),
                 check_out.isoformat(), guests, status),
            )


def main() -> None:
    settings = load_settings()
    conn = db.connect(settings.db_path)
    seed(conn)
    count = conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
    print(f"Seeded {count} reservations into {settings.db_path} (today is {today_in_hotel()}).")


if __name__ == "__main__":
    main()
