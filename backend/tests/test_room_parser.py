"""Room parser: 40 table-driven cases across English, Spanish and bed-bank abbreviations.

Each case lists only the fields it asserts. Board and refundability are parsed (they are offer terms)
but must never leak into room identity.
"""
import pytest

from app.pipeline.normalize import parse_board, parse_cancellation, parse_room, room_identity

CASES = [
    # ---- English, clean (DirectConnect style)
    ("Deluxe King Room – Sea View", {"class": "Deluxe", "bed": "King", "view": "Sea"}),
    ("Superior Twin Room – City View", {"class": "Superior", "bed": "Twin", "view": "City"}),
    ("Standard Queen Room", {"class": "Standard", "bed": "Queen", "view": None}),
    ("Junior Suite King – Burj Khalifa View", {"class": "Junior Suite", "bed": "King", "view": "Burj"}),
    ("Executive King Room – Marina View", {"class": "Executive", "bed": "King", "view": "Marina"}),
    ("Premier King Room – Garden View", {"class": "Premier", "bed": "King", "view": "Garden"}),
    ("Deluxe King Room – Pool View (Accessible)", {"class": "Deluxe", "bed": "King", "view": "Pool", "accessible": True}),
    ("Suite King – Sea View", {"class": "Suite", "bed": "King", "view": "Sea"}),
    ("Villa King – Sea View", {"class": "Villa", "bed": "King", "view": "Sea", "occupancy": 4}),
    ("Standard Double Room", {"class": "Standard", "bed": "Double"}),
    # ---- Luxury marketing style (LuxeCollection)
    ("Deluxe Ocean View King with Balcony", {"class": "Deluxe", "bed": "King", "view": "Sea", "extras": ["balcony"]}),
    ("Deluxe Fountain View King with Club Access", {"class": "Deluxe", "bed": "King", "view": "Burj", "extras": ["club access"]}),
    ("Premier Skyline View King", {"class": "Premier", "bed": "King", "view": "City"}),
    ("Accessible Deluxe Pool View King with Lounge Access", {"class": "Deluxe", "view": "Pool", "accessible": True, "extras": ["lounge access"]}),
    ("Executive Burj Khalifa View King", {"class": "Executive", "bed": "King", "view": "Burj"}),
    # ---- Bed-bank abbreviations (GlobalBeds / RapidStay)
    ("DLX DBL SV BB NRF", {"class": "Deluxe", "bed": "Double", "view": "Sea", "board": "BB", "refundable": False}),
    ("DLX K SV RO", {"class": "Deluxe", "bed": "King", "view": "Sea", "board": "RO"}),
    ("SUP TWN CV HB", {"class": "Superior", "bed": "Twin", "view": "City", "board": "HB"}),
    ("STD QN PV RO NRF", {"class": "Standard", "bed": "Queen", "view": "Pool", "refundable": False}),
    ("JR STE K SV BB", {"class": "Junior Suite", "bed": "King", "view": "Sea", "board": "BB"}),
    ("EXEC KG MV", {"class": "Executive", "bed": "King", "view": "Marina"}),
    ("PREM K GV AI", {"class": "Premier", "bed": "King", "view": "Garden", "board": "AI"}),
    ("STE K BV FB", {"class": "Suite", "bed": "King", "view": "Burj", "board": "FB"}),
    ("DLX K PV HCP", {"class": "Deluxe", "bed": "King", "view": "Pool", "accessible": True}),
    ("dlx pv hcp", {"class": "Deluxe", "bed": None, "view": "Pool", "accessible": True}),
    ("STD TWN ACC RO", {"class": "Standard", "bed": "Twin", "accessible": True, "board": "RO"}),
    # ---- Spanish wholesaler (IberiaBeds)
    ("Habitación Doble Deluxe Vista Mar – AD", {"class": "Deluxe", "bed": "Double", "view": "Sea", "board": "BB"}),
    ("Habitación Doble cama King Deluxe Vista Piscina adaptada", {"class": "Deluxe", "bed": "King", "view": "Pool", "accessible": True}),
    ("Habitación Twin Estándar Vista Ciudad – SA", {"class": "Standard", "bed": "Twin", "view": "City", "board": "RO"}),
    ("Habitación Dos camas Superior Vista Jardín – MP", {"class": "Superior", "bed": "Twin", "view": "Garden", "board": "HB"}),
    ("Habitación Doble cama Queen Ejecutiva Vista Marina", {"class": "Executive", "bed": "Queen", "view": "Marina"}),
    ("Junior Suite Vista Burj Khalifa – PC", {"class": "Junior Suite", "view": "Burj", "board": "FB"}),
    ("Suite Vista Mar – TI", {"class": "Suite", "view": "Sea", "board": "AI"}),
    ("Habitación Doble Premier Vista Mar No reembolsable", {"class": "Premier", "view": "Sea", "refundable": False}),
    # ---- Medium abbreviations (NovaBeds) and mixed casing
    ("Dlx King Rm Sea Vw", {"class": "Deluxe", "bed": "King", "view": "Sea"}),
    ("Sup Twin Rm City View", {"class": "Superior", "bed": "Twin", "view": "City"}),
    ("Jr Suite King Burj Vw", {"class": "Junior Suite", "bed": "King", "view": "Burj"}),
    ("Std Double Rm Accessible", {"class": "Standard", "bed": "Double", "accessible": True}),
    ("deluxe king room – sea view", {"class": "Deluxe", "bed": "King", "view": "Sea"}),
    ("Deluxe King Room – Sea View Bed & Breakfast", {"class": "Deluxe", "bed": "King", "view": "Sea", "board": "BB"}),
]


def test_forty_cases():
    assert len(CASES) == 40


@pytest.mark.parametrize("text,expected", CASES, ids=[c[0] for c in CASES])
def test_parse_room(text, expected):
    parsed = parse_room(text)
    for key, value in expected.items():
        if key == "extras":
            for extra in value:
                assert extra in parsed["extras"], (text, parsed["extras"])
        else:
            assert parsed[key] == value, (text, key, parsed[key], value)


def test_board_and_refundability_never_decide_identity():
    a = room_identity(parse_room("DLX K SV BB"))
    b = room_identity(parse_room("DLX K SV RO NRF"))
    c = room_identity(parse_room("Habitación Doble cama King Deluxe Vista Mar – AD"))
    assert a == b
    assert a["class"] == c["class"] and a["view"] == c["view"]
    assert "board" not in a and "refundable" not in a


@pytest.mark.parametrize("raw,board", [
    ("Bed & Breakfast", "BB"), ("AD", "BB"), ("Breakfast included", "BB"), ("SA", "RO"), ("Room only", "RO"),
    ("MP", "HB"), ("Half board (breakfast & dinner)", "HB"), ("PC", "FB"), ("All-inclusive", "AI"), ("No meals", "RO"),
])
def test_parse_board(raw, board):
    assert parse_board(raw) == board


@pytest.mark.parametrize("raw,refundable,hours", [
    ("NRF", False, 0), ("Non-refundable", False, 0), ("No reembolsable", False, 0),
    ("CXL 72H", True, 72), ("Free cancellation until 48h before check-in", True, 48),
    ("Free cancellation until 7 days before arrival", True, 168), ("Cancelación gratuita hasta 48h antes", True, 48),
])
def test_parse_cancellation(raw, refundable, hours):
    assert parse_cancellation(raw) == (refundable, hours)
