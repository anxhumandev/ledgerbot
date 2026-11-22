"""End-to-end tests of the enterprise workspace API against the real pipeline build (temporary database)."""
from __future__ import annotations

import json
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from app import config, store

OPS = {"X-LedgerBot-User": "u-rahul"}
REVENUE = {"X-LedgerBot-User": "u-sara"}
ADMIN = {"X-LedgerBot-User": "u-admin"}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    config.DB_PATH = tmp_path_factory.mktemp("db") / "ws.sqlite3"
    store._CONN = None
    from app.main import app
    with TestClient(app) as c:
        assert c.get("/api/health").json()["ok"], "run `make data train` first"
        yield c


def test_identity_and_permissions(client):
    me = client.get("/api/me", headers=ADMIN).json()
    assert me["user"]["role"] == "admin" and len(me["users"]) == 4
    assert client.get("/api/me", headers={"X-LedgerBot-User": "u-priya"}).json()["user"]["role"] == "analyst"
    assert client.get("/api/me", headers={"X-LedgerBot-User": "u-nobody"}).json()["user"] is None
    r = client.put("/api/settings/price_cap_pct", json={"value": 3})
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"
    r = client.put("/api/settings/price_cap_pct", json={"value": 3}, headers=OPS)
    assert r.status_code == 403
    r = client.put("/api/settings/price_cap_pct", json={"value": 99}, headers=REVENUE)
    assert r.status_code == 422 and r.json()["error"]["details"]["field"] == "price_cap_pct"


def test_inventory_filter_sort_search(client):
    r = client.get("/api/inventory", params={"type": "hotel", "page_size": 10}).json()
    assert r["total"] > 2000 and len(r["items"]) == 10
    dubai = client.get("/api/inventory", params={"city": "dubai", "page_size": 200}).json()
    assert dubai["total"] < r["total"] and all(i["city"] == "dubai" for i in dubai["items"])
    srt = client.get("/api/inventory", params={"sort": "n_suppliers", "order": "desc", "page_size": 20}).json()["items"]
    assert [i["n_suppliers"] for i in srt] == sorted([i["n_suppliers"] for i in srt], reverse=True)
    hit = client.get("/api/inventory", params={"q": "atlantis the palm"}).json()["items"]
    assert any(i["name"] == "Atlantis The Palm" for i in hit)
    assert client.get("/api/inventory", params={"sort": "nope"}).status_code == 400
    acts = client.get("/api/inventory", params={"type": "activity"}).json()
    assert acts["total"] == 33 and acts["items"][0]["category"] == "Sightseeing"


def test_hotel_and_activity_detail(client):
    tid = client.get("/api/inventory", params={"q": "atlantis the palm"}).json()["items"][0]["id"]
    d = client.get(f"/api/inventory/hotel/{tid}").json()
    assert d["records"] and d["rooms"] and d["links"] and d["headline_offer"]
    assert client.get("/api/inventory/hotel/TS-NOPE").status_code == 404
    burj = [p for p in client.get("/api/inventory", params={"type": "activity", "q": "burj"}).json()["items"]]
    assert len(burj) == 2, "levels 124/125 and 148 must stay separate products"
    a = client.get(f"/api/inventory/activity/{burj[0]['id']}").json()
    assert a["kept_separate_products"] and len(a["options"]) >= 2


def _hotel_with_rates(client):
    tid = client.get("/api/inventory", params={"q": "atlantis the palm"}).json()["items"][0]["id"]
    return tid, client.get(f"/api/offers/hotel/{tid}", params={"nights": 3}).json()


def test_offer_groups_keep_terms_apart_and_recommendation_is_coherent(client):
    tid, o = _hotel_with_rates(client)
    for room in o["rooms"]:
        keys = [(g["board"], g["refundable"]) for g in room["groups"]]
        assert len(keys) == len(set(keys)), "a room must never have two groups with the same board and refundability"
        for g in room["groups"]:
            assert all(x["board"] == g["board"] and x["refundable"] == g["refundable"] for x in g["offers"])
            rec = g["recommended"]
            if rec:
                src = next(x for x in g["offers"] if x["offer_id"] == rec["offer_id"])
                assert (rec["total"], rec["cancel_hours"], rec["payment"], rec["supplier"]) == \
                       (src["total"], src["cancel_hours"], src["payment"], src["supplier"])
                assert rec["premium_pct"] <= o["cap_pct"] + 1e-6
                assert rec["total"] == src["per_night"] * 3


