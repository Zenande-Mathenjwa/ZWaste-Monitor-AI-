import reflex as rx

from app.components.alerts_view import alerts_workspace
from app.components.monitoring import monitoring_workspace
from app.components.overview import overview_workspace
from app.components.reports_view import reports_workspace
from app.components.routes_view import routes_workspace
from app.components.shell import context_bar, header, messages
from app.pages.login import login_page
from app.states.auth_state import AuthState
from app.states.workspace_state import WorkspaceState


def _workspace_body() -> rx.Component:
    return rx.match(
        WorkspaceState.active_tab,
        ("Overview", overview_workspace()),
        ("Monitoring", monitoring_workspace()),
        ("Collection routes", routes_workspace()),
        ("Alerts", alerts_workspace()),
        ("Waste reports", reports_workspace()),
        overview_workspace(),
    )


def _page_title() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.h1(
                WorkspaceState.active_tab,
                class_name="font-['IBM_Plex_Sans_Condensed'] text-[28px] font-semibold leading-none tracking-tight text-[#161616]",
            ),
            rx.el.p(
                WorkspaceState.selected_municipality_name,
                class_name="mt-1 text-[13px] font-medium text-[#6f6f6f]",
            ),
            class_name="min-w-0",
        ),
        rx.el.span(
            "SIMULATED DEMONSTRATION DATA",
            class_name="w-fit rounded-[2px] border border-[#f1c21b] bg-[#fcf4d6] px-2 py-1 text-[11px] font-semibold uppercase tracking-widest text-[#684e00]",
        ),
        class_name="flex w-full flex-wrap items-center justify-between gap-3",
    )


def index() -> rx.Component:
    return rx.el.div(
        header(),
        context_bar(),
        rx.el.main(
            _page_title(),
            messages(),
            _workspace_body(),
            class_name="flex w-full min-w-0 flex-1 flex-col gap-4 overflow-y-auto bg-[#f4f4f4] p-4",
        ),
        class_name="flex h-dvh w-full flex-col overflow-hidden bg-[#f4f4f4] font-['IBM_Plex_Sans'] text-[#161616]",
    )


app = rx.App(
    theme=rx.theme(appearance="light"),
    head_components=[
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(
            rel="preconnect",
            href="https://fonts.gstatic.com",
            cross_origin="",
        ),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Sans+Condensed:wght@500;600;700&display=swap",
            rel="stylesheet",
        ),
    ],
)
app.add_page(index, route="/", on_load=AuthState.require_auth)
app.add_page(
    login_page,
    route="/login",
    title="Sign in · ZWaste Monitor AI",
    on_load=AuthState.redirect_if_authenticated,
)
