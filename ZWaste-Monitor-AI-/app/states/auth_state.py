"""App-owned local account authentication for ZWaste Monitor AI.

Security invariants:
  * Passwords are hashed with Argon2 (argon2-cffi) and never stored or
    logged in plaintext.
  * Registration access codes are verified server-side only and never
    persisted or logged; only *which role gate* was satisfied is recorded.
  * The browser holds an OPAQUE random session token (no privileged
    facts). PostgreSQL stores only its SHA-256 hash plus an expiry.
  * Sessions expire after 12 hours, rotate on every login and are cleared
    on logout. Repeated failures trigger a temporary lockout, and every
    credential failure returns the same generic message so accounts
    cannot be enumerated.
"""

from __future__ import annotations

import datetime
import hashlib
import logging
import re
import secrets
from typing import Any, TypedDict

import reflex as rx
from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from sqlalchemy import text

#: Session lifetime (seconds / timedelta) - 12 hours.
SESSION_TTL_SECONDS = 12 * 60 * 60
SESSION_TTL = datetime.timedelta(seconds=SESSION_TTL_SECONDS)

#: Failure throttling.
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15

#: Roles a person may self-register for, with their UI labels.
SELF_REGISTRATION_ROLES: list[tuple[str, str]] = [
    ("VIEWER", "Viewer"),
    ("OPERATOR", "Operator"),
    ("MUNICIPAL_ADMIN", "Manager"),
]
ROLE_LABELS: dict[str, str] = {
    "SUPER_ADMIN": "Super admin",
    "MUNICIPAL_ADMIN": "Manager",
    "OPERATOR": "Operator",
    "DRIVER": "Driver",
    "ANALYST": "Analyst",
    "VIEWER": "Viewer",
}

#: Access codes gating the privileged self-registration roles. VIEWER is
#: absent on purpose: viewers are never prompted for or checked against a
#: code. Never rendered, returned or logged.
_ROLE_ACCESS_CODES: dict[str, str] = {
    "OPERATOR": "2006",
    "MUNICIPAL_ADMIN": "6002",
}

#: Roles allowed to acknowledge/resolve alerts, plan routes and export.
PRIVILEGED_ROLES = ("SUPER_ADMIN", "MUNICIPAL_ADMIN", "OPERATOR")

_GENERIC_CREDENTIAL_ERROR = "Email or password is incorrect."
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")

_hasher = PasswordHasher()
_logger = logging.getLogger(__name__)


class SessionUser(TypedDict):
    id: int
    label: str
    role: str


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _password_problem(password: str) -> str:
    if len(password) < 10:
        return "Password must be at least 10 characters long."
    if not any(c.isupper() for c in password):
        return "Password must contain an uppercase letter."
    if not any(c.islower() for c in password):
        return "Password must contain a lowercase letter."
    if not any(c.isdigit() for c in password):
        return "Password must contain a number."
    return ""


