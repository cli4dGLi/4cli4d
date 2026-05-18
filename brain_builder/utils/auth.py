from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Optional

import streamlit as st


HASH_PREFIX = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 260_000


def hash_password(password: str, salt: bytes | None = None, iterations: int = DEFAULT_ITERATIONS) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "$".join(
        [
            HASH_PREFIX,
            str(iterations),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        prefix, iterations_text, salt_text, digest_text = password_hash.split("$", 3)
        if prefix != HASH_PREFIX:
            return False
        iterations = int(iterations_text)
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    except Exception:
        return False
    return hmac.compare_digest(actual, expected)


def _secret(name: str, default: Optional[str] = None) -> Optional[str]:
    try:
        value = st.secrets.get(name)
        if value:
            return str(value)
    except Exception:
        pass
    return os.environ.get(name, default)


def _configured_username() -> Optional[str]:
    return _secret("BRAIN_BUILDER_ADMIN_USERNAME")


def _configured_password_hash() -> Optional[str]:
    return _secret("BRAIN_BUILDER_ADMIN_PASSWORD_HASH")


def require_login() -> bool:
    username = _configured_username()
    password_hash = _configured_password_hash()
    if not username or not password_hash:
        st.markdown("# Brain Builder Login")
        st.info(
            "Grown-up setup needed. Add BRAIN_BUILDER_ADMIN_USERNAME and "
            "BRAIN_BUILDER_ADMIN_PASSWORD_HASH to Streamlit secrets."
        )
        return False

    if st.session_state.get("auth_ok"):
        with st.sidebar:
            st.markdown(f"Signed in as **{st.session_state.get('auth_user', username)}**")
            if st.button("Log out"):
                st.session_state.pop("auth_ok", None)
                st.session_state.pop("auth_user", None)
                st.rerun()
        return True

    st.markdown("# Brain Builder Login")
    st.markdown('<div class="brain-card friendly-text">Grown-up, please sign in first.</div>', unsafe_allow_html=True)
    with st.form("login-form"):
        entered_username = st.text_input("Username", max_chars=40)
        entered_password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        if hmac.compare_digest(entered_username.strip(), username) and verify_password(entered_password, password_hash):
            st.session_state.auth_ok = True
            st.session_state.auth_user = username
            st.rerun()
        st.warning("Please check the username and password.")
    return False
