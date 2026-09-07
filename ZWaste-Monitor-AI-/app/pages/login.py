"""Public /login page: local account sign-in and registration."""

from __future__ import annotations

import reflex as rx

from app.states.auth_state import AuthState

_INPUT = (
    "h-10 w-full rounded-[2px] border-0 border-b border-[#8d8d8d] bg-[#f4f4f4] "
    "px-4 text-[14px] font-medium text-[#161616] placeholder:text-[#8d8d8d] "
    "focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe]"
)
_LABEL = "mb-1 block text-[12px] font-semibold uppercase tracking-wide text-[#525252]"


def _field(
    label: str,
    name: str,
    placeholder: str,
    input_type: str = "text",
    auto_complete: str = "off",
) -> rx.Component:
    return rx.el.div(
        rx.el.label(label, class_name=_LABEL, html_for=f"login-{name}"),
        rx.el.input(
            id=f"login-{name}",
            name=name,
            type=input_type,
            placeholder=placeholder,
            auto_complete=auto_complete,
            required=True,
            class_name=_INPUT,
        ),
        class_name="w-full",
    )


def _brand_point(icon: str, title: str, body: str) -> rx.Component:
    return rx.el.li(
        rx.icon(icon, class_name="mt-0.5 h-4 w-4 shrink-0 text-[#42be65]"),
        rx.el.div(
            rx.el.p(
                title,
                class_name="font-['IBM_Plex_Sans_Condensed'] text-[14px] font-semibold uppercase tracking-wide text-white",
            ),
            rx.el.p(body, class_name="text-[13px] font-medium text-white/60"),
            class_name="flex flex-col gap-1",
        ),
        class_name="flex items-start gap-4",
    )


def _brand_panel() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon("recycle", class_name="h-6 w-6 text-[#42be65]"),
            rx.el.span(
                "ZWaste Monitor AI",
                class_name="font-['IBM_Plex_Sans_Condensed'] text-[20px] font-semibold uppercase tracking-wide text-white",
            ),
            class_name="flex items-center gap-4",
        ),
        rx.el.h1(
            "Municipal waste intelligence, in one control room.",
            class_name="mt-8 max-w-md font-['IBM_Plex_Sans_Condensed'] text-[36px] font-semibold leading-tight tracking-tight text-white",
        ),
        rx.el.p(
            "Sensor-driven bin monitoring, fleet operations and transparent forecasts for the municipalities you oversee.",
            class_name="mt-4 max-w-md text-[16px] font-medium text-white/60",
        ),
        rx.el.ul(
            _brand_point(
                "radio",
                "Live sensor telemetry",
                "GateZ readings, overflow alerts and sensor health.",
            ),
            _brand_point(
                "truck",
                "Fleet & route operations",
                "Drivers, vehicles, stops and status workflows.",
            ),
            _brand_point(
                "chart-line",
                "Explainable analytics",
                "Performance scores, forecasts and CSV exports.",
            ),
            class_name="mt-8 flex flex-col gap-6",
        ),
        rx.el.p(
            "SIMULATED DEMONSTRATION DATA — not verified municipal fact.",
            class_name="mt-8 w-fit rounded-[2px] border border-[#f1c21b] px-2 py-1 text-[11px] font-semibold uppercase tracking-widest text-[#f1c21b]",
        ),
        class_name="hidden w-1/2 flex-col justify-center bg-[#0B1A14] p-8 lg:flex",
    )


def _mode_tab(label: str, mode: str) -> rx.Component:
    return rx.el.button(
        label,
        type="button",
        on_click=AuthState.set_mode(mode),
        class_name=rx.cond(
            AuthState.mode == mode,
            "h-10 flex-1 border-b-[3px] border-[#0f62fe] font-['IBM_Plex_Sans_Condensed'] text-[14px] font-semibold uppercase tracking-wide text-[#161616]",
            "h-10 flex-1 border-b-[3px] border-[#e0e0e0] font-['IBM_Plex_Sans_Condensed'] text-[14px] font-semibold uppercase tracking-wide text-[#6f6f6f] transition-colors hover:text-[#161616]",
        ),
    )