def test_price_cap_blocks_expensive_winner(client):
    tid, before = _hotel_with_rates(client)
    assert client.put("/api/settings/price_cap_pct", json={"value": 0}, headers=REVENUE).status_code == 200
    o = client.get(f"/api/offers/hotel/{tid}").json()
    for room in o["rooms"]:
        for g in room["groups"]:
            if g["recommended"]:
                assert g["recommended"]["cheapest"] or g["recommended"]["premium_pct"] == 0
    client.put("/api/settings/price_cap_pct", json={"value": 5}, headers=REVENUE)


def test_activity_options_keep_inclusions_apart(client):
    pid = client.get("/api/inventory", params={"type": "activity", "q": "desert safari"}).json()["items"][0]["id"]
    o = client.get(f"/api/offers/activity/{pid}").json()
    keys = [(x["time_slot"], x["transfer"], x["meal"], x["private"], x["language"], tuple(x["addons"])) for x in o["options"]]
    assert len(keys) == len(set(keys))
    assert any(x["meal"] for x in o["options"]) and any(not x["meal"] for x in o["options"])


def test_review_decision_persists_changes_catalog_and_is_idempotent(client):
    cases = client.get("/api/review/cases").json()["items"]
    assert cases, "the review band should not be empty at the default alpha"
    case = next(c for c in cases if not c["mapping"]["same_property"] and not c["mapping"]["merge_conflict_suppliers"])
    c = client.get(f"/api/review/cases/{case['id']}").json()
    assert c["explain"]["items"] and c["diffs"]
    # analysts cannot skip the version check
    stale = client.post(f"/api/review/cases/{case['id']}/decision", json={"decision": "confirm", "version": c["version"] + 5}, headers=ADMIN)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_version"
    # role check
    assert client.post(f"/api/review/cases/{case['id']}/decision", json={"decision": "confirm", "version": c["version"]},
                       headers=REVENUE).status_code == 403
    key = {"Idempotency-Key": "k-confirm-1", **ADMIN}
    r1 = client.post(f"/api/review/cases/{case['id']}/decision", json={"decision": "confirm", "reason": "same phone and address",
                                                                      "version": c["version"]}, headers=key)
    assert r1.status_code == 200, r1.text
    assert r1.json()["case"]["status"] == "confirmed" and r1.json()["case"]["mapping"]["same_property"]
    r2 = client.post(f"/api/review/cases/{case['id']}/decision", json={"decision": "confirm", "version": c["version"]}, headers=key)
    assert r2.status_code == 200 and r2.json() == r1.json(), "same key must replay the same response, not decide twice"
    again = client.post(f"/api/review/cases/{case['id']}/decision", json={"decision": "reject", "reason": "x y z",
                                                                         "version": r1.json()["case"]["version"]}, headers=ADMIN)
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_decided"
    tid = r1.json()["case"]["mapping"]["property_a"]
    hotel = client.get(f"/api/inventory/hotel/{tid}").json()
    assert {case["record_a"], case["record_b"]} <= {r["record_id"] for r in hotel["records"]}
    hist = client.get("/api/audit", params={"entity_id": case["id"]}).json()["items"]
    assert any(e["action"] == "review.confirmed" and e["actor"] == "u-admin" for e in hist)
    # undo restores the previous mapping
    undone = client.post(f"/api/review/cases/{case['id']}/reopen", json={"reason": "decided too fast"}, headers=ADMIN).json()
    assert undone["status"] == "open" and not undone["mapping"]["same_property"]


def test_reject_splits_a_merged_pair(client):
    cases = client.get("/api/review/cases").json()["items"]
    case = next((c for c in cases if c["mapping"]["same_property"]), None)
    if case is None:
        pytest.skip("no merged pair in the band")
    c = client.get(f"/api/review/cases/{case['id']}").json()
    r = client.post(f"/api/review/cases/{case['id']}/decision", json={"decision": "reject", "reason": "different street address",
                                                                     "version": c["version"]}, headers=ADMIN)
    assert r.status_code == 200, r.text
    m = r.json()["case"]["mapping"]
    assert not m["same_property"] and m["property_a"] != m["property_b"]
    assert client.post(f"/api/review/cases/{case['id']}/decision", json={"decision": "reject", "version": c["version"]},
                       headers=ADMIN).status_code in (409, 422)


