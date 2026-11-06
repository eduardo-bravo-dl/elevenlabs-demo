from datetime import date, time
from typing import Annotated, List, Literal, Optional

from pydantic import AfterValidator, BaseModel, Field, model_validator

from app.config import today_in_hotel
from app.phone import normalize_mx_phone

MAX_STAY_NIGHTS = 30

MxPhone = Annotated[str, AfterValidator(normalize_mx_phone)]
ReservationStatus = Literal["confirmed", "checked_in", "checked_out", "cancelled"]
TicketCategory = Literal["late_checkout", "reservation_change", "billing", "housekeeping",
                         "maintenance", "complaint", "other"]
TicketPriority = Literal["low", "normal", "high", "urgent"]


class FindReservationRequest(BaseModel):
    phone: Optional[MxPhone] = Field(None, examples=["+52 55 5010 0001"])
    confirmation_code: Optional[str] = Field(None, examples=["CJ1001"])
    last_name: Optional[str] = Field(None, examples=["Hernandez"])

    @model_validator(mode="after")
    def one_lookup_method(self):
        if not self.phone and not (self.confirmation_code and self.last_name):
            raise ValueError("Provide phone, or confirmation_code plus last_name.")
        return self


class ReservationSummary(BaseModel):
    reservation_id: int
    confirmation_code: str
    guest_first_name: str
    room_type: str
    check_in: date
    check_out: date
    nights: int
    guests: int
    status: ReservationStatus


class FindReservationResponse(BaseModel):
    found: bool
    multiple: bool = False
    reservation: Optional[ReservationSummary] = None
    reservations: List[ReservationSummary] = Field(default_factory=list)
    message: str


class CheckAvailabilityRequest(BaseModel):
    check_in: date
    check_out: date
    guests: int = Field(ge=1, le=10)
    room_type: Optional[str] = Field(None, examples=["suite"])

    @model_validator(mode="after")
    def valid_dates(self):
        if self.check_in < today_in_hotel():
            raise ValueError("check_in cannot be in the past.")
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in.")
        if (self.check_out - self.check_in).days > MAX_STAY_NIGHTS:
            raise ValueError(f"Stays are limited to {MAX_STAY_NIGHTS} nights.")
        return self


class RoomOption(BaseModel):
    room_type: str
    name: str
    max_guests: int
    nightly_price_mxn: int
    total_price_mxn: int
    rooms_left: int


class CheckAvailabilityResponse(BaseModel):
    available: bool
    check_in: date
    check_out: date
    nights: int
    options: List[RoomOption] = Field(default_factory=list)
    alternatives: List[RoomOption] = Field(default_factory=list)
    message: str


class LateCheckoutRequest(BaseModel):
    reservation_id: int
    requested_time: time = Field(examples=["13:30"])


class LateCheckoutResponse(BaseModel):
    status: Literal["approved", "rejected", "not_needed", "not_found"]
    approved: bool
    reservation_id: int
    requested_time: str
    checkout_time: str
    latest_available_time: Optional[str] = None
    reason: Optional[str] = None
    already_requested: bool = False
    message: str


class CreateTicketRequest(BaseModel):
    reservation_id: Optional[int] = None
    category: TicketCategory
    priority: TicketPriority = "normal"
    summary: str = Field(min_length=3, max_length=500)
    guest_phone: MxPhone = Field(examples=["5550100001"])


class CreateTicketResponse(BaseModel):
    ticket_id: str
    status: Literal["open"]
    reservation_linked: bool
    message: str
