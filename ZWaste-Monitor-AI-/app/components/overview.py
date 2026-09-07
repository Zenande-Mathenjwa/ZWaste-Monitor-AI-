"""Overview workspace: metrics, fill distribution, priority bins, fleet."""

from __future__ import annotations

import reflex as rx

from app.components.ui import (
    dot,
    empty_state,
    meter,
    panel,
    panel_header,
    skeleton_rows,
    source_tag,
    status_pill,
    td,
    th,
)
from app.states.workspace_state import (
    AlertRow,
    BinRow,
    BucketRow,
    MetricRow,
    RouteRow,
    SensorRow,
    VehicleRow,
    WorkspaceState,
)


def _metric_card(metric: MetricRow) -> rx.Component:
    return rx.el.div(
        rx.el.p(
            metric["label"],
            class_name="text-[12px] font-semibold uppercase tracking-wide text-[#525252]",
        ),
        rx.el.p(
            metric["value"],
            class_name="mt-2 font-['IBM_Plex_Sans_Condensed'] text-[28px] font-semibold leading-none text-[#161616]",
        ),
        rx.el.p(
            metric["caption"],
            class_name="mt-2 text-[12px] font-medium text-[#6f6f6f]",
        ),
        style={"borderTopColor": metric["accent"]},
        class_name="w-full border border-[#e0e0e0] border-t-[3px] bg-white p-4 rounded-[2px]",
    )


def metric_grid() -> rx.Component:
    return rx.el.div(
        rx.foreach(WorkspaceState.metric_cards, _metric_card),
        class_name="grid w-full grid-cols-2 gap-4 lg:grid-cols-4",
    )


def _bucket_row(bucket: BucketRow) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                bucket["label"],
                class_name="w-[86px] shrink-0 text-[13px] font-semibold text-[#161616]",
            ),
            meter(bucket["share"], bucket["color"]),
            rx.el.span(
                f"{bucket['count']} bins",
                class_name="w-[72px] shrink-0 text-right text-[12px] font-medium text-[#6f6f6f]",
            ),
            class_name="flex w-full items-center gap-3",
        ),
        class_name="w-full",
    )


def _status_chip(bucket: BucketRow) -> rx.Component:
    return rx.el.div(
        dot(bucket["color"]),
        rx.el.span(
            bucket["label"],
            class_name="text-[12px] font-semibold uppercase tracking-wide text-[#161616]",
        ),
        rx.el.span(
            bucket["count"].to_string(),
            class_name="ml-auto text-[13px] font-semibold text-[#161616]",
        ),
        class_name="flex w-full items-center gap-2 border border-[#e0e0e0] bg-[#f4f4f4] px-3 py-2 rounded-[2px]",
    )


def flow_board() -> rx.Component:
    return panel(
        panel_header(
            "Waste-flow monitoring board",
            "Bin fill distribution and operational status across the municipality",
            "activity",
        ),
        rx.cond(
            WorkspaceState.fill_buckets.length() > 0,
            rx.el.div(
                rx.el.div(
                    rx.el.p(
                        "Fill distribution",
                        class_name="mb-3 text-[12px] font-semibold uppercase tracking-widest text-[#525252]",
                    ),
                    rx.el.div(
                        rx.foreach(WorkspaceState.fill_buckets, _bucket_row),
                        class_name="flex w-full flex-col gap-3",
                    ),
                    class_name="w-full min-w-0 flex-1",
                ),
                rx.el.div(
                    rx.el.p(
                        "Operational status",
                        class_name="mb-3 text-[12px] font-semibold uppercase tracking-widest text-[#525252]",
                    ),
                    rx.el.div(
                        rx.foreach(WorkspaceState.status_buckets, _status_chip),
                        class_name="flex w-full flex-col gap-2",
                    ),
                    class_name="w-full min-w-0 flex-1",
                ),
                class_name="flex w-full flex-col gap-8 p-4 lg:flex-row",
            ),
            empty_state(
                "No bins recorded for this municipality yet.", "trash-2"
            ),
        ),
        class_name="w-full",
    )


