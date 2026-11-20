"""The simulated LLM-only baseline must stay labelled as simulated and never count as a measured run."""
import orjson

from app.eval import baseline_llm, baseline_sim


def _pair(pid, label, kind, name_a, name_b, km=0.0):
    a = {"name": name_a, "lat": 25.0, "lng": 55.0}
    b = {"name": name_b, "lat": 25.0 + km / 111, "lng": 55.0}
    return {"pair_id": pid, "label": label, "kind": kind, "a": a, "b": b}


def test_wrong_answers_land_on_the_most_alike_non_matches():
    pairs = [_pair("p1", 0, "hard_negative", "Address Downtown", "Address Downtown Dubai", 0.2),
             _pair("p2", 0, "hard_negative", "Rove Downtown", "Atlantis The Royal", 4.0),
             _pair("p3", 0, "hard_negative", "Hilton Dubai Jumeirah", "Hilton Dubai The Walk", 0.2),
             _pair("p4", 0, "hard_negative", "Premier Inn", "JW Marriott Marquis", 3.0)]
    wrong = baseline_sim._wrong_ids(pairs, 0.5, hardest_first=True)
    assert wrong == {"p1", "p3"}


def test_wrong_answers_land_on_the_least_alike_matches():
    pairs = [_pair("p1", 1, "positive", "Grosvenor House Dubai", "GROSVENOR HOUSE DXB"),
             _pair("p2", 1, "positive", "Grosvenor House Dubai", "Grosvenor House Dubai")]
    assert baseline_sim._wrong_ids(pairs, 0.5, hardest_first=False) == {"p1"}


def test_simulated_results_are_not_reported_as_measured_cost(tmp_path, monkeypatch):
    path = tmp_path / "baseline_results.json"
    monkeypatch.setattr(baseline_llm, "RESULTS_PATH", path)
    path.write_bytes(orjson.dumps({"simulated": True, "summary": {"hotel_cost_per_pair_inr": 0.5}}))
    _, measured = baseline_llm.baseline_cost_per_pair()
    assert measured is False
    path.write_bytes(orjson.dumps({"summary": {"hotel_cost_per_pair_inr": 0.5}}))
    cost, measured = baseline_llm.baseline_cost_per_pair()
    assert measured is True and cost == 0.5
