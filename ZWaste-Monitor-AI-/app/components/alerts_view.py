"""Alerts workspace: search, filters and guarded acknowledge/resolve actions."""

from __future__ import annotations

import reflex as rx

from app.components.ui import (
    empty_state,
    field_label,
    panel,
    panel_header,
    select_box,
    skeleton_rows,
    source_tag,
    status_pill,
    td,
    th,
)
from app.states.auth_state import AuthState
from app.states.workspace_state import (
    ALERT_SOURCE_OPTIONS,
    ALERT_STATUS_OPTIONS,
    SEVERITY_OPTIONS,
    AlertRow,
    WorkspaceState,
)


def alert_filters() -> rx.Component:
    return panel(
        panel_header(
            "Alert filters", "Search and narrow the alert queue", "filter"
        ),
        rx.el.div(
            rx.el.div(
                field_label("Search"),
                rx.el.div(
                    rx.icon(
                        "search",
                        class_name="pointer-events-none absolute left-3 top-3 h-4 w-4 text-[#525252]",
                    ),
                    rx.el.input(
                        placeholder="Title, message or bin code",
                        default_value=WorkspaceState.alert_query,
                        on_change=WorkspaceState.set_alert_query.debounce(400),
                        class_name="h-10 w-full border-0 border-b border-[#8d8d8d] bg-[#f4f4f4] pl-9 pr-3 text-[14px] font-medium text-[#161616] placeholder:text-[#8d8d8d] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe]",
                    ),
                    class_name="relative w-full",
                ),
                class_name="w-full",
            ),
            select_box(
                SEVERITY_OPTIONS,
                WorkspaceState.alert_severity,
                WorkspaceState.set_alert_severity,
                "Severity",
            ),
            select_box(
                ALERT_STATUS_OPTIONS,
                WorkspaceState.alert_status,
                WorkspaceState.set_alert_status,
                "Status",
            ),
            select_box(
                ALERT_SOURCE_OPTIONS,
                WorkspaceState.alert_source,
                WorkspaceState.set_alert_source,
                "Source",
            ),
            class_name="grid w-full grid-cols-1 gap-4 p-4 md:grid-cols-2 xl:grid-cols-4",
        ),
        class_name="w-full",
    )


def _actions(alert: AlertRow) -> rx.Component:
    return rx.cond(
        AuthState.is_privileged,
        rx.el.div(
            rx.cond(
                alert["status"] == "OPEN",
                rx.el.button(
                    rx.icon("eye", class_name="h-3.5 w-3.5"),
                    rx.el.span("Acknowledge"),
                    on_click=lambda: WorkspaceState.acknowledge_alert(
                        alert["id"]
                    ),
                    class_name="flex h-8 items-center gap-1.5 rounded-[2px] border border-[#0f62fe] bg-white px-3 text-[12px] font-semibold text-[#0f62fe] transition-colors hover:bg-[#edf5ff] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe] focus:ring-offset-1",
                ),
            ),
            rx.cond(
                (alert["status"] == "OPEN")
                | (alert["status"] == "ACKNOWLEDGED"),
                rx.el.button(
                    rx.icon("circle-check", class_name="h-3.5 w-3.5"),
                    rx.el.span("Resolve"),
                    on_click=lambda: WorkspaceState.resolve_alert(alert["id"]),
                    class_name="flex h-8 items-center gap-1.5 rounded-[2px] bg-[#0f62fe] px-3 text-[12px] font-semibold text-white transition-colors hover:bg-[#0353e9] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe] focus:ring-offset-1",
                ),
                rx.el.span(
                    "Closed",
                    class_name="text-[12px] font-medium text-[#6f6f6f]",
                ),
            ),
            class_name="flex items-center gap-2",
        ),
        rx.el.span(
            "Read-only", class_name="text-[12px] font-medium text-[#6f6f6f]"
        ),
    )


def _alert_row(alert: AlertRow) -> rx.Component:
    return rx.el.tr(
        td(status_pill(alert["severity"], alert["color"])),
        td(
            rx.el.div(
                rx.el.span(alert["title"], class_name="font-semibold"),
                rx.el.span(
                    alert["message"],
                    class_name="block max-w-[420px] truncate text-[12px] font-medium text-[#6f6f6f]",
                ),
                class_name="flex flex-col",
            ),
            class_name="whitespace-normal",
        ),
        td(alert["kind"]),
        td(alert["bin_code"]),
        td(alert["status"]),
        td(source_tag(alert["source"])),
        td(f"{alert['priority']:.0f}"),
        td(alert["created_at"], class_name="text-[#6f6f6f]"),
        td(_actions(alert)),
        class_name="hover:bg-[#f4f4f4]",
    )


def alerts_table() -> rx.Component:
    return panel(
        panel_header(
            "Alert queue",
            "SIMULATED and derived alerts · acknowledge and resolve are audited",
            "bell-ring",
        ),
        rx.cond(
            WorkspaceState.loading & (WorkspaceState.alerts.length() == 0),
            skeleton_rows(6),
            rx.cond(
                WorkspaceState.alerts.length() > 0,
                rx.el.div(
                    rx.el.table(
                        rx.el.thead(
                            rx.el.tr(
                                th("Severity", "triangle-alert"),
                                th("Alert", "bell"),
                                th("Kind", "tag"),
                                th("Bin", "trash-2"),
                                th("Status", "circle-dot"),
                                th("Source", "database"),
                                th("Priority", "arrow-up-narrow-wide"),
                                th("Raised", "clock"),
                                th("Actions", "settings"),
                            )
                        ),
                        rx.el.tbody(
                            rx.foreach(WorkspaceState.alerts, _alert_row)
                        ),
                        class_name="table-auto w-full border-collapse",
                    ),
                    class_name="w-full overflow-x-auto",
                ),
                empty_state("No alerts match the current filters.", "bell-off"),
            ),
        ),
        class_name="w-full overflow-hidden",
    )


def alerts_workspace() -> rx.Component:
    return rx.el.div(
        alert_filters(),
        alerts_table(),
        class_name="flex w-full flex-col gap-4",
    )
