"""Existing display tests focus on chat widgets; pilot tests cover the login gate."""

import pytest


@pytest.fixture(autouse=True)
def isolate_legacy_login(request, monkeypatch):
    if request.node.path.name.startswith("test_pilot_"):
        return
    import frontend_auth

    def signed_in():
        import streamlit as st

        st.session_state.usage = {
            "remaining": 5,
            "limit": 5,
            "resets_at": "2026-11-04T00:00:00+01:00",
        }
        return True

    monkeypatch.setattr(frontend_auth, "require_login", signed_in)
    monkeypatch.setattr(frontend_auth, "usage_card", lambda: None)
