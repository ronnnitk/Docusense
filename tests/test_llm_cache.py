from docusense import llm
from docusense.schemas import Hit
from docusense.store import Store


def test_second_identical_call_is_served_from_cache(tmp_path, monkeypatch):
    calls = []

    def fake(system, user, num_predict):
        calls.append(user)
        yield "Hello "
        yield "[Source 1]"

    monkeypatch.setattr(llm, "_ollama_stream", fake)
    llm.set_cache(Store(tmp_path / "t.db"))
    hits = [Hit("chunk text", "a.pdf", 1, 0.3)]
    try:
        first = "".join(llm.answer_stream("What?", hits))
        second = "".join(llm.answer_stream("What?", hits))
        assert first == second == "Hello [Source 1]"
        assert len(calls) == 1

        # different evidence in the prompt -> must not reuse the old answer
        "".join(llm.answer_stream("What?", [Hit("other chunk", "a.pdf", 1, 0.3)]))
        assert len(calls) == 2
    finally:
        llm.set_cache(None)


def test_interrupted_or_empty_generation_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "_ollama_stream", lambda *a: iter(["  "]))
    store = Store(tmp_path / "t.db")
    llm.set_cache(store)
    try:
        "".join(llm._chat_stream("s", "u", 10))
        assert store.cache_clear() == 0
    finally:
        llm.set_cache(None)


def test_truncated_output_is_flagged_and_never_cached(tmp_path, monkeypatch):
    def fake(system, user, num_predict):
        yield "Half an ans"
        yield llm._TRUNCATED

    monkeypatch.setattr(llm, "_ollama_stream", fake)
    store = Store(tmp_path / "t.db")
    llm.set_cache(store)
    try:
        out = "".join(llm._chat_stream("s", "u", 10))
        assert out.startswith("Half an ans") and "Cut off" in out
        assert store.cache_clear() == 0          # nothing was stored
    finally:
        llm.set_cache(None)


def test_fresh_bypasses_the_cache_and_refreshes_it(tmp_path, monkeypatch):
    replies = iter(["first answer", "second answer"])
    monkeypatch.setattr(llm, "_ollama_stream", lambda *a: iter([next(replies)]))
    store = Store(tmp_path / "t.db")
    llm.set_cache(store)
    try:
        assert "".join(llm._chat_stream("s", "u", 10)) == "first answer"
        assert "".join(llm._chat_stream("s", "u", 10)) == "first answer"                # cached
        assert "".join(llm._chat_stream("s", "u", 10, fresh=True)) == "second answer"   # forced
        assert "".join(llm._chat_stream("s", "u", 10)) == "second answer"               # cache updated
    finally:
        llm.set_cache(None)


def test_cache_is_bounded(tmp_path, monkeypatch):
    from docusense import store as store_mod
    monkeypatch.setattr(store_mod, "CACHE_MAX_ENTRIES", 5)
    s = Store(tmp_path / "t.db")
    for i in range(20):
        s.cache_put(f"k{i}", "v")
    assert s.cache_clear() == 5
