"""Collection routes workspace: routes, sequenced stops and route planning."""

from __future__ import annotations

import reflex as rx

from app.components.ui import (
    empty_state,
    field_label,
    ghost_button,
    meter,
    panel,
    panel_header,
    primary_button,
    skeleton_rows,
    source_tag,
    status_pill,
    td,
    th,
)
from app.states.auth_state import AuthState
from app.states.workspace_state import BinRow, RouteRow, StopRow, WorkspaceState


def _route_card(route: RouteRow) -> rx.Component:
    return rx.el.button(
        rx.el.div(
            rx.el.span(
                route["name"],
                class_name="text-[13px] font-semibold text-[#161616]",
            ),
            source_tag(route["source"]),
            class_name="flex w-full items-center justify-between gap-2",
        ),
        rx.el.div(
            status_pill(route["status"], "#0f62fe"),
            rx.el.span(
                f"{route['code']} · {route['scheduled_for']}",
                class_name="text-[12px] font-medium text-[#6f6f6f]",
            ),
            class_name="mt-2 flex w-full flex-wrap items-center gap-2",
        ),
        rx.el.div(
            meter(route["progress"], "#0f62fe"),
            rx.el.span(
                f"{route['done']}/{route['stops']} stops",
                class_name="w-[86px] shrink-0 text-right text-[12px] font-semibold text-[#161616]",
            ),
            class_name="mt-3 flex w-full items-center gap-2",
        ),
        rx.el.p(
            f"{route['vehicle']} · {route['load_kg']:,.0f} kg / {route['capacity_kg']:,.0f} kg capacity ({route['load_pct']:.0f}%)",
            class_name="mt-1 w-full text-left text-[12px] font-medium text-[#6f6f6f]",
        ),
        on_click=lambda: WorkspaceState.select_route(route["id"]),
        class_name=rx.cond(
            WorkspaceState.selected_route_id == route["id"],
            "w-full border border-[#0f62fe] bg-[#edf5ff] p-4 text-left rounded-[2px] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe]",
            "w-full border border-[#e0e0e0] bg-white p-4 text-left transition-colors hover:bg-[#f4f4f4] rounded-[2px] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe]",
        ),
    )


def routes_list() -> rx.Component:
    return panel(
        panel_header(
            "Routes", "Select a route to see its sequenced stops", "route"
        ),
        rx.cond(
            WorkspaceState.routes.length() > 0,
            rx.el.div(
                rx.foreach(WorkspaceState.routes, _route_card),
                class_name="flex flex-col gap-3 p-4",
            ),
            empty_state("No routes recorded for this municipality.", "route"),
        ),
        class_name="w-full",
    )


def _stop_row(stop: StopRow) -> rx.Component:
    return rx.el.tr(
        td(stop["sequence"].to_string(), class_name="w-12 font-semibold"),
        td(stop["bin_code"]),
        td(stop["area"]),
        td(status_pill(stop["status"], stop["color"])),
        td(f"{stop['collected_kg']:.1f} kg"),
        td(stop["eta"], class_name="text-[#6f6f6f]"),
        class_name="hover:bg-[#f4f4f4]",
    )


def stops_table() -> rx.Component:
    return panel(
        panel_header(
            "Sequenced stops",
            WorkspaceState.selected_route_name,
            "list-ordered",
        ),
        rx.cond(
            WorkspaceState.route_stops.length() > 0,
            rx.el.div(
                rx.el.table(
                    rx.el.thead(
                        rx.el.tr(
                            th("#", "hash"),
                            th("Bin", "trash-2"),
                            th("Area", "map-pin"),
                            th("Status", "circle-dot"),
                            th("Collected", "weight"),
                            th("ETA", "clock"),
                        )
                    ),
                    rx.el.tbody(
                        rx.foreach(WorkspaceState.route_stops, _stop_row)
                    ),
                    class_name="table-auto w-full border-collapse",
                ),
                class_name="w-full overflow-x-auto",
            ),
            empty_state("This route has no stops yet.", "list"),
        ),
        class_name="w-full overflow-hidden",
    )


