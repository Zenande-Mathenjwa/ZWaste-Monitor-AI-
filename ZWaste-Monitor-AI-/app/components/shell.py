"""Operational header, municipality selector and responsive tab navigation."""

from __future__ import annotations

import reflex as rx

from app.components.ui import notification
from app.states.auth_state import AuthState
from app.states.workspace_state import TABS, WorkspaceState


def _municipality_option(option: dict) -> rx.Component:
    return rx.el.option(
        f"{option['name']} · {option['code']}",
        value=option["id"].to_string(),
    )


def _tab(name: str) -> rx.Component:
    return rx.el.button(
        name,
        on_click=lambda: WorkspaceState.set_active_tab(name),
        class_name=rx.cond(
            WorkspaceState.active_tab == name,
            "h-12 shrink-0 border-b-[3px] border-[#0f62fe] px-4 font-['IBM_Plex_Sans_Condensed'] text-[14px] font-semibold uppercase tracking-wide text-[#161616] focus:outline-hidden focus:ring-2 focus:ring-inset focus:ring-[#0f62fe]",
            "h-12 shrink-0 border-b-[3px] border-transparent px-4 font-['IBM_Plex_Sans_Condensed'] text-[14px] font-semibold uppercase tracking-wide text-[#6f6f6f] transition-colors hover:border-[#c6c6c6] hover:text-[#161616] focus:outline-hidden focus:ring-2 focus:ring-inset focus:ring-[#0f62fe]",
        ),
    )


def header() -> rx.Component:
    return rx.el.header(
        rx.el.div(
            rx.el.div(
                rx.icon("recycle", class_name="h-5 w-5 text-[#42be65]"),
                rx.el.span(
                    "ZWaste Monitor AI",
                    class_name="font-['IBM_Plex_Sans_Condensed'] text-[16px] font-semibold uppercase tracking-wide text-white",
                ),
                rx.el.span(
                    "Municipality operations",
                    class_name="hidden text-[12px] font-medium uppercase tracking-widest text-white/50 md:block",
                ),
                class_name="flex items-center gap-3",
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.span(
                        AuthState.full_name,
                        class_name="text-[13px] font-semibold text-white",
                    ),
                    rx.el.span(
                        AuthState.email,
                        class_name="text-[12px] font-medium text-white/60",
                    ),
                    class_name="hidden flex-col leading-tight lg:flex",
                ),
                rx.el.span(
                    AuthState.role_label,
                    class_name="hidden w-fit rounded-[2px] border border-white/20 bg-white/10 px-2 py-1 text-[11px] font-semibold uppercase tracking-widest text-white sm:block",
                ),
                rx.el.button(
                    rx.icon("log-out", class_name="h-4 w-4"),
                    rx.el.span("Log out", class_name="hidden sm:block"),
                    on_click=AuthState.sign_out,
                    class_name="flex h-8 items-center gap-2 rounded-[2px] border border-white/25 px-3 text-[13px] font-semibold text-white transition-colors hover:bg-white/10 focus:outline-hidden focus:ring-2 focus:ring-white",
                ),
                class_name="flex items-center gap-3",
            ),
            class_name="flex h-12 w-full items-center justify-between gap-4 px-4",
        ),
        class_name="w-full shrink-0 bg-[#0B1A14]",
    )


def context_bar() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.label(
                    "Municipality",
                    class_name="text-[11px] font-semibold uppercase tracking-widest text-[#6f6f6f]",
                ),
                rx.el.div(
                    rx.el.select(
                        rx.foreach(
                            WorkspaceState.municipalities, _municipality_option
                        ),
                        value=WorkspaceState.selected_municipality_id.to_string(),
                        on_change=WorkspaceState.set_municipality,
                        class_name="h-10 w-full appearance-none border-0 border-b border-[#8d8d8d] bg-[#f4f4f4] px-3 pr-9 text-[14px] font-semibold text-[#161616] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe]",
                    ),
                    rx.icon(
                        "chevron-down",
                        class_name="pointer-events-none absolute right-3 top-3 h-4 w-4 text-[#525252]",
                    ),
                    class_name="relative w-full min-w-[220px]",
                ),
                class_name="flex w-full max-w-sm flex-col gap-1",
            ),
            rx.el.div(
                rx.el.button(
                    rx.icon("refresh-cw", class_name="h-4 w-4"),
                    rx.el.span("Refresh"),
                    on_click=WorkspaceState.refresh_all,
                    class_name="flex h-10 items-center gap-2 rounded-[2px] border border-[#8d8d8d] bg-white px-4 text-[13px] font-semibold text-[#161616] transition-colors hover:bg-[#e8e8e8] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe] focus:ring-offset-2",
                ),
                class_name="flex items-end gap-2",
            ),
            class_name="flex w-full flex-wrap items-end justify-between gap-4",
        ),
        rx.el.nav(
            rx.foreach(TABS, _tab),
            class_name="flex w-full items-center gap-1 overflow-x-auto border-t border-[#e0e0e0]",
        ),
        class_name="flex w-full shrink-0 flex-col gap-4 border-b border-[#e0e0e0] bg-white px-4 pt-4",
    )


def messages() -> rx.Component:
    return rx.el.div(
        rx.cond(
            WorkspaceState.seeded_now,
            notification(
                "info",
                "A SIMULATED demonstration municipality was seeded on first load. Every record shown is synthetic demonstration data, not verified municipal fact.",
            ),
        ),
        rx.cond(
            WorkspaceState.status_message != "",
            notification("success", WorkspaceState.status_message),
        ),
        rx.cond(
            WorkspaceState.error_message != "",
            notification("error", WorkspaceState.error_message),
        ),
        rx.cond(
            AuthState.welcome_message != "",
            notification("info", AuthState.welcome_message),
        ),
        rx.cond(
            ~AuthState.is_privileged,
            notification(
                "info",
                "You are signed in as Viewer (read-only). Every dashboard, map, route and report is available to read. Acknowledging or resolving alerts, approving collection route plans and generating report exports require an Operator or Manager account.",
            ),
        ),
        class_name="flex w-full flex-col gap-2",
    )
