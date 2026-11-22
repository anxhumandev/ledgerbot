"""Sightseeing option equivalence and hotel rate-plan keys (pure unit tests, no server)."""
from app.pipeline import activities as act
from app.pipeline import offers as off
from app.pipeline.normalize import duration_range


def L(lid, sup, title, duration, **extra):
    return {"listing_id": lid, "supplier": sup, "title": title, "duration": duration, "language": "English",
            "meeting_point": "Hotel lobby", "inclusions": "Guide", "prices": {"adult": 1000, "child": 800, "infant": 0}, "city": "Dubai", **extra}


def options_of(listings):
    prods = act.build_products(listings)
    assert len(prods) == 1, [p["label"] for p in prods]
    return prods[0]["options"]


def test_duration_ranges():
    assert duration_range("4h") == (204, 276)
    assert duration_range("1h 30m") == (60, 120)
    assert duration_range("half day") == (180, 360)
    assert duration_range("Full Day") == (360, 720)
    assert duration_range(None) is None


def test_different_durations_are_different_options():
    opts = options_of([L("a", "S1", "Old Dubai Walking Tour", "2h"), L("b", "S3", "Old Dubai Walking Tour", "4h")])
    assert len(opts) == 2
    assert len({o["label"] for o in opts}) == 2, "options that differ only by duration must be labelled apart"


def test_same_duration_in_different_wording_is_one_option():
    opts = options_of([L("a", "S1", "Old Dubai Walking Tour", "5h"), L("b", "S3", "Old Dubai Walking Tour", "300 minutos"),
                       L("c", "S5", "Old Dubai Walking Tour", "half day"), L("d", "S2", "Old Dubai Walking Tour", None)])
    assert len(opts) == 1 and len(opts[0]["units"]) == 4


def test_cancellation_terms_split_options_when_present():
    opts = options_of([L("a", "S1", "Old Dubai Walking Tour", "3h", cancellation="Free cancellation up to 24 hours"),
                       L("b", "S3", "Old Dubai Walking Tour", "3h", cancellation="Non-refundable"),
                       L("c", "S5", "Old Dubai Walking Tour", "3h", cancellation="Free cancellation 24h before")])
    assert len(opts) == 2
    by = {o["cancellation"]["refundable"]: o for o in opts}
    assert len(by[True]["units"]) == 2 and len(by[False]["units"]) == 1


def test_world_option_quality_not_reduced():
    import orjson
    from app import config
    listings = orjson.loads((config.WORLD_DIR / "activities_raw.json").read_bytes())
    truth = orjson.loads((config.WORLD_DIR / "truth.json").read_bytes())["activity_of_listing"]
    ev = act.evaluate(act.build_products(listings), truth)
    assert ev["option"]["f1"] >= 0.96 and ev["product"]["f1"] >= 0.96


def _o(**kw):
    base = {"board": "BB", "refundable": True, "cancel_hours": 48, "payment": "prepay", "occupancy": 2, "nights": 1}
    return {**base, **kw}


def test_rate_plan_key_separates_deadline_and_payment_but_slot_does_not():
    a, b, c = _o(), _o(cancel_hours=24), _o(payment="pay_later")
    assert off.slot_key(0, a) == off.slot_key(0, b) == off.slot_key(0, c), "same comparable group"
    assert len({off.rate_plan_key(x) for x in (a, b, c)}) == 3, "three different rate plans"
    nr1, nr2 = _o(refundable=False, cancel_hours=0), _o(refundable=False, cancel_hours=12)
    assert off.rate_plan_key(nr1) == off.rate_plan_key(nr2), "deadline is irrelevant when non-refundable"
    assert "pay later" in off.rate_plan_label(c) and "24 h" in off.rate_plan_label(b)
