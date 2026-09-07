"""Monitoring workspace: schematic geographic operations board.

The board is drawn from coordinates stored on bins and vehicles. No external
map service is used and no positions are invented.
"""

from __future__ import annotations

import reflex as rx

from app.components.ui import (
    dot,
    empty_state,
    ghost_button,
    meter,
    panel,
    panel_header,
    select_box,
    source_tag,
    status_pill,
)
from app.states.workspace_state import Marker, WorkspaceState

_LEGEND = [
    ("OK", "#24a148"),
    ("FILLING", "#42be65"),
    ("NEAR_FULL", "#f1c21b"),
    ("FULL", "#ff832b"),
    ("OVERFLOW", "#da1e28"),
    ("Vehicle on route", "#0f62fe"),
    ("Offline / out of service", "#8d8d8d"),
]


def _legend_item(label: str, color: str) -> rx.Component:
    return rx.el.li(
        dot(color),
        rx.el.span(label, class_name="text-[12px] font-medium text-[#161616]"),
        class_name="flex items-center gap-2",
    )


def _marker(marker: Marker) -> rx.Component:
    return rx.el.button(
        rx.cond(
            marker["kind"] == "VEHICLE",
            rx.icon("truck", class_name="h-3 w-3 text-white"),
            rx.el.span(class_name="h-1.5 w-1.5 rounded-[1px] bg-white"),
        ),
        on_click=lambda: WorkspaceState.select_marker(marker["key"]),
        aria_label=f"{marker['kind']} {marker['code']} status {marker['status']}",
        title=f"{marker['code']} · {marker['status']} · {marker['detail']}",
        style={
            "left": marker["left"],
            "top": marker["top"],
            "backgroundColor": marker["color"],
        },
        class_name=rx.cond(
            WorkspaceState.selected_marker["key"] == marker["key"],
            "absolute flex h-6 w-6 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-[2px] ring-2 ring-[#161616] ring-offset-1 focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe]",
            "absolute flex h-5 w-5 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-[2px] transition-transform hover:scale-125 focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe]",
        ),
    )


def board() -> rx.Component:
    return panel(
        panel_header(
            "Geographic operations board",
            "Schematic layout from stored latitude/longitude · SIMULATED positions",
            "map",
        ),
        rx.cond(
            WorkspaceState.visible_markers.length() > 0,
            rx.el.div(
                rx.el.div(
                    rx.foreach(WorkspaceState.visible_markers, _marker),
                    style={
                        "backgroundImage": "linear-gradient(to right, #e0e0e0 1px, transparent 1px), linear-gradient(to bottom, #e0e0e0 1px, transparent 1px)",
                        "backgroundSize": "32px 32px",
                    },
                    class_name="relative h-[420px] w-full min-w-[280px] border border-[#e0e0e0] bg-[#f4f4f4] rounded-[2px]",
                ),
                rx.el.p(
                    "North is up. Positions are normalised to the extent of the municipality's stored coordinates.",
                    class_name="mt-2 text-[12px] font-medium text-[#6f6f6f]",
                ),
                class_name="p-4",
            ),
            empty_state(
                "No bins or vehicles with stored coordinates match the current filters.",
                "map-pinned",
            ),
        ),
        class_name="w-full shrink-0",
    )


def filters() -> rx.Component:
    return panel(
        panel_header("Filters", "Narrow the board", "sliders-horizontal"),
        rx.el.div(
            rx.el.div(
                rx.el.label(
                    rx.el.input(
                        type="checkbox",
                        checked=WorkspaceState.show_bins,
                        on_change=lambda _v: WorkspaceState.toggle_bins(),
                        class_name="h-4 w-4 accent-[#0f62fe] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe]",
                    ),
                    rx.el.span(
                        "Bins",
                        class_name="text-[13px] font-medium text-[#161616]",
                    ),
                    class_name="flex items-center gap-2",
                ),
                rx.el.label(
                    rx.el.input(
                        type="checkbox",
                        checked=WorkspaceState.show_vehicles,
                        on_change=lambda _v: WorkspaceState.toggle_vehicles(),
                        class_name="h-4 w-4 accent-[#0f62fe] focus:outline-hidden focus:ring-2 focus:ring-[#0f62fe]",
                    ),
                    rx.el.span(
                        "Vehicles",
                        class_name="text-[13px] font-medium text-[#161616]",
                    ),
                    class_name="flex items-center gap-2",
                ),
                class_name="flex items-center gap-6",
            ),
            select_box(
                WorkspaceState.marker_status_options,
                WorkspaceState.monitor_status,
                WorkspaceState.set_monitor_status,
                "Status",
            ),
            select_box(
                WorkspaceState.area_options,
                WorkspaceState.monitor_area,
                WorkspaceState.set_monitor_area,
                "Area",
            ),
            rx.el.p(
                f"{WorkspaceState.visible_markers.length()} of {WorkspaceState.markers.length()} locations shown",
                class_name="text-[12px] font-medium text-[#6f6f6f]",
            ),
            class_name="flex flex-col gap-4 p-4",
        ),
        class_name="w-full",
    )