def _feedback() -> rx.Component:
    return rx.el.div(
        rx.cond(
            AuthState.error != "",
            rx.el.div(
                rx.icon(
                    "circle-alert",
                    class_name="h-4 w-4 shrink-0 text-[#da1e28]",
                ),
                rx.el.p(
                    AuthState.error,
                    class_name="text-[13px] font-medium text-[#161616]",
                ),
                class_name="flex items-start gap-3 rounded-[2px] border border-[#e0e0e0] border-l-[3px] border-l-[#da1e28] bg-[#fff1f1] px-4 py-3",
            ),
        ),
        rx.cond(
            AuthState.notice != "",
            rx.el.div(
                rx.icon(
                    "circle-check",
                    class_name="h-4 w-4 shrink-0 text-[#24a148]",
                ),
                rx.el.p(
                    AuthState.notice,
                    class_name="text-[13px] font-medium text-[#161616]",
                ),
                class_name="flex items-start gap-3 rounded-[2px] border border-[#e0e0e0] border-l-[3px] border-l-[#24a148] bg-[#defbe6] px-4 py-3",
            ),
        ),
        class_name="flex w-full flex-col gap-2",
    )


def _submit(label: str) -> rx.Component:
    return rx.el.button(
        rx.cond(
            AuthState.busy,
            rx.el.span("Working…"),
            rx.el.span(label),
        ),
        type="submit",
        disabled=AuthState.busy,
        class_name="h-12 w-full rounded-[2px] bg-[#0f62fe] px-4 text-[14px] font-semibold text-white transition-colors hover:bg-[#0353e9] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe] focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-[#c6c6c6]",
    )


def _login_form() -> rx.Component:
    return rx.el.form(
        _field(
            "Email address",
            "email",
            "you@municipality.gov",
            "email",
            "username",
        ),
        _field(
            "Password",
            "password",
            "Enter your password",
            "password",
            "current-password",
        ),
        _submit("Sign in"),
        rx.el.p(
            "Sessions expire automatically after 12 hours. Repeated failed attempts temporarily lock the account.",
            class_name="text-[12px] font-medium text-[#6f6f6f]",
        ),
        on_submit=AuthState.sign_in,
        reset_on_submit=True,
        class_name="flex w-full flex-col gap-4",
    )


def _role_select() -> rx.Component:
    return rx.el.div(
        rx.el.label("Role", class_name=_LABEL, html_for="login-role"),
        rx.el.div(
            rx.el.select(
                rx.foreach(
                    AuthState.role_options,
                    lambda option: rx.el.option(option, value=option),
                ),
                id="login-role",
                value=AuthState.reg_role_label,
                on_change=AuthState.set_reg_role_label,
                class_name="h-10 w-full appearance-none rounded-[2px] border-0 border-b border-[#8d8d8d] bg-[#f4f4f4] px-4 pr-9 text-[14px] font-medium text-[#161616] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe]",
            ),
            rx.icon(
                "chevron-down",
                class_name="pointer-events-none absolute right-3 top-3 h-4 w-4 text-[#525252]",
            ),
            class_name="relative w-full",
        ),
        rx.el.p(
            rx.cond(
                AuthState.requires_access_code,
                "Operator and Manager accounts may acknowledge alerts, approve route plans and generate reports.",
                "Viewer accounts have full read-only access to every dashboard, map and report.",
            ),
            class_name="mt-1 text-[12px] font-medium text-[#6f6f6f]",
        ),
        class_name="w-full",
    )