def _bin_row(row: BinRow) -> rx.Component:
    return rx.el.tr(
        td(rx.el.span(row["code"], class_name="font-semibold")),
        td(row["entity"]),
        td(row["area"]),
        td(row["waste_type"]),
        td(
            rx.el.div(
                meter(row["fill"], row["color"]),
                rx.el.span(
                    f"{row['fill']:.0f}%",
                    class_name="w-[46px] shrink-0 text-right text-[12px] font-semibold",
                ),
                class_name="flex items-center gap-2 min-w-[150px]",
            )
        ),
        td(status_pill(row["status"], row["color"])),
        td(row["last_reading"], class_name="text-[#6f6f6f]"),
        td(source_tag(row["source"])),
        class_name="hover:bg-[#f4f4f4]",
    )


def priority_bins_table() -> rx.Component:
    return panel(
        panel_header(
            "Priority bins",
            "Highest fill first · SIMULATED sensor-derived values",
            "triangle-alert",
        ),
        rx.cond(
            WorkspaceState.loading
            & (WorkspaceState.priority_bins.length() == 0),
            skeleton_rows(6),
            rx.cond(
                WorkspaceState.priority_bins.length() > 0,
                rx.el.div(
                    rx.el.table(
                        rx.el.thead(
                            rx.el.tr(
                                th("Bin", "trash-2"),
                                th("Entity", "building-2"),
                                th("Area", "map-pin"),
                                th("Waste type", "recycle"),
                                th("Fill", "gauge"),
                                th("Status", "circle-dot"),
                                th("Last reading", "clock"),
                                th("Source", "database"),
                            )
                        ),
                        rx.el.tbody(
                            rx.foreach(WorkspaceState.priority_bins, _bin_row)
                        ),
                        class_name="table-auto w-full border-collapse",
                    ),
                    class_name="w-full overflow-x-auto",
                ),
                empty_state("No bins to prioritise.", "trash-2"),
            ),
        ),
        class_name="w-full overflow-hidden",
    )


def _alert_item(alert: AlertRow) -> rx.Component:
    return rx.el.li(
        rx.el.div(
            dot(alert["color"]),
            rx.el.span(
                alert["severity"],
                class_name="text-[11px] font-semibold uppercase tracking-widest text-[#525252]",
            ),
            rx.el.span(
                alert["created_at"],
                class_name="ml-auto text-[11px] font-medium text-[#6f6f6f]",
            ),
            class_name="flex items-center gap-2",
        ),
        rx.el.p(
            alert["title"],
            class_name="mt-1 text-[13px] font-semibold text-[#161616]",
        ),
        rx.el.p(
            f"{alert['kind']} · bin {alert['bin_code']} · {alert['status']}",
            class_name="text-[12px] font-medium text-[#6f6f6f]",
        ),
        class_name="border-b border-[#f4f4f4] px-4 py-3",
    )


def alert_queue() -> rx.Component:
    return panel(
        panel_header("Open alert queue", "Ordered by severity", "bell-ring"),
        rx.cond(
            WorkspaceState.alerts.length() > 0,
            rx.el.ul(
                rx.foreach(WorkspaceState.alerts[:8], _alert_item),
                class_name="flex w-full flex-col",
            ),
            empty_state("No alerts match the current filters.", "bell-off"),
        ),
        class_name="w-full",
    )


def _sensor_item(sensor: SensorRow) -> rx.Component:
    return rx.el.li(
        rx.el.div(
            dot(sensor["color"]),
            rx.el.span(
                sensor["serial"],
                class_name="text-[13px] font-semibold text-[#161616]",
            ),
            rx.el.span(
                sensor["status"],
                class_name="ml-auto text-[11px] font-semibold uppercase tracking-widest text-[#525252]",
            ),
            class_name="flex items-center gap-2",
        ),
        rx.el.p(
            f"Bin {sensor['bin_code']} · battery {sensor['battery']:.0f}% · {sensor['signal']:.0f} dBm · seen {sensor['last_seen']}",
            class_name="mt-1 text-[12px] font-medium text-[#6f6f6f]",
        ),
        class_name="border-b border-[#f4f4f4] px-4 py-3",
    )