def legend() -> rx.Component:
    return panel(
        panel_header("Legend", "", "list"),
        rx.el.ul(
            *[_legend_item(label, color) for label, color in _LEGEND],
            class_name="flex flex-col gap-2 p-4",
        ),
        class_name="w-full",
    )


def detail_panel() -> rx.Component:
    return panel(
        panel_header(
            "Selected location",
            "Details of the highlighted marker",
            "crosshair",
        ),
        rx.cond(
            WorkspaceState.selected_marker["key"] != "",
            rx.el.div(
                rx.el.div(
                    rx.el.h3(
                        WorkspaceState.selected_marker["code"],
                        class_name="font-['IBM_Plex_Sans_Condensed'] text-[20px] font-semibold text-[#161616]",
                    ),
                    source_tag(WorkspaceState.selected_marker["source"]),
                    class_name="flex items-center justify-between gap-2",
                ),
                rx.el.p(
                    WorkspaceState.selected_marker["label"],
                    class_name="text-[13px] font-medium text-[#525252]",
                ),
                status_pill(
                    WorkspaceState.selected_marker["status"],
                    WorkspaceState.selected_marker["color"],
                ),
                rx.cond(
                    WorkspaceState.selected_marker["kind"] == "BIN",
                    rx.el.div(
                        rx.el.p(
                            f"Fill level {WorkspaceState.selected_marker['fill']:.0f}%",
                            class_name="text-[12px] font-semibold uppercase tracking-wide text-[#525252]",
                        ),
                        meter(
                            WorkspaceState.selected_marker["fill"],
                            WorkspaceState.selected_marker["color"],
                        ),
                        class_name="flex flex-col gap-2",
                    ),
                ),
                rx.el.dl(
                    rx.el.div(
                        rx.el.dt(
                            "Kind",
                            class_name="text-[11px] font-semibold uppercase tracking-widest text-[#6f6f6f]",
                        ),
                        rx.el.dd(
                            WorkspaceState.selected_marker["kind"],
                            class_name="text-[13px] font-medium text-[#161616]",
                        ),
                    ),
                    rx.el.div(
                        rx.el.dt(
                            "Area",
                            class_name="text-[11px] font-semibold uppercase tracking-widest text-[#6f6f6f]",
                        ),
                        rx.el.dd(
                            WorkspaceState.selected_marker["area"],
                            class_name="text-[13px] font-medium text-[#161616]",
                        ),
                    ),
                    rx.el.div(
                        rx.el.dt(
                            "Context",
                            class_name="text-[11px] font-semibold uppercase tracking-widest text-[#6f6f6f]",
                        ),
                        rx.el.dd(
                            WorkspaceState.selected_marker["detail"],
                            class_name="text-[13px] font-medium text-[#161616]",
                        ),
                    ),
                    class_name="flex flex-col gap-3",
                ),
                ghost_button(
                    "Clear selection", WorkspaceState.clear_marker, "x"
                ),
                class_name="flex flex-col gap-4 p-4",
            ),
            empty_state(
                "Select a marker on the board to inspect it.",
                "mouse-pointer-click",
            ),
        ),
        class_name="w-full",
    )


def monitoring_workspace() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            board(),
            rx.el.div(
                filters(),
                legend(),
                class_name="flex w-full flex-col gap-4 xl:w-[300px] xl:shrink-0",
            ),
            class_name="flex w-full flex-col gap-4 xl:flex-row",
        ),
        detail_panel(),
        class_name="flex w-full flex-col gap-4",
    )
