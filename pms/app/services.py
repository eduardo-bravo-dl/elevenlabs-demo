import logging
import sqlite3
import unicodedata
from datetime import date, time, timedelta
from typing import List, NamedTuple, Optional

from app import db
from app.phone import mask_phone
from app.schemas import (
    CheckAvailabilityRequest, CheckAvailabilityResponse, CreateTicketRequest,
    CreateTicketResponse, FindReservationRequest, FindReservationResponse,
    LateCheckoutRequest, LateCheckoutResponse, ReservationSummary, RoomOption,
)

log = logging.getLogger("pms")

STANDARD_CHECKOUT = time(12, 0)
LATEST_CHECKOUT = time(14, 0)


def find_reservation(conn: sqlite3.Connection,
                     req: FindReservationRequest) -> FindReservationResponse:
    rows = _lookup_reservations(conn, req)
    if not rows:
        return FindReservationResponse(
            found=False, message="I couldn't find a reservation with those details.")

    reservations = [_to_summary(row) for row in rows]
    active = [r for r in reservations if r.status in db.ACTIVE_STATUSES]

    if len(active) > 1:
        listed = "; ".join(_describe(r) for r in active)
        return FindReservationResponse(
            found=True, multiple=True, reservations=active,
            message=f"I found {len(active)} reservations: {listed}. Which one is this about?")

    if len(active) == 1:
        r = active[0]
        return FindReservationResponse(
            found=True, reservation=r,
            message=f"I found your reservation, {r.guest_first_name}: {_describe(r)}.")

    latest = reservations[-1]
    state = "was cancelled" if latest.status == "cancelled" else "is already checked out"
    return FindReservationResponse(
        found=True, reservation=latest,
        message=f"I found a reservation for {latest.guest_first_name}, but it {state}.")


def check_availability(conn: sqlite3.Connection,
                       req: CheckAvailabilityRequest) -> CheckAvailabilityResponse:
    nights = (req.check_out - req.check_in).days
    free_rooms = db.free_rooms_by_type(conn, req.check_in, req.check_out)
    room_types = db.room_types(conn)
    bookable = [
        _to_option(rt, nights, free_rooms[rt["code"]])
        for rt in room_types
        if rt["max_guests"] >= req.guests and free_rooms.get(rt["code"], 0) > 0
    ]
    stay = dict(check_in=req.check_in, check_out=req.check_out, nights=nights)

    if req.room_type:
        return _check_one_room_type(req, room_types, bookable, stay)

    if not bookable:
        return CheckAvailabilityResponse(
            available=False, **stay,
            message=f"Sorry, we have nothing available for {req.guests} guests on those dates.")
    return CheckAvailabilityResponse(
        available=True, options=bookable, **stay,
        message=f"For {_spoken_stay(req.check_in, nights)}, we have {_price_list(bookable)}.")


def _check_one_room_type(req: CheckAvailabilityRequest, room_types: List[sqlite3.Row],
                         bookable: List[RoomOption], stay: dict) -> CheckAvailabilityResponse:
    wanted = _match_room_type(room_types, req.room_type)
    if wanted is None:
        return CheckAvailabilityResponse(
            available=False, alternatives=bookable, **stay,
            message=f"We don't have a room type called {req.room_type}. {_suggest(bookable)}")

    for option in bookable:
        if option.room_type == wanted["code"]:
            return CheckAvailabilityResponse(
                available=True, options=[option], **stay,
                message=f"Yes, the {option.name} is available for "
                        f"{_spoken_stay(req.check_in, stay['nights'])}: "
                        f"{option.nightly_price_mxn:,} pesos a night, "
                        f"{option.total_price_mxn:,} pesos total.")

    if wanted["max_guests"] < req.guests:
        problem = f"only fits up to {wanted['max_guests']} guests"
    else:
        problem = "is sold out for those dates"
    others = [o for o in bookable if o.room_type != wanted["code"]]
    return CheckAvailabilityResponse(
        available=False, alternatives=others, **stay,
        message=f"The {wanted['name']} {problem}. {_suggest(others)}")


class Decision(NamedTuple):
    approved: bool
    reason: Optional[str]
    latest_time: Optional[str]


def request_late_checkout(conn: sqlite3.Connection, req: LateCheckoutRequest,
                          today: date) -> LateCheckoutResponse:
    requested = _hhmm(req.requested_time)
    standard = _hhmm(STANDARD_CHECKOUT)
    base = dict(reservation_id=req.reservation_id, requested_time=requested)

    reservation = db.reservation_by_id(conn, req.reservation_id)
    if reservation is None:
        return LateCheckoutResponse(
            status="not_found", approved=False, checkout_time=standard,
            reason="Reservation not found.", **base,
            message="I couldn't find that reservation.")

    if req.requested_time <= STANDARD_CHECKOUT:
        return LateCheckoutResponse(
            status="not_needed", approved=True, checkout_time=standard, **base,
            message=f"Checkout is at {standard}, so no late checkout is needed for that time.")

    # An approval is a promise to the guest: repeating it returns the stored answer, and a
    # rejected follow-up request never cancels it. Rejections are re-evaluated, because
    # the guest may ask again on a later day.
    previous = db.late_checkout_request(conn, req.reservation_id)
    previous_approval = previous["requested_time"] if previous and previous["approved"] else None
    is_repeat = previous is not None and previous["requested_time"] == requested
    if previous_approval == requested:
        return LateCheckoutResponse(
            status="approved", approved=True, checkout_time=requested, already_requested=True,
            latest_available_time=previous["latest_available_time"], **base,
            message=f"Your late checkout at {requested} is already confirmed.")

    decision = _decide_late_checkout(conn, reservation, req.requested_time, today)

    if decision.approved:
        db.save_late_checkout(conn, req.reservation_id, requested, approved=True,
                              reason=None, latest_available_time=decision.latest_time)
        return LateCheckoutResponse(
            status="approved", approved=True, checkout_time=requested,
            latest_available_time=decision.latest_time, already_requested=is_repeat, **base,
            message=f"Done. Your checkout is now at {requested}.")

    if previous_approval is None:
        db.save_late_checkout(conn, req.reservation_id, requested, approved=False,
                              reason=decision.reason, latest_available_time=decision.latest_time)
    checkout_time = previous_approval or standard
    return LateCheckoutResponse(
        status="rejected", approved=False, checkout_time=checkout_time,
        latest_available_time=decision.latest_time, reason=decision.reason,
        already_requested=is_repeat, **base,
        message=_rejection_message(requested, decision, checkout_time))


