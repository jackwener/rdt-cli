from __future__ import annotations

from rdt_cli.auth import Credential
from rdt_cli.session import SessionState, summarize_session


def test_session_state_from_credential_read_only() -> None:
    cred = Credential(cookies={"reddit_session": "abc"}, source="browser:chrome")
    state = SessionState.from_credential(cred)

    assert state.is_authenticated is True
    assert state.can_write is False
    assert state.source == "browser:chrome"


def test_session_state_infers_write_capability_from_modhash_cookie() -> None:
    cred = Credential(cookies={"reddit_session": "abc", "modhash": "xyz"})
    state = SessionState.from_credential(cred)

    assert state.can_write is True
    assert state.modhash == "xyz"


def test_session_apply_identity_upgrades_capabilities() -> None:
    state = SessionState.from_credential(Credential(cookies={"reddit_session": "abc"}))

    state.apply_identity({"name": "spez", "modhash": "mh"})

    assert state.username == "spez"
    assert state.can_write is True


def test_summarize_session_structured_fields() -> None:
    state = SessionState.from_credential(
        Credential(cookies={"reddit_session": "abc", "modhash": "mh"}, source="saved", username="me")
    )
    summary = summarize_session(state)

    assert summary.authenticated is True
    assert summary.modhash_present is True
    assert "write" in summary.capabilities