def sensor_health() -> rx.Component:
    return panel(
        panel_header(
            "Sensor health", "Faulty and low-battery devices first", "radio"
        ),
        rx.cond(
            WorkspaceState.sensors.length() > 0,
            rx.el.ul(
                rx.foreach(WorkspaceState.sensors, _sensor_item),
                class_name="flex flex-col",
            ),
            empty_state("No sensors registered.", "radio"),
        ),
        class_name="w-full",
    )


def _route_progress_item(route: RouteRow) -> rx.Component:
    return rx.el.li(
        rx.el.div(
            rx.el.span(
                route["name"],
                class_name="text-[13px] font-semibold text-[#161616]",
            ),
            rx.el.span(
                route["status"],
                class_name="ml-auto text-[11px] font-semibold uppercase tracking-widest text-[#525252]",
            ),
            class_name="flex items-center gap-2",
        ),
        rx.el.div(
            meter(route["progress"], "#0f62fe"),
            rx.el.span(
                f"{route['done']}/{route['stops']}",
                class_name="w-[54px] shrink-0 text-right text-[12px] font-semibold text-[#161616]",
            ),
            class_name="mt-2 flex items-center gap-2",
        ),
        rx.el.p(
            f"{route['vehicle']} · load {route['load_kg']:,.0f} kg of {route['capacity_kg']:,.0f} kg ({route['load_pct']:.0f}%)",
            class_name="mt-1 text-[12px] font-medium text-[#6f6f6f]",
        ),
        class_name="border-b border-[#f4f4f4] px-4 py-3",
    )


def route_progress() -> rx.Component:
    return panel(
        panel_header("Route progress", "Stops completed against plan", "route"),
        rx.cond(
            WorkspaceState.routes.length() > 0,
            rx.el.ul(
                rx.foreach(WorkspaceState.routes[:6], _route_progress_item),
                class_name="flex flex-col",
            ),
            empty_state("No routes recorded.", "route"),
        ),
        class_name="w-full",
    )


def _vehicle_item(vehicle: VehicleRow) -> rx.Component:
    return rx.el.li(
        dot(vehicle["color"]),
        rx.el.span(
            vehicle["plate"],
            class_name="text-[13px] font-semibold text-[#161616]",
        ),
        rx.el.span(
            vehicle["label"],
            class_name="text-[12px] font-medium text-[#6f6f6f]",
        ),
        rx.el.span(
            f"{vehicle['capacity_kg']:,.0f} kg",
            class_name="ml-auto text-[12px] font-semibold text-[#161616]",
        ),
        rx.el.span(
            vehicle["status"],
            class_name="text-[11px] font-semibold uppercase tracking-widest text-[#525252]",
        ),
        class_name="flex items-center gap-3 border-b border-[#f4f4f4] px-4 py-3",
    )


def vehicle_availability() -> rx.Component:
    return panel(
        panel_header(
            "Vehicle availability", "Fleet readiness by status", "truck"
        ),
        rx.cond(
            WorkspaceState.vehicles.length() > 0,
            rx.el.ul(
                rx.foreach(WorkspaceState.vehicles, _vehicle_item),
                class_name="flex flex-col",
            ),
            empty_state("No vehicles registered.", "truck"),
        ),
        class_name="w-full",
    )


def overview_workspace() -> rx.Component:
    return rx.el.div(
        metric_grid(),
        flow_board(),
        priority_bins_table(),
        rx.el.div(
            alert_queue(),
            sensor_health(),
            class_name="grid w-full grid-cols-1 gap-4 xl:grid-cols-2",
        ),
        rx.el.div(
            route_progress(),
            vehicle_availability(),
            class_name="grid w-full grid-cols-1 gap-4 xl:grid-cols-2",
        ),
        class_name="flex w-full flex-col gap-4",
    )