def _register_form() -> rx.Component:
    return rx.el.form(
        rx.el.div(
            _field("First name", "first_name", "Amara", "text", "given-name"),
            _field("Surname", "surname", "Okoye", "text", "family-name"),
            class_name="grid w-full grid-cols-1 gap-4 sm:grid-cols-2",
        ),
        _field(
            "Email address",
            "email",
            "you@municipality.gov",
            "email",
            "username",
        ),
        rx.el.div(
            _field(
                "Password",
                "password",
                "At least 10 characters",
                "password",
                "new-password",
            ),
            _field(
                "Confirm password",
                "confirm_password",
                "Repeat your password",
                "password",
                "new-password",
            ),
            class_name="grid w-full grid-cols-1 gap-4 sm:grid-cols-2",
        ),
        rx.el.p(
            "Passwords need 10+ characters with an uppercase letter, a lowercase letter and a number.",
            class_name="text-[12px] font-medium text-[#6f6f6f]",
        ),
        _role_select(),
        rx.cond(
            AuthState.requires_access_code,
            rx.el.div(
                rx.el.label(
                    "Access code", class_name=_LABEL, html_for="login-code"
                ),
                rx.el.input(
                    id="login-code",
                    name="access_code",
                    type="password",
                    placeholder="Provided by your municipality administrator",
                    auto_complete="off",
                    required=True,
                    class_name=_INPUT,
                ),
                rx.el.p(
                    "Required to self-register a privileged role. Verified on the server and never stored.",
                    class_name="mt-1 text-[12px] font-medium text-[#6f6f6f]",
                ),
                class_name="w-full",
            ),
        ),
        rx.el.label(
            rx.el.input(
                type="checkbox",
                name="accept_terms",
                class_name="mt-0.5 h-4 w-4 shrink-0 accent-[#0f62fe]",
            ),
            rx.el.span(
                "I confirm I accept the ZWaste terms of service and privacy policy, and that all data in this workspace is simulated demonstration data.",
                class_name="text-[13px] font-medium text-[#161616]",
            ),
            class_name="flex w-full items-start gap-3",
        ),
        _submit("Create account"),
        on_submit=AuthState.register,
        reset_on_submit=False,
        class_name="flex w-full flex-col gap-4",
    )


def login_page() -> rx.Component:
    return rx.el.main(
        _brand_panel(),
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.icon("recycle", class_name="h-5 w-5 text-[#0f62fe]"),
                    rx.el.span(
                        "ZWaste Monitor AI",
                        class_name="font-['IBM_Plex_Sans_Condensed'] text-[16px] font-semibold uppercase tracking-wide text-[#161616]",
                    ),
                    class_name="flex items-center gap-3 lg:hidden",
                ),
                rx.el.h2(
                    rx.cond(
                        AuthState.mode == "login",
                        "Sign in to the operations workspace",
                        "Create your ZWaste account",
                    ),
                    class_name="mt-4 font-['IBM_Plex_Sans_Condensed'] text-[28px] font-semibold leading-none tracking-tight text-[#161616] lg:mt-0",
                ),
                rx.el.p(
                    "Local ZWaste accounts. Passwords are hashed with Argon2 and sessions are stored as hashes only.",
                    class_name="mt-2 text-[13px] font-medium text-[#6f6f6f]",
                ),
                rx.el.div(
                    _mode_tab("Login", "login"),
                    _mode_tab("Create account", "register"),
                    class_name="mt-8 flex w-full items-center",
                ),
                rx.el.div(_feedback(), class_name="mt-4 w-full"),
                rx.el.div(
                    rx.cond(
                        AuthState.mode == "login",
                        _login_form(),
                        _register_form(),
                    ),
                    class_name="mt-4 w-full",
                ),
                class_name="w-full max-w-[480px] border border-[#e0e0e0] bg-white p-8",
            ),
            class_name="flex w-full min-w-0 flex-1 items-center justify-center bg-[#f4f4f4] p-8",
        ),
        class_name="flex min-h-dvh w-full bg-[#f4f4f4] font-['IBM_Plex_Sans'] text-[#161616]",
    )