class AuthState(rx.State):
    """Local account session, role facts and the /login workflows."""

    #: Opaque random session token. Carries NO privileged information.
    session_token: str = rx.Cookie(
        "",
        name="zwaste_session",
        max_age=SESSION_TTL_SECONDS,
        path="/",
        same_site="strict",
        secure=True,
    )

    user_id: int = 0
    first_name: str = ""
    surname: str = ""
    email: str = ""
    role: str = "VIEWER"
    session_checked: bool = False

    # ---- /login form state ------------------------------------------------
    mode: str = "login"
    error: str = ""
    notice: str = ""
    reg_role: str = "VIEWER"
    busy: bool = False
    welcome_message: str = ""

    # ---- computed ---------------------------------------------------------
    @rx.var
    def is_authenticated(self) -> bool:
        return self.user_id > 0

    @rx.var
    def full_name(self) -> str:
        name = f"{self.first_name} {self.surname}".strip()
        return name or self.email

    @rx.var
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, "Viewer")

    @rx.var
    def is_privileged(self) -> bool:
        return self.role in PRIVILEGED_ROLES

    @rx.var
    def requires_access_code(self) -> bool:
        return self.reg_role in _ROLE_ACCESS_CODES

    @rx.var
    def role_options(self) -> list[str]:
        return [label for _, label in SELF_REGISTRATION_ROLES]

    @rx.var
    def reg_role_label(self) -> str:
        return ROLE_LABELS.get(self.reg_role, "Viewer")

    # ---- session plumbing -------------------------------------------------
    async def _load_session(self) -> SessionUser | None:
        """Verify the cookie token against PostgreSQL. Fails closed."""
        token = self.session_token
        if not token:
            self._clear_identity()
            return None
        async with rx.asession() as asession:
            row = (
                await asession.execute(
                    text(
                        """
                        SELECT id, first_name, surname, email, role,
                               session_expires_at
                        FROM app_user
                        WHERE session_token_hash = :h AND is_active = TRUE
                        """
                    ),
                    {"h": _hash_token(token)},
                )
            ).first()
        if not row or not row[5] or row[5] <= _now():
            self._clear_identity()
            return None
        self.user_id = int(row[0])
        self.first_name = str(row[1])
        self.surname = str(row[2])
        self.email = str(row[3])
        self.role = str(row[4])
        self.session_checked = True
        return {
            "id": self.user_id,
            "label": f"{self.first_name} {self.surname} <{self.email}>".strip(),
            "role": self.role,
        }

    def _clear_identity(self) -> None:
        self.user_id = 0
        self.first_name = ""
        self.surname = ""
        self.email = ""
        self.role = "VIEWER"
        self.session_checked = True

    @rx.event
    async def verify_privileged(self) -> SessionUser | None:
        """Server-side role verification against the DB session row.

        Called by every mutating handler immediately before it writes.
        """
        session = await self._load_session()
        if session is None or session["role"] not in PRIVILEGED_ROLES:
            return None
        return session

    # ---- page guards ------------------------------------------------------
    @rx.event
    async def require_auth(self):
        session = await self._load_session()
        if session is None:
            self.session_token = ""
            return rx.redirect("/login")
        from app.states.workspace_state import WorkspaceState

        return WorkspaceState.load_workspace()

    @rx.event
    async def redirect_if_authenticated(self):
        self.error = ""
        session = await self._load_session()
        if session is not None:
            return rx.redirect("/")
        return None

    # ---- form events ------------------------------------------------------
    @rx.event
    def set_mode(self, mode: str):
        self.mode = mode
        self.error = ""
        self.notice = ""

    @rx.event
    def set_reg_role_label(self, label: str):
        for value, ui_label in SELF_REGISTRATION_ROLES:
            if ui_label == label:
                self.reg_role = value
                self.error = ""
                return
        self.reg_role = "VIEWER"

    @rx.event
    def dismiss_welcome(self):
        self.welcome_message = ""

    # ---- sign in ----------------------------------------------------------
    @rx.event
    async def sign_in(self, form_data: dict[str, Any]):
        email = _normalize_email(str(form_data.get("email", "")))
        password = str(form_data.get("password", ""))
        self.error = ""
        self.notice = ""
        if not email or not password:
            self.error = _GENERIC_CREDENTIAL_ERROR
            return
        self.busy = True
        yield rx.noop()
        try:
            async with rx.asession() as asession:
                row = (
                    await asession.execute(
                        text(
                            """
                            SELECT id, first_name, surname, email, role,
                                   password_hash, failed_login_count, locked_until
                            FROM app_user
                            WHERE email = :e AND is_active = TRUE
                            """
                        ),
                        {"e": email},
                    )
                ).first()
                now = _now()
                if row is None:
                    self.busy = False
                    self.error = _GENERIC_CREDENTIAL_ERROR
                    return
                if row[7] and row[7] > now:
                    self.busy = False
                    self.error = (
                        "Too many failed sign-in attempts. This account is "
                        f"temporarily locked for {LOCKOUT_MINUTES} minutes."
                    )
                    return
                ok = False
                try:
                    ok = _hasher.verify(str(row[5]), password)
                except (
                    VerifyMismatchError,
                    VerificationError,
                    InvalidHashError,
                ):
                    # Normal bad-password / legacy-hash path: never log a
                    # stack trace or any credential context here.
                    logging.exception("Unexpected error")
                    ok = False
                if not ok:
                    failures = int(row[6] or 0) + 1
                    locked = (
                        now + datetime.timedelta(minutes=LOCKOUT_MINUTES)
                        if failures >= MAX_FAILED_LOGINS
                        else None
                    )
                    await asession.execute(
                        text(
                            """
                            UPDATE app_user
                            SET failed_login_count = :f,
                                last_failed_login_at = :now,
                                locked_until = :locked
                            WHERE id = :id
                            """
                        ),
                        {
                            "f": failures,
                            "now": now,
                            "locked": locked,
                            "id": int(row[0]),
                        },
                    )
                    await asession.commit()
                    self.busy = False
                    self.error = _GENERIC_CREDENTIAL_ERROR
                    return

                token = secrets.token_urlsafe(48)
                await asession.execute(
                    text(
                        """
                        UPDATE app_user
                        SET session_token_hash = :h,
                            session_issued_at = :now,
                            session_expires_at = :exp,
                            last_login_at = :now,
                            failed_login_count = 0,
                            locked_until = NULL
                        WHERE id = :id
                        """
                    ),
                    {
                        "h": _hash_token(token),
                        "now": now,
                        "exp": now + SESSION_TTL,
                        "id": int(row[0]),
                    },
                )
                await asession.execute(
                    text(
                        """
                        INSERT INTO audit_log
                            (user_id, actor_label, actor_role, action,
                             table_name, record_id, summary, source)
                        VALUES (:u, :label, :role, 'LOGIN', 'app_user', :u,
                                'Local account sign-in (session rotated).',
                                'MANUAL')
                        """
                    ),
                    {
                        "u": int(row[0]),
                        "label": f"{row[1]} {row[2]} <{row[3]}>".strip(),
                        "role": str(row[4]),
                    },
                )
                await asession.commit()
        except Exception as exc:  # noqa: BLE001
            logging.exception("Unexpected error")
            _logger.exception(f"Unexpected sign-in failure: {exc}")
            self.busy = False
            self.error = "Sign-in is temporarily unavailable. Try again."
            return

        self.session_token = token
        self.user_id = int(row[0])
        self.first_name = str(row[1])
        self.surname = str(row[2])
        self.email = str(row[3])
        self.role = str(row[4])
        self.session_checked = True
        self.busy = False
        self.welcome_message = self._capability_message()
        yield rx.redirect("/")

    def _capability_message(self) -> str:
        if self.role in PRIVILEGED_ROLES:
            return (
                f"Signed in as {ROLE_LABELS.get(self.role, self.role)}. You "
                "may acknowledge and resolve alerts, approve collection route "
                "plans and generate waste reports. Every action is written to "
                "the audit log against your account."
            )
        return (
            "Signed in as Viewer (read-only). You can explore every dashboard, "
            "map, route and report, but acknowledging alerts, approving route "
            "plans and generating exports are reserved for Operator and "
            "Manager accounts."
        )

    # ---- registration -----------------------------------------------------
    @rx.event
    async def register(self, form_data: dict[str, Any]):
        first_name = str(form_data.get("first_name", "")).strip()
        surname = str(form_data.get("surname", "")).strip()
        email = _normalize_email(str(form_data.get("email", "")))
        password = str(form_data.get("password", ""))
        confirm = str(form_data.get("confirm_password", ""))
        access_code = str(form_data.get("access_code", "")).strip()
        accepted = bool(form_data.get("accept_terms"))
        role = self.reg_role
        self.error = ""
        self.notice = ""

        allowed = [value for value, _ in SELF_REGISTRATION_ROLES]
        if role not in allowed:
            self.error = "Choose Viewer, Operator or Manager."
            return
        if len(first_name) < 2 or len(first_name) > 120:
            self.error = "Enter your first name (at least 2 characters)."
            return
        if len(surname) < 2 or len(surname) > 120:
            self.error = "Enter your surname (at least 2 characters)."
            return
        if not _EMAIL_RE.match(email) or len(email) > 320:
            self.error = "Enter a valid email address."
            return
        problem = _password_problem(password)
        if problem:
            self.error = problem
            return
        if password != confirm:
            self.error = "The two passwords do not match."
            return
        if not accepted:
            self.error = (
                "You must accept the terms of service and privacy policy."
            )
            return
        # VIEWER is never prompted for or checked against an access code.
        expected_code = _ROLE_ACCESS_CODES.get(role)
        if expected_code is not None:
            if not access_code:
                self.error = f"An access code is required for {ROLE_LABELS[role]} accounts."
                return
            if not secrets.compare_digest(access_code, expected_code):
                self.error = (
                    "That access code is not valid for the selected role."
                )
                return

        self.busy = True
        yield rx.noop()
        # Plaintext password and access code are discarded here: only the
        # Argon2 hash and the satisfied role gate are persisted.
        password_hash = _hasher.hash(password)
        now = _now()
        try:
            async with rx.asession() as asession:
                exists = (
                    await asession.execute(
                        text("SELECT 1 FROM app_user WHERE email = :e"),
                        {"e": email},
                    )
                ).first()
                if exists:
                    self.busy = False
                    self.error = (
                        "An account already exists for that email address. "
                        "Sign in instead."
                    )
                    return
                new_id = (
                    await asession.execute(
                        text(
                            """
                            INSERT INTO app_user
                                (first_name, surname, email, password_hash,
                                 password_changed_at, email_verified,
                                 display_name, role, role_code_verified_for,
                                 role_code_verified_at, terms_accepted_at,
                                 privacy_accepted_at, failed_login_count,
                                 is_active)
                            VALUES (:first, :sur, :email, :hash, :now, FALSE,
                                    :display, :role, :gate, :gate_at, :now,
                                    :now, 0, TRUE)
                            RETURNING id
                            """
                        ),
                        {
                            "first": first_name,
                            "sur": surname,
                            "email": email,
                            "hash": password_hash,
                            "now": now,
                            "display": f"{first_name} {surname}",
                            "role": role,
                            "gate": role if expected_code else None,
                            "gate_at": now if expected_code else None,
                        },
                    )
                ).scalar_one()
                await asession.execute(
                    text(
                        """
                        INSERT INTO audit_log
                            (user_id, actor_label, actor_role, action,
                             table_name, record_id, summary, source)
                        VALUES (:u, :label, :role, 'CREATE', 'app_user', :u,
                                :summary, 'MANUAL')
                        """
                    ),
                    {
                        "u": int(new_id),
                        "label": f"{first_name} {surname} <{email}>",
                        "role": role,
                        "summary": (
                            f"Self-registered ZWaste account with role {role}."
                        ),
                    },
                )
                await asession.commit()
        except Exception as exc:  # noqa: BLE001
            logging.exception("Unexpected error")
            _logger.exception(f"Unexpected registration failure: {exc}")
            self.busy = False
            self.error = "The account could not be created. Try again."
            return

        self.busy = False
        self.mode = "login"
        self.notice = (
            f"Account created for {email} as {ROLE_LABELS[role]}. "
            + (
                "Operator and Manager accounts may acknowledge alerts, approve "
                "route plans and generate reports."
                if role in PRIVILEGED_ROLES
                else "Viewer accounts have full read-only access to every "
                "dashboard, map and report."
            )
            + " Sign in below to continue."
        )

    # ---- sign out ---------------------------------------------------------
    @rx.event
    async def sign_out(self):
        token = self.session_token
        if token:
            async with rx.asession() as asession:
                await asession.execute(
                    text(
                        """
                        UPDATE app_user
                        SET session_token_hash = NULL,
                            session_issued_at = NULL,
                            session_expires_at = NULL
                        WHERE session_token_hash = :h
                        """
                    ),
                    {"h": _hash_token(token)},
                )
                await asession.commit()
        self.session_token = ""
        self._clear_identity()
        self.welcome_message = ""
        self.mode = "login"
        self.notice = "You have been signed out and your session was cleared."
        return rx.redirect("/login")
