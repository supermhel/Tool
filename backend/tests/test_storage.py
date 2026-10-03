"""DocStore contract, run against SQLite and against the Upstash store over real HTTP."""

import pytest

from app import storage
from app.storage import SqliteDocStore, UpstashDocStore
from tests import fakes


@pytest.fixture(params=["sqlite", "upstash"])
def ds(request, tmp_path, monkeypatch):
    if request.param == "sqlite":
        yield SqliteDocStore(str(tmp_path / "ds.db"))
        return
    with fakes.upstash() as (url, _redis, _reqs):
        monkeypatch.setenv("KV_REST_API_URL", url)
        monkeypatch.setenv("KV_REST_API_TOKEN", "tok")
        yield UpstashDocStore()


def test_put_get_roundtrip_unicode(ds):
    ds.put("ticket", "o", "1", {"subject": "café — 日本"})
    assert ds.get("ticket", "o", "1") == {"subject": "café — 日本"}


def test_get_missing(ds):
    assert ds.get("ticket", "o", "nope") is None


def test_list_newest_first_and_oldest_first(ds):
    for i in range(3):
        ds.put("k", "o", str(i), {"i": i})
    assert [d["i"] for d in ds.list("k", "o")] == [2, 1, 0]
    assert [d["i"] for d in ds.list("k", "o", oldest_first=True)] == [0, 1, 2]


def test_list_pagination(ds):
    for i in range(5):
        ds.put("k", "o", str(i), {"i": i})
    assert [d["i"] for d in ds.list("k", "o", limit=2, offset=1)] == [3, 2]
    assert [d["i"] for d in ds.list("k", "o", limit=2, offset=1, oldest_first=True)] == [1, 2]
    assert ds.list("k", "o", limit=2, offset=10) == []


def test_overwrite_keeps_position_and_count(ds):
    ds.put("k", "o", "a", {"v": 1})
    ds.put("k", "o", "b", {"v": 1})
    ds.put("k", "o", "a", {"v": 2})
    assert [d["v"] for d in ds.list("k", "o", oldest_first=True)] == [2, 1]
    assert ds.count("k", "o") == 2


def test_org_and_kind_isolation(ds):
    ds.put("k", "org1", "x", {"o": 1})
    assert ds.get("k", "org2", "x") is None
    assert ds.get("other", "org1", "x") is None
    assert ds.list("k", "org2") == []


def test_delete(ds):
    ds.put("k", "o", "a", {"v": 1})
    assert ds.delete("k", "o", "a") is True
    assert ds.delete("k", "o", "a") is False
    assert ds.list("k", "o") == [] and ds.count("k", "o") == 0


def test_compare_and_set_creates_only_when_absent(ds):
    assert ds.compare_and_set("h", "o", "head", None, {"hash": "a"}) is True
    assert ds.compare_and_set("h", "o", "head", None, {"hash": "b"}) is False
    assert ds.get("h", "o", "head") == {"hash": "a"}


def test_compare_and_set_requires_matching_current_value(ds):
    ds.compare_and_set("h", "o", "head", None, {"hash": "a"})
    assert ds.compare_and_set("h", "o", "head", {"hash": "stale"}, {"hash": "c"}) is False
    assert ds.compare_and_set("h", "o", "head", {"hash": "a"}, {"hash": "b"}) is True
    assert ds.get("h", "o", "head") == {"hash": "b"}


def test_upstash_rejects_a_wrong_token(monkeypatch):
    with fakes.upstash() as (url, _r, _q):
        monkeypatch.setenv("KV_REST_API_URL", url)
        monkeypatch.setenv("KV_REST_API_TOKEN", "wrong")
        with pytest.raises(Exception, match="401"):
            UpstashDocStore().get("k", "o", "x")


def test_make_store_selects_backend(monkeypatch, tmp_path):
    monkeypatch.delenv("KV_REST_API_URL", raising=False)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "x.db"))
    assert isinstance(storage.make_store(), SqliteDocStore)
    monkeypatch.setenv("KV_REST_API_URL", "https://kv.example")
    monkeypatch.setenv("KV_REST_API_TOKEN", "tok")
    assert isinstance(storage.make_store(), UpstashDocStore)
