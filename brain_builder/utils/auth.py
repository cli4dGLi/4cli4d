from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Optional

import streamlit as st

import database


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


def _bootstrap_secret_admin() -> bool:
    username = _configured_username()
    password_hash = _configured_password_hash()
    if not username or not password_hash:
        return False
    database.upsert_app_user(
        username=username,
        display_name="Clifford",
        password_hash=password_hash,
        role="admin",
        is_active=True,
    )
    return True


def _valid_username(username: str) -> bool:
    clean = username.strip()
    return 3 <= len(clean) <= 40 and all(ch.isalnum() or ch in {"_", "-", "."} for ch in clean)


def _clear_auth() -> None:
    for key in ["auth_ok", "auth_user", "auth_role", "auth_display_name"]:
        st.session_state.pop(key, None)


def _render_admin_user_tools() -> None:
    if st.session_state.get("auth_role") != "admin":
        return

    with st.sidebar.expander("Admin: users"):
        st.caption("Create tablet logins and reset passwords.")
        with st.form("create-user-form", clear_on_submit=True):
            username = st.text_input("New username", max_chars=40, key="create-username")
            display_name = st.text_input("Display name", max_chars=60, key="create-display-name")
            password = st.text_input("Temporary password", type="password", key="create-password")
            role = st.selectbox("Role", ["learner", "admin"], key="create-role")
            submitted = st.form_submit_button("Create user")
        if submitted:
            clean = database.normalize_username(username)
            if not _valid_username(clean):
                st.warning("Use 3-40 letters, numbers, dot, dash, or underscore.")
            elif len(password) < 8:
                st.warning("Use at least 8 characters for the password.")
            elif database.get_app_user(clean):
                st.warning("That username already exists.")
            else:
                database.create_app_user(clean, display_name or clean, hash_password(password), role)
                st.success(f"Created {clean}.")
                st.rerun()

        users = [dict(row) for row in database.list_app_users()]
        if not users:
            st.info("No users yet.")
            return

        labels = [f"{row['username']} ({row['role']})" for row in users]
        selected_label = st.selectbox("Edit user", labels, key="edit-user-select")
        selected = users[labels.index(selected_label)]
        is_self = selected["username"] == st.session_state.get("auth_user")

        with st.form("edit-user-form"):
            edit_display = st.text_input("Display name", value=selected["display_name"] or selected["username"])
            edit_role = st.selectbox(
                "Role",
                ["learner", "admin"],
                index=0 if selected["role"] == "learner" else 1,
                disabled=is_self,
            )
            edit_active = st.checkbox("Active", value=bool(selected["is_active"]), disabled=is_self)
            new_password = st.text_input("New password", type="password", help="Leave blank to keep current password.")
            saved = st.form_submit_button("Save changes")
        if saved:
            if new_password and len(new_password) < 8:
                st.warning("Use at least 8 characters for the password.")
            else:
                database.update_app_user(
                    selected["username"],
                    display_name=edit_display,
                    password_hash=hash_password(new_password) if new_password else None,
                    role=selected["role"] if is_self else edit_role,
                    is_active=True if is_self else edit_active,
                )
                st.success("User updated.")
                st.rerun()

        st.dataframe(
            [
                {
                    "Username": row["username"],
                    "Name": row["display_name"],
                    "Role": row["role"],
                    "Active": "yes" if row["is_active"] else "no",
                    "Last login": row["last_login_at"] or "",
                }
                for row in users
            ],
            use_container_width=True,
            hide_index=True,
        )


def require_login() -> bool:
    has_secret_admin = _bootstrap_secret_admin()
    if not has_secret_admin and not database.list_app_users():
        st.markdown("# Brain Builder Login")
        st.info(
            "Grown-up setup needed. Add BRAIN_BUILDER_ADMIN_USERNAME and "
            "BRAIN_BUILDER_ADMIN_PASSWORD_HASH to Streamlit secrets."
        )
        return False

    if st.session_state.get("auth_ok"):
        with st.sidebar:
            name = st.session_state.get("auth_display_name") or st.session_state.get("auth_user")
            st.markdown(f"Signed in as **{name}**")
            if st.button("Log out"):
                _clear_auth()
                st.rerun()
            _render_admin_user_tools()
        return True

    st.markdown("# Brain Builder Login")
    st.markdown('<div class="brain-card friendly-text">Grown-up, please sign in first.</div>', unsafe_allow_html=True)
    with st.form("login-form"):
        entered_username = st.text_input("Username", max_chars=40)
        entered_password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        clean = database.normalize_username(entered_username)
        user = database.get_app_user(clean)
        if user and int(user["is_active"]) and verify_password(entered_password, user["password_hash"]):
            st.session_state.auth_ok = True
            st.session_state.auth_user = user["username"]
            st.session_state.auth_role = user["role"]
            st.session_state.auth_display_name = user["display_name"] or user["username"]
            database.record_user_login(user["username"])
            st.rerun()
        st.warning("Please check the username and password.")
    return False
