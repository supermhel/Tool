from app.storage import JsonStore


def make_store(tmp_path):
    return JsonStore(str(tmp_path / "tickets.json"))


def test_create_returns_ticket_with_id_and_timestamp(tmp_path):
    store = make_store(tmp_path)
    t = store.create({"subject": "x", "score": 80.0})
    assert t["id"]
    assert t["created_at"]
    assert t["subject"] == "x"


def test_list_empty(tmp_path):
    store = make_store(tmp_path)
    assert store.list() == []


def test_create_and_list(tmp_path):
    store = make_store(tmp_path)
    store.create({"subject": "x"})
    assert len(store.list()) == 1


def test_newest_first(tmp_path):
    store = make_store(tmp_path)
    t1 = store.create({"subject": "first"})
    t2 = store.create({"subject": "second"})
    lst = store.list()
    assert lst[0]["id"] == t2["id"]
    assert lst[1]["id"] == t1["id"]


def test_get_existing(tmp_path):
    store = make_store(tmp_path)
    t = store.create({"subject": "x"})
    assert store.get(t["id"]) == t


def test_get_missing_returns_none(tmp_path):
    store = make_store(tmp_path)
    assert store.get("nosuchid") is None


def test_delete_existing(tmp_path):
    store = make_store(tmp_path)
    t = store.create({"subject": "x"})
    assert store.delete(t["id"]) is True
    assert store.list() == []


def test_delete_missing_returns_false(tmp_path):
    store = make_store(tmp_path)
    assert store.delete("nosuchid") is False


def test_delete_does_not_affect_others(tmp_path):
    store = make_store(tmp_path)
    t1 = store.create({"subject": "keep"})
    t2 = store.create({"subject": "drop"})
    store.delete(t2["id"])
    lst = store.list()
    assert len(lst) == 1
    assert lst[0]["id"] == t1["id"]


def test_atomic_write_does_not_corrupt(tmp_path):
    store = make_store(tmp_path)
    for i in range(5):
        store.create({"subject": f"ticket-{i}"})
    assert len(store.list()) == 5
