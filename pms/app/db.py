import sqlite3
from datetime import date
from typing import Dict, List, Optional

ACTIVE_STATUSES = ("confirmed", "checked_in")

SCHEMA = """
CREATE TABLE IF NOT EXISTS room_types (
    code              TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    max_guests        INTEGER NOT NULL,
    nightly_price_mxn INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS rooms (
    number         TEXT PRIMARY KEY,
    room_type_code TEXT NOT NULL REFERENCES room_types(code)
);

CREATE TABLE IF NOT EXISTS reservations (
    id                INTEGER PRIMARY KEY,
    confirmation_code TEXT NOT NULL UNIQUE,
    guest_first_name  TEXT NOT NULL,
    guest_last_name   TEXT NOT NULL,
    guest_phone       TEXT NOT NULL,
    guest_email       TEXT,
    room_number       TEXT NOT NULL REFERENCES rooms(number),
    check_in          TEXT NOT NULL,
    check_out         TEXT NOT NULL,
    guests            INTEGER NOT NULL,
    status            TEXT NOT NULL
        CHECK (status IN ('confirmed', 'checked_in', 'checked_out', 'cancelled'))
);
CREATE INDEX IF NOT EXISTS idx_reservations_phone ON reservations(guest_phone);

CREATE TABLE IF NOT EXISTS late_checkout_requests (
    id                    INTEGER PRIMARY KEY,
    reservation_id        INTEGER NOT NULL UNIQUE REFERENCES reservations(id),
    requested_time        TEXT NOT NULL,
    approved              INTEGER NOT NULL,
    reason                TEXT,
    latest_available_time TEXT,
    updated_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS support_tickets (
    id             INTEGER PRIMARY KEY,
    reservation_id INTEGER REFERENCES reservations(id),
    category       TEXT NOT NULL,
    priority       TEXT NOT NULL,
    summary        TEXT NOT NULL,
    guest_phone    TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'open',
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

RESERVATION_WITH_ROOM_TYPE = """
SELECT r.*, rt.name AS room_type_name
FROM reservations r
JOIN rooms rm ON rm.number = r.room_number
JOIN room_types rt ON rt.code = rm.room_type_code
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def reservations_by_phone(conn: sqlite3.Connection, phone: str) -> List[sqlite3.Row]:
    return conn.execute(
        RESERVATION_WITH_ROOM_TYPE + " WHERE r.guest_phone = ? ORDER BY r.check_in",
        (phone,),
    ).fetchall()


def reservation_by_code(conn: sqlite3.Connection, code: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        RESERVATION_WITH_ROOM_TYPE + " WHERE UPPER(r.confirmation_code) = UPPER(?)",
        (code,),
    ).fetchone()


def reservation_by_id(conn: sqlite3.Connection, reservation_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        RESERVATION_WITH_ROOM_TYPE + " WHERE r.id = ?",
        (reservation_id,),
    ).fetchone()


def room_has_arrival_on(conn: sqlite3.Connection, room_number: str, day: date,
                        exclude_reservation_id: int) -> bool:
    row = conn.execute(
        """SELECT 1 FROM reservations
           WHERE room_number = ? AND check_in = ? AND id != ?
             AND status IN ('confirmed', 'checked_in')
           LIMIT 1""",
        (room_number, day.isoformat(), exclude_reservation_id),
    ).fetchone()
    return row is not None


def room_types(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    return conn.execute("SELECT * FROM room_types ORDER BY nightly_price_mxn").fetchall()


def free_rooms_by_type(conn: sqlite3.Connection, check_in: date, check_out: date) -> Dict[str, int]:
    """Count rooms per type with no active reservation overlapping the stay."""
    rows = conn.execute(
        """SELECT rm.room_type_code AS code, COUNT(*) AS free
           FROM rooms rm
           WHERE NOT EXISTS (
               SELECT 1 FROM reservations r
               WHERE r.room_number = rm.number
                 AND r.status IN ('confirmed', 'checked_in')
                 AND r.check_in < ? AND r.check_out > ?
           )
           GROUP BY rm.room_type_code""",
        (check_out.isoformat(), check_in.isoformat()),
    ).fetchall()
    return {row["code"]: row["free"] for row in rows}


def late_checkout_request(conn: sqlite3.Connection, reservation_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM late_checkout_requests WHERE reservation_id = ?",
        (reservation_id,),
    ).fetchone()


def save_late_checkout(conn: sqlite3.Connection, reservation_id: int, requested_time: str,
                       approved: bool, reason: Optional[str],
                       latest_available_time: Optional[str]) -> None:
    with conn:
        conn.execute(
            """INSERT INTO late_checkout_requests
                   (reservation_id, requested_time, approved, reason, latest_available_time)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(reservation_id) DO UPDATE SET
                   requested_time = excluded.requested_time,
                   approved = excluded.approved,
                   reason = excluded.reason,
                   latest_available_time = excluded.latest_available_time,
                   updated_at = CURRENT_TIMESTAMP""",
            (reservation_id, requested_time, int(approved), reason, latest_available_time),
        )


def insert_ticket(conn: sqlite3.Connection, reservation_id: Optional[int], category: str,
                  priority: str, summary: str, guest_phone: str) -> int:
    with conn:
        cursor = conn.execute(
            """INSERT INTO support_tickets
                   (reservation_id, category, priority, summary, guest_phone)
               VALUES (?, ?, ?, ?, ?)""",
            (reservation_id, category, priority, summary, guest_phone),
        )
    return cursor.lastrowid
