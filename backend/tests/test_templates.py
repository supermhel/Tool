"""Custom templates: creation, versioning, import, validation."""

import pytest

from app.importers import ImportError_, parse_template

CUSTOM = {
    "id": "vendor-risk", "name": "Vendor risk",
    "criteria": [
        {"id": "security", "label": "Security", "weight": 2, "max": 5},
        {"id": "pricing", "label": "Pricing", "weight": 1, "max": 5},
    ],
}


def _eval(client, **kw):
    return client.post("/api/v1/evaluations", json={
        "template_id": "vendor-risk", "subject": "Acme",
        "scores": {"security": 5, "pricing": 0}} | kw)


def test_custom_template_can_be_used_for_an_evaluation(client):
    """Regression: uploaded templates used to 404 because only the browser knew them."""
    r = client.post("/api/v1/templates", json=CUSTOM)
    assert r.status_code == 201 and r.json()["version"] == 1 and r.json()["builtin"] is False
    assert "vendor-risk" in [t["id"] for t in client.get("/api/v1/templates").json()]
    t = _eval(client).json()
    assert t["score"] == pytest.approx(66.7, abs=0.05)
    assert t["template_id"] == "vendor-risk" and t["template_version"] == 1


def test_new_version_pins_old_tickets_and_is_default(client):
    client.post("/api/v1/templates", json=CUSTOM)
    old = _eval(client).json()
    v2 = dict(CUSTOM, criteria=[
        {"id": "security", "label": "Security", "weight": 1, "max": 5},
        {"id": "pricing", "label": "Pricing", "weight": 1, "max": 5}])
    assert client.post("/api/v1/templates", json=v2).json()["version"] == 2

    assert _eval(client).json()["score"] == pytest.approx(50.0)           # latest = v2
    assert _eval(client, template_version=1).json()["score"] == pytest.approx(66.7, abs=0.05)
    assert client.get(f"/api/v1/tickets/{old['id']}").json()["template_version"] == 1
    assert len(client.get("/api/v1/templates/vendor-risk/versions").json()) == 2
    assert client.get("/api/v1/templates/vendor-risk?version=1").json()["criteria"][0]["weight"] == 2
    assert client.get("/api/v1/templates/vendor-risk").json()["version"] == 2
    assert client.get("/api/v1/templates/vendor-risk?version=9").status_code == 404
    assert _eval(client, template_version=9).status_code == 404


def test_listing_shows_only_latest_version(client):
    client.post("/api/v1/templates", json=CUSTOM)
    client.post("/api/v1/templates", json=CUSTOM)
    mine = [t for t in client.get("/api/v1/templates").json() if t["id"] == "vendor-risk"]
    assert len(mine) == 1 and mine[0]["version"] == 2


def test_cannot_shadow_builtin_ids(client):
    r = client.post("/api/v1/templates", json=dict(CUSTOM, id="process"))
    assert r.status_code == 409


@pytest.mark.parametrize("patch", [
    {"id": "Bad Id!"},
    {"id": ""},
    {"criteria": []},
    {"criteria": [{"id": "a", "label": "A", "weight": 0, "max": 5}]},
    {"criteria": [{"id": "a", "label": "A", "weight": 1, "max": 0}]},
    {"criteria": [{"id": "a", "label": "A", "weight": 1, "max": 5},
                  {"id": "a", "label": "B", "weight": 1, "max": 5}]},
    {"color": "red"},
    {"name": ""},
])
def test_invalid_templates_rejected(client, patch):
    assert client.post("/api/v1/templates", json=CUSTOM | patch).status_code == 422


def test_delete_custom_but_not_builtin(client):
    client.post("/api/v1/templates", json=CUSTOM)
    assert client.delete("/api/v1/templates/vendor-risk").status_code == 200
    assert client.get("/api/v1/templates/vendor-risk").status_code == 404
    assert client.delete("/api/v1/templates/vendor-risk").status_code == 404
    assert client.delete("/api/v1/templates/process").status_code == 409


# ── import ───────────────────────────────────────────────────────────────────

def _import(client, filename, content):
    return client.post("/api/v1/templates/import", json={"filename": filename, "content": content})


def test_import_json(client):
    import json
    r = _import(client, "t.json", json.dumps(CUSTOM))
    assert r.status_code == 201 and r.json()["id"] == "vendor-risk"


def test_import_yaml(client):
    y = ("id: yaml-t\nname: Yaml T\ncriteria:\n"
         "  - {id: a, label: A, weight: 1, max: 10}\n  - {id: b, label: B, weight: 2, max: 10}\n")
    r = _import(client, "t.yaml", y)
    assert r.status_code == 201 and len(r.json()["criteria"]) == 2


def test_import_csv_with_and_without_header(client):
    csv_h = "id,label,max,weight,detail\nsec,Security,5,2,Is it secure\nprice,Pricing,5,1,\n"
    r = _import(client, "vendor risk.csv", csv_h)
    assert r.status_code == 201
    assert r.json()["id"] == "vendor-risk" and r.json()["criteria"][0]["detail"] == "Is it secure"
    r = _import(client, "plain.csv", "a,Alpha,10,1\nb,Beta,10,2\n")
    assert r.status_code == 201 and r.json()["criteria"][1]["weight"] == 2


@pytest.mark.parametrize("filename,content", [
    ("t.docx", "x"),
    ("t.json", "{not json"),
    ("t.json", "[]"),
    ("t.json", '{"id":"a","name":"A"}'),
    ("t.yaml", "a: &x [1]\nb: *x\n"),
    ("t.csv", ""),
    ("t.csv", "id,label,max,weight\na,A,ten,1\n"),
])
def test_bad_imports_rejected(client, filename, content):
    assert _import(client, filename, content).status_code == 422


def test_import_runs_template_validation(client):
    bad = '{"id":"x","name":"X","criteria":[{"id":"a","label":"A","weight":-1,"max":5}]}'
    assert _import(client, "t.json", bad).status_code == 422


def test_import_size_limit(client):
    assert _import(client, "t.json", "x" * 100_001).status_code == 422


def test_parse_template_unit():
    assert parse_template("a.json", '{"name": "My Tpl", "criteria": []}')["id"] == "my-tpl"
    with pytest.raises(ImportError_):
        parse_template("a.txt", "x")
