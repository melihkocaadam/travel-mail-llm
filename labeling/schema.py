
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

TimeType = Literal["exact", "range", "after", "before", "unspecified"]
DateType = Literal["exact", "range", "after", "before", "unspecified"]

class DateSpec(BaseModel):
    type: DateType
    exact: Optional[str] = None   # YYYY-MM-DD
    from_: Optional[str] = Field(default=None, alias="from")  # YYYY-MM-DD
    to: Optional[str] = None      # YYYY-MM-DD
    text: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)

class TimeSpec(BaseModel):
    type: TimeType
    exact: Optional[str] = None   # HH:MM
    from_: Optional[str] = Field(default=None, alias="from")  # HH:MM
    to: Optional[str] = None      # HH:MM
    text: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)

class Leg(BaseModel):
    from_: Optional[str] = Field(default=None, alias="from")
    to: Optional[str] = Field(default=None, alias="to")
    date: Optional[DateSpec] = None
    time: Optional[TimeSpec] = None

    model_config = ConfigDict(populate_by_name=True)

class Pax(BaseModel):
    adult: int
    child: int
    infant: int

class Baggage(BaseModel):
    hand: Optional[int] = None
    hold: Optional[int] = None

class FlightRequest(BaseModel):
    trip_type: Literal["one_way", "round_trip", "multi_city"]
    pnr: Optional[str] = None
    airline_preference: Optional[str] = None
    cabin: Optional[Literal["ECONOMY", "BUSINESS", "FIRST", "PREMIUM_ECONOMY"]] = None
    legs: List[Leg]
    pax: Pax
    baggage: Baggage
    currency: Optional[str] = None
    budget_total: Optional[float] = None
    notes: Optional[str] = None
    po_number: Optional[str] = None

class HotelPax(BaseModel):
    adult: int
    child: int

class HotelDate(BaseModel):
    check_in: DateSpec
    check_out: DateSpec

class HotelRequest(BaseModel):
    city: Optional[str] = None
    area: Optional[str] = None
    date: Optional[HotelDate] = None
    nights: Optional[int] = None
    rooms: Optional[int] = None
    pax: HotelPax
    purpose: Optional[Literal["business", "leisure", "mixed"]] = None
    theme: Optional[Literal["city_center", "sea_side", "ski", "conference"]] = None
    hotel_class: Optional[int] = None
    budget_total: Optional[float] = None
    currency: Optional[str] = None
    notes: Optional[str] = None
    po_number: Optional[str] = None

class TransferPax(BaseModel):
    adult: int
    child: int
    infant: int

class TransferRequest(BaseModel):
    direction: Optional[Literal["arrival", "departure", "roundtrip", "other"]] = None
    from_: Optional[str] = Field(default=None, alias="from")
    to: Optional[str] = Field(default=None, alias="to")
    date: Optional[DateSpec] = None
    time: Optional[TimeSpec] = None
    pax: TransferPax
    luggage_pieces: Optional[int] = None
    notes: Optional[str] = None
    po_number: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)

class RequestItem(BaseModel):
    type: Literal["flight", "hotel", "transfer"]
    flight: Optional[FlightRequest] = None
    hotel: Optional[HotelRequest] = None
    transfer: Optional[TransferRequest] = None

class EmailRequest(BaseModel):
    requests: List[RequestItem]
