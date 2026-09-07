"""Waste reports workspace: filters, preview totals and CSV generation."""

from __future__ import annotations

import reflex as rx

from app.components.ui import (
    empty_state,
    field_label,
    meter,
    notification,
    panel,
    panel_header,
    primary_button,
    select_box,
    skeleton_rows,
    td,
    th,
)
from app.states.auth_state import AuthState
from app.states.workspace_state import REPORT_KINDS, TotalRow, WorkspaceState


def report_filters() -> rx.Component:
    return panel(
        panel_header(
            "Report parameters",
            "Date range and report type",
            "sliders-horizontal",
        ),
        rx.el.div(
            select_box(
                REPORT_KINDS,
                WorkspaceState.report_kind,
                WorkspaceState.set_report_kind,
                "Report type",
            ),
            rx.el.div(
                field_label("Start date"),
                rx.el.input(
                    type="date",
                    default_value=WorkspaceState.report_start,
                    on_change=WorkspaceState.set_report_start,
                    class_name="h-10 w-full border-0 border-b border-[#8d8d8d] bg-[#f4f4f4] px-3 text-[14px] font-medium text-[#161616] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe]",
                ),
                class_name="w-full",
            ),
            rx.el.div(
                field_label("End date"),
                rx.el.input(
                    type="date",
                    default_value=WorkspaceState.report_end,
                    on_change=WorkspaceState.set_report_end,
                    class_name="h-10 w-full border-0 border-b border-[#8d8d8d] bg-[#f4f4f4] px-3 text-[14px] font-medium text-[#161616] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe]",
                ),
                class_name="w-full",
            ),
            rx.el.div(
                field_label("Generate"),
                rx.cond(
                    AuthState.is_privileged,
                    primary_button(
                        "Download CSV report",
                        WorkspaceState.generate_csv_report,
                        "download",
                    ),
                    rx.el.p(
                        "Read-only access: report generation requires the zwaste-super-admins group.",
                        class_name="text-[12px] font-medium text-[#da1e28]",
                    ),
                ),
                class_name="w-full",
            ),
            class_name="grid w-full grid-cols-1 gap-4 p-4 md:grid-cols-2 xl:grid-cols-4",
        ),
        rx.el.div(
            rx.cond(
                WorkspaceState.report_error != "",
                notification("error", WorkspaceState.report_error),
            ),
            rx.cond(
                WorkspaceState.report_notice != "",
                notification("success", WorkspaceState.report_notice),
            ),
            class_name="flex flex-col gap-2 px-4 pb-4",
        ),
        class_name="w-full",
    )


def _kpi(label: str, value: rx.Var | str, caption: str) -> rx.Component:
    return rx.el.div(
        rx.el.p(
            label,
            class_name="text-[12px] font-semibold uppercase tracking-wide text-[#525252]",
        ),
        rx.el.p(
            value,
            class_name="mt-2 font-['IBM_Plex_Sans_Condensed'] text-[24px] font-semibold leading-none text-[#161616]",
        ),
        rx.el.p(
            caption, class_name="mt-1 text-[12px] font-medium text-[#6f6f6f]"
        ),
        class_name="w-full border border-[#e0e0e0] bg-white p-4 rounded-[2px]",
    )


def kpi_grid() -> rx.Component:
    return rx.el.div(
        _kpi(
            "Total collected",
            f"{WorkspaceState.report_kpis['total_kg']:,.0f} kg",
            "Across the selected range",
        ),
        _kpi(
            "Recycling rate",
            f"{WorkspaceState.report_kpis['recycling_rate']:.1f}%",
            f"{WorkspaceState.report_kpis['recycled_kg']:,.0f} kg recycled",
        ),
        _kpi(
            "Landfilled",
            f"{WorkspaceState.report_kpis['landfill_kg']:,.0f} kg",
            "Residual waste",
        ),
        _kpi(
            "Collection records",
            f"{WorkspaceState.report_kpis['records']:,.0f}",
            f"{WorkspaceState.report_kpis['collections_per_day']:.2f} per day",
        ),
        _kpi(
            "Stops completed",
            f"{WorkspaceState.report_kpis['stops_completed']:,.0f}",
            "All recorded route stops",
        ),
        _kpi(
            "Alerts raised",
            f"{WorkspaceState.report_kpis['alerts_raised']:,.0f}",
            "Within the selected range",
        ),
        class_name="grid w-full grid-cols-2 gap-4 lg:grid-cols-3",
    )


def _total_row(row: TotalRow) -> rx.Component:
    return rx.el.tr(
        td(rx.el.span(row["label"], class_name="font-semibold")),
        td(f"{row['kg']:,.1f} kg"),
        td(
            rx.el.div(
                meter(row["share"], "#0f62fe"),
                rx.el.span(
                    f"{row['share']:.1f}%",
                    class_name="w-[54px] shrink-0 text-right text-[12px] font-semibold",
                ),
                class_name="flex min-w-[160px] items-center gap-2",
            )
        ),
        class_name="hover:bg-[#f4f4f4]",
    )


def _totals_panel(
    title: str, caption: str, icon: str, rows: rx.Var
) -> rx.Component:
    return panel(
        panel_header(title, caption, icon),
        rx.cond(
            WorkspaceState.report_loading,
            skeleton_rows(5),
            rx.cond(
                rows.length() > 0,
                rx.el.div(
                    rx.el.table(
                        rx.el.thead(
                            rx.el.tr(
                                th(title, icon),
                                th("Quantity", "weight"),
                                th("Share", "chart-pie"),
                            )
                        ),
                        rx.el.tbody(rx.foreach(rows, _total_row)),
                        class_name="table-auto w-full border-collapse",
                    ),
                    class_name="w-full overflow-x-auto",
                ),
                empty_state(
                    "No collection records in the selected range.", "file-x"
                ),
            ),
        ),
        class_name="w-full overflow-hidden",
    )


def reports_workspace() -> rx.Component:
    return rx.el.div(
        report_filters(),
        kpi_grid(),
        rx.el.div(
            _totals_panel(
                "By waste type",
                "SIMULATED collection totals",
                "recycle",
                WorkspaceState.report_by_type,
            ),
            _totals_panel(
                "By area",
                "SIMULATED collection totals",
                "map-pin",
                WorkspaceState.report_by_area,
            ),
            class_name="grid w-full grid-cols-1 gap-4 xl:grid-cols-2",
        ),
        rx.cond(
            WorkspaceState.last_report_name != "",
            notification(
                "info",
                f"Last generated file: {WorkspaceState.last_report_name} (contains SIMULATED demonstration data).",
            ),
        ),
        class_name="flex w-full flex-col gap-4",
    )