def _selectable_bin(row: BinRow) -> rx.Component:
    return rx.el.tr(
        td(
            rx.el.input(
                type="checkbox",
                checked=WorkspaceState.selected_bin_ids.contains(row["id"]),
                on_change=lambda _v: WorkspaceState.toggle_bin_selection(
                    row["id"]
                ),
                class_name="h-4 w-4 accent-[#0f62fe] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe]",
            ),
            class_name="w-10",
        ),
        td(rx.el.span(row["code"], class_name="font-semibold")),
        td(row["area"]),
        td(
            rx.el.div(
                meter(row["fill"], row["color"]),
                rx.el.span(
                    f"{row['fill']:.0f}%",
                    class_name="w-[46px] shrink-0 text-right text-[12px] font-semibold",
                ),
                class_name="flex min-w-[150px] items-center gap-2",
            )
        ),
        td(status_pill(row["status"], row["color"])),
        td(source_tag(row["source"])),
        class_name="hover:bg-[#f4f4f4]",
    )


def planner() -> rx.Component:
    return panel(
        panel_header(
            "Human-approved route planning",
            "Selected bins become a DRAFT route for review",
            "clipboard-check",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    field_label("Route name"),
                    rx.el.input(
                        placeholder="e.g. Central overflow response",
                        default_value=WorkspaceState.plan_route_name,
                        on_change=WorkspaceState.set_plan_route_name.debounce(
                            400
                        ),
                        class_name="h-10 w-full border-0 border-b border-[#8d8d8d] bg-[#f4f4f4] px-3 text-[14px] font-medium text-[#161616] placeholder:text-[#8d8d8d] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe]",
                    ),
                    class_name="w-full",
                ),
                rx.el.div(
                    field_label("Vehicle"),
                    rx.el.div(
                        rx.el.select(
                            rx.foreach(
                                WorkspaceState.vehicles,
                                lambda v: rx.el.option(
                                    f"{v['plate']} · {v['status']}",
                                    value=v["id"].to_string(),
                                ),
                            ),
                            value=WorkspaceState.plan_vehicle_id.to_string(),
                            on_change=WorkspaceState.set_plan_vehicle,
                            class_name="h-10 w-full appearance-none border-0 border-b border-[#8d8d8d] bg-[#f4f4f4] px-3 pr-9 text-[14px] font-medium text-[#161616] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe]",
                        ),
                        rx.icon(
                            "chevron-down",
                            class_name="pointer-events-none absolute right-3 top-3 h-4 w-4 text-[#525252]",
                        ),
                        class_name="relative w-full",
                    ),
                    class_name="w-full",
                ),
                class_name="grid w-full grid-cols-1 gap-4 md:grid-cols-2",
            ),
            rx.el.div(
                rx.el.p(
                    f"{WorkspaceState.selected_bin_count} priority bins selected",
                    class_name="text-[13px] font-semibold text-[#161616]",
                ),
                rx.el.div(
                    rx.cond(
                        AuthState.is_privileged,
                        primary_button(
                            "Approve and create DRAFT route",
                            WorkspaceState.plan_route,
                            "check",
                        ),
                        rx.el.p(
                            "Read-only access: route approval requires the zwaste-super-admins group.",
                            class_name="text-[12px] font-medium text-[#da1e28]",
                        ),
                    ),
                    ghost_button(
                        "Clear selection",
                        WorkspaceState.clear_bin_selection,
                        "eraser",
                    ),
                    class_name="flex flex-wrap items-center gap-3",
                ),
                class_name="flex w-full flex-wrap items-center justify-between gap-4 border-t border-[#e0e0e0] pt-4",
            ),
            class_name="flex flex-col gap-4 p-4",
        ),
        rx.cond(
            WorkspaceState.loading
            & (WorkspaceState.priority_bins.length() == 0),
            skeleton_rows(5),
            rx.cond(
                WorkspaceState.priority_bins.length() > 0,
                rx.el.div(
                    rx.el.table(
                        rx.el.thead(
                            rx.el.tr(
                                th(""),
                                th("Bin", "trash-2"),
                                th("Area", "map-pin"),
                                th("Fill", "gauge"),
                                th("Status", "circle-dot"),
                                th("Source", "database"),
                            )
                        ),
                        rx.el.tbody(
                            rx.foreach(
                                WorkspaceState.priority_bins, _selectable_bin
                            )
                        ),
                        class_name="table-auto w-full border-collapse",
                    ),
                    class_name="w-full overflow-x-auto border-t border-[#e0e0e0]",
                ),
                empty_state("No priority bins available to plan.", "trash-2"),
            ),
        ),
        class_name="w-full overflow-hidden",
    )


def routes_workspace() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            routes_list(),
            stops_table(),
            class_name="grid w-full grid-cols-1 gap-4 xl:grid-cols-2",
        ),
        planner(),
        class_name="flex w-full flex-col gap-4",
    )