def test_ingestion_validation_errors(client):
    bad = client.post("/api/ingestion/jobs", data={"supplier": "S6"}, files={"file": ("feed.json", b"{not json", "application/json")}, headers=OPS)
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "malformed_file"
    csv_bad = client.post("/api/ingestion/jobs", data={"supplier": "S6"}, files={"file": ("f.csv", b"id,title\n1,x\n", "text/csv")}, headers=OPS)
    assert csv_bad.status_code == 422 and csv_bad.json()["error"]["code"] == "schema_mismatch"
    txt = client.post("/api/ingestion/jobs", data={"supplier": "S6"}, files={"file": ("f.txt", b"hello", "text/plain")}, headers=OPS)
    assert txt.status_code == 415
    dup = json.dumps({"hotels": [{"record_id": "X1", "name": "A", "city": "Dubai"}, {"record_id": "X1", "name": "B", "city": "Dubai"},
                                 {"record_id": "X2", "name": "", "city": "Atlantis"}]}).encode()
    j = client.post("/api/ingestion/jobs", data={"supplier": "S6"}, files={"file": ("d.json", dup, "application/json")}, headers=OPS).json()
    assert j["status"] == "validated" and j["valid"] == 1 and j["invalid"] == 2
    msgs = " ".join(i["message"] for i in j["issues"])
    assert "Duplicate record_id" in msgs and "Unknown city" in msgs and "Missing name" in msgs
    assert client.post("/api/ingestion/jobs", data={"supplier": "S6"}, files={"file": ("d.json", dup, "application/json")},
                       headers=REVENUE).status_code == 403


def test_ingestion_job_runs_real_pipeline(client):
    raw = client.get("/api/ingestion/sample", params={"format": "json"}).content
    feed = json.loads(raw)
    feed["hotels"] = feed["hotels"][:6]
    ids = {h["record_id"] for h in feed["hotels"]}
    feed["rooms"] = [r for r in feed["rooms"] if r["record_id"] in ids]
    feed["offers"] = [o for o in feed["offers"] if o["record_id"] in ids]
    j = client.post("/api/ingestion/jobs", data={"supplier": "S6"}, files={"file": ("nb.json", json.dumps(feed).encode(), "application/json")},
                    headers=OPS).json()
    assert j["status"] == "validated" and j["valid"] == 6
    client.post(f"/api/ingestion/jobs/{j['id']}/start", headers=OPS)
    for _ in range(120):
        st = client.get(f"/api/ingestion/jobs/{j['id']}").json()
        if st["status"] in ("completed", "failed"):
            break
        time.sleep(0.5)
    assert st["status"] == "completed", st.get("error")
    assert st["processed"] == 6 and st["merged"] + st["created"] + st["review"] + st["updated"] == 6
    assert len(st["results"]) == 6
    merged = next((r for r in st["results"] if r["outcome"] == "attach"), None)
    if merged:
        h = client.get(f"/api/inventory/hotel/{merged['tessera_id']}").json()
        assert "S6" in h["suppliers"]
    assert client.post(f"/api/ingestion/jobs/{j['id']}/start", headers=OPS).status_code == 409


def test_catalog_rebuild_reproduces_state(client):
    from app.demo import DEMO
    from app.services import catalog
    snapshot = {tid: sorted(h["members"]) for tid, h in DEMO.hotels.items()}
    catalog.rebuild()
    assert {tid: sorted(h["members"]) for tid, h in DEMO.hotels.items()} == snapshot


def test_audit_log_is_append_only(client):
    db = sqlite3.connect(config.DB_PATH)
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("UPDATE audit_events SET actor = 'mallory'")
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("DELETE FROM audit_events")
    db.close()


def test_overview_analytics_ranking(client):
    ov = client.get("/api/overview").json()
    keys = {k["key"] for k in ov["kpis"]}
    assert {"suppliers", "listings", "canonical", "dedup", "reviews", "reliability", "competitiveness", "quality"} <= keys
    assert all(k["source"] in ("measured", "simulated", "live") for k in ov["kpis"])
    assert ov["issues"] and ov["activity"]
    an = client.get("/api/analytics").json()
    assert an["matching"]["pairwise"]["f1"] > 0.8
    rk = client.get("/api/ranking/hotels", params={"persona": "riya", "strategy": "price"}).json()["results"]
    totals = [r["offer"]["total"] for r in rk if r["offer"]]
    assert totals == sorted(totals)
    cmp_ = client.get("/api/ranking/compare", params={"a": "relevance", "b": "balanced"}).json()
    assert cmp_["rows"] and "ndcg" in cmp_["offline_quality"]
    act = client.get("/api/ranking/activities", params={"q": "burj"}).json()
    assert act["results"] and "Rule-based" in act["model"]


def test_structured_validation_error(client):
    r = client.get("/api/inventory", params={"page": 0})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request" and r.headers.get("X-Request-ID")
