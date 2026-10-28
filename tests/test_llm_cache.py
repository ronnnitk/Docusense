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
