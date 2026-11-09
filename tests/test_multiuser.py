from streamlit.testing.v1 import AppTest

HEAD = "import sys; sys.path.insert(0, 'src')\nimport streamlit as st\nfrom docusense import shared\nshared.init()\n"


def _app(body, uid=None):
    at = AppTest.from_string(HEAD + body, default_timeout=60)
    if uid:
        at.query_params["u"] = uid
    return at.run()


def test_visitors_have_private_workspaces(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCUSENSE_MULTIUSER", "1")
    monkeypatch.setenv("DOCUSENSE_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("DOCUSENSE_NO_WARMUP", "1")
    import docusense.shared as shared
    monkeypatch.setattr(shared, "USERS_DIR", tmp_path / "users")

    show = "st.json(shared.indexed_sources())"
    a = _app("shared.get_store().register_document('mine.pdf','h',1,1)\n" + show)
    b = _app(show)
    again = _app(show, uid=a.session_state.uid)
    assert not a.exception and not b.exception and not again.exception
    assert a.json[0].value == '["mine.pdf"]'
    assert b.json[0].value == "[]"                      # another visitor sees nothing
    assert again.json[0].value == '["mine.pdf"]'        # same link restores the workspace
    assert a.session_state.uid != b.session_state.uid


def test_bad_uid_in_url_is_replaced(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCUSENSE_MULTIUSER", "1")
    monkeypatch.setenv("DOCUSENSE_NO_WARMUP", "1")
    import docusense.shared as shared
    monkeypatch.setattr(shared, "USERS_DIR", tmp_path / "users")
    at = _app("pass", uid="../../etc")
    assert at.session_state.uid != "../../etc" and len(at.session_state.uid) == 16