def _decide_late_checkout(conn: sqlite3.Connection, reservation: sqlite3.Row,
                          requested: time, today: date) -> Decision:
    standard, latest = _hhmm(STANDARD_CHECKOUT), _hhmm(LATEST_CHECKOUT)
    check_out = date.fromisoformat(reservation["check_out"])

    if reservation["status"] not in db.ACTIVE_STATUSES:
        status = reservation["status"].replace("_", " ")
        return Decision(False, f"This reservation is {status}.", None)
    if check_out not in (today, today + timedelta(days=1)):
        return Decision(False, "Late checkout can only be arranged on the day before "
                               "or the day of checkout.", standard)
    if db.room_has_arrival_on(conn, reservation["room_number"], check_out, reservation["id"]):
        return Decision(False, "Another guest is arriving in that room the same day.", standard)
    if requested > LATEST_CHECKOUT:
        return Decision(False, "That is later than our latest checkout time.", latest)
    return Decision(True, None, latest)


def _rejection_message(requested: str, decision: Decision, checkout_time: str) -> str:
    message = f"Sorry, I can't approve {requested}. {decision.reason}"
    if decision.latest_time is None:
        return message
    if checkout_time != _hhmm(STANDARD_CHECKOUT):
        return f"{message} Your checkout stays at {checkout_time}."
    if decision.latest_time == checkout_time:
        return f"{message} Checkout stays at {checkout_time}."
    return f"{message} The latest I can offer is {decision.latest_time}."


def create_ticket(conn: sqlite3.Connection, req: CreateTicketRequest) -> CreateTicketResponse:
    reservation_id = req.reservation_id
    if reservation_id is not None and db.reservation_by_id(conn, reservation_id) is None:
        reservation_id = None

    row_id = db.insert_ticket(conn, reservation_id, req.category, req.priority,
                              req.summary, req.guest_phone)
    ticket_id = f"T-{1000 + row_id}"
    log.info("ticket %s created for %s", ticket_id, mask_phone(req.guest_phone))
    return CreateTicketResponse(
        ticket_id=ticket_id, status="open", reservation_linked=reservation_id is not None,
        message=f"I've passed this to our front desk team. Your ticket number is {ticket_id}.")


def _lookup_reservations(conn: sqlite3.Connection,
                         req: FindReservationRequest) -> List[sqlite3.Row]:
    if req.phone:
        log.info("lookup by phone %s", mask_phone(req.phone))
        return db.reservations_by_phone(conn, req.phone)

    code = req.confirmation_code.replace(" ", "").replace("-", "")
    row = db.reservation_by_code(conn, code)
    if row and _fold(row["guest_last_name"]) == _fold(req.last_name):
        return [row]
    return []


def _match_room_type(room_types: List[sqlite3.Row], query: str) -> Optional[sqlite3.Row]:
    key = _fold(query)
    for rt in room_types:
        if key in (_fold(rt["code"]), _fold(rt["name"])):
            return rt
    return None


def _to_summary(row: sqlite3.Row) -> ReservationSummary:
    check_in = date.fromisoformat(row["check_in"])
    check_out = date.fromisoformat(row["check_out"])
    return ReservationSummary(
        reservation_id=row["id"],
        confirmation_code=row["confirmation_code"],
        guest_first_name=row["guest_first_name"],
        room_type=row["room_type_name"],
        check_in=check_in,
        check_out=check_out,
        nights=(check_out - check_in).days,
        guests=row["guests"],
        status=row["status"],
    )


def _to_option(room_type: sqlite3.Row, nights: int, rooms_left: int) -> RoomOption:
    return RoomOption(
        room_type=room_type["code"],
        name=room_type["name"],
        max_guests=room_type["max_guests"],
        nightly_price_mxn=room_type["nightly_price_mxn"],
        total_price_mxn=room_type["nightly_price_mxn"] * nights,
        rooms_left=rooms_left,
    )


def _fold(text: str) -> str:
    """Lowercase and strip accents, so "hernandez" matches "Hernández"."""
    decomposed = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _hhmm(t: time) -> str:
    return t.strftime("%H:%M")


def _spoken_date(d: date) -> str:
    return f"{d:%A}, {d:%B} {d.day}"


def _spoken_stay(check_in: date, nights: int) -> str:
    plural = "night" if nights == 1 else "nights"
    return f"{nights} {plural} from {_spoken_date(check_in)}"


def _describe(r: ReservationSummary) -> str:
    return f"{r.room_type}, {_spoken_stay(r.check_in, r.nights)}"


def _price_list(options: List[RoomOption]) -> str:
    return ", or ".join(f"the {o.name} at {o.nightly_price_mxn:,} pesos a night" for o in options)


def _suggest(options: List[RoomOption]) -> str:
    if not options:
        return "Sorry, nothing else is available on those dates."
    return f"We have {_price_list(options)}."
