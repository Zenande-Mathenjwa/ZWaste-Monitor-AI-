"""Municipality operations workspace state.

Every query and mutation is scoped to the selected municipality and uses
parameterized SQLAlchemy `text()` statements through `rx.asession()`.
"""

from __future__ import annotations

import csv
import datetime
import io
from typing import TypedDict

import reflex as rx
from sqlalchemy import text

from app.states.auth_state import AuthState, SessionUser
from app.states.seed import seed_demo_data

_DENIED = (
    "Your Viewer account has read-only access. Acknowledging or resolving "
    "alerts, approving route plans and generating report exports require an "
    "Operator or Manager account."
)

TABS = [
    "Overview",
    "Monitoring",
    "Collection routes",
    "Alerts",
    "Waste reports",
]

SEVERITY_OPTIONS = ["All", "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
ALERT_STATUS_OPTIONS = ["All", "OPEN", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"]
ALERT_SOURCE_OPTIONS = [
    "All",
    "DERIVED",
    "SENSOR",
    "GATEZ_DEVICE",
    "SIMULATED",
    "MANUAL",
    "API",
]
REPORT_KINDS = [
    "DAILY",
    "WEEKLY",
    "MONTHLY",
    "WASTE_TYPE",
    "AREA",
    "PERFORMANCE",
]

_STATUS_COLORS = {
    "OK": "#24a148",
    "FILLING": "#42be65",
    "NEAR_FULL": "#f1c21b",
    "FULL": "#ff832b",
    "OVERFLOW": "#da1e28",
    "OFFLINE": "#8d8d8d",
    "MAINTENANCE": "#0f62fe",
}
_VEHICLE_COLORS = {
    "AVAILABLE": "#24a148",
    "ON_ROUTE": "#0f62fe",
    "MAINTENANCE": "#f1c21b",
    "OUT_OF_SERVICE": "#da1e28",
}


class MuniOption(TypedDict):
    id: int
    name: str
    code: str
    region: str
    source: str


class MetricRow(TypedDict):
    label: str
    value: str
    caption: str
    accent: str


class BucketRow(TypedDict):
    label: str
    count: int
    share: float
    color: str


class BinRow(TypedDict):
    id: int
    code: str
    label: str
    entity: str
    area: str
    waste_type: str
    fill: float
    status: str
    color: str
    capacity: float
    last_reading: str
    source: str


class AlertRow(TypedDict):
    id: int
    title: str
    message: str
    kind: str
    severity: str
    status: str
    source: str
    bin_code: str
    priority: float
    created_at: str
    color: str


class SensorRow(TypedDict):
    id: int
    serial: str
    status: str
    battery: float
    signal: float
    bin_code: str
    last_seen: str
    color: str
    source: str


class RouteRow(TypedDict):
    id: int
    name: str
    code: str
    status: str
    scheduled_for: str
    vehicle: str
    stops: int
    done: int
    progress: float
    capacity_kg: float
    load_kg: float
    load_pct: float
    source: str


class StopRow(TypedDict):
    id: int
    sequence: int
    bin_code: str
    area: str
    status: str
    collected_kg: float
    eta: str
    color: str


class VehicleRow(TypedDict):
    id: int
    plate: str
    label: str
    status: str
    capacity_kg: float
    color: str
    source: str


class Marker(TypedDict):
    key: str
    kind: str
    code: str
    label: str
    status: str
    area: str
    fill: float
    detail: str
    color: str
    left: str
    top: str
    source: str


class TotalRow(TypedDict):
    label: str
    kg: float
    share: float


_EMPTY_MARKER: Marker = {
    "key": "",
    "kind": "",
    "code": "",
    "label": "",
    "status": "",
    "area": "",
    "fill": 0.0,
    "detail": "",
    "color": "#8d8d8d",
    "left": "0%",
    "top": "0%",
    "source": "",
}


def _fmt_dt(value) -> str:
    if not value:
        return "—"
    return value.strftime("%d %b %H:%M")


def _pct(part: float, whole: float) -> float:
    return round(part / whole * 100.0, 1) if whole else 0.0


class WorkspaceState(rx.State):
    # ---------------- shell -------------------------------------------------
    active_tab: str = "Overview"
    municipalities: list[MuniOption] = []
    selected_municipality_id: int = 0
    loading: bool = False
    seeded_now: bool = False
    error_message: str = ""
    status_message: str = ""

    # ---------------- overview ---------------------------------------------
    metrics: dict[str, float] = {
        "bins": 0.0,
        "avg_fill": 0.0,
        "critical_bins": 0.0,
        "open_alerts": 0.0,
        "critical_alerts": 0.0,
        "sensors_total": 0.0,
        "sensors_healthy": 0.0,
        "routes_active": 0.0,
        "routes_total": 0.0,
        "vehicles_total": 0.0,
        "vehicles_available": 0.0,
        "waste_kg_30d": 0.0,
        "recycled_kg_30d": 0.0,
        "entities": 0.0,
        "waste_types": 0.0,
    }
    fill_buckets: list[BucketRow] = []
    status_buckets: list[BucketRow] = []
    priority_bins: list[BinRow] = []
    sensors: list[SensorRow] = []
    routes: list[RouteRow] = []
    vehicles: list[VehicleRow] = []

    # ---------------- monitoring -------------------------------------------
    markers: list[Marker] = []
    show_bins: bool = True
    show_vehicles: bool = True
    monitor_status: str = "All"
    monitor_area: str = "All"
    area_options: list[str] = ["All"]
    selected_marker: Marker = _EMPTY_MARKER

    # ---------------- routes -----------------------------------------------
    selected_route_id: int = 0
    route_stops: list[StopRow] = []
    selected_bin_ids: list[int] = []
    plan_route_name: str = ""
    plan_vehicle_id: int = 0
    planning: bool = False

    # ---------------- alerts -----------------------------------------------
    alerts: list[AlertRow] = []
    alert_query: str = ""
    alert_severity: str = "All"
    alert_status: str = "OPEN"
    alert_source: str = "All"

    # ---------------- reports ----------------------------------------------
    report_kind: str = "MONTHLY"
    report_start: str = ""
    report_end: str = ""
    report_by_type: list[TotalRow] = []
    report_by_area: list[TotalRow] = []
    report_kpis: dict[str, float] = {
        "total_kg": 0.0,
        "recycled_kg": 0.0,
        "landfill_kg": 0.0,
        "records": 0.0,
        "recycling_rate": 0.0,
        "collections_per_day": 0.0,
        "stops_completed": 0.0,
        "alerts_raised": 0.0,
    }
    report_loading: bool = False
    report_error: str = ""
    report_notice: str = ""
    last_report_name: str = ""

    # ---------------- computed ---------------------------------------------
    @rx.var
    def selected_municipality_name(self) -> str:
        for option in self.municipalities:
            if option["id"] == self.selected_municipality_id:
                return option["name"]
        return "No municipality"

    @rx.var
    def metric_cards(self) -> list[MetricRow]:
        m = self.metrics
        return [
            {
                "label": "Average bin fill",
                "value": f"{m['avg_fill']:.1f}%",
                "caption": f"{int(m['critical_bins'])} critical of {int(m['bins'])} bins",
                "accent": "#0f62fe",
            },
            {
                "label": "Critical bins",
                "value": f"{int(m['critical_bins'])}",
                "caption": "At or above full threshold",
                "accent": "#da1e28",
            },
            {
                "label": "Open alerts",
                "value": f"{int(m['open_alerts'])}",
                "caption": f"{int(m['critical_alerts'])} critical severity",
                "accent": "#ff832b",
            },
            {
                "label": "Sensor health",
                "value": f"{_pct(m['sensors_healthy'], m['sensors_total']):.0f}%",
                "caption": f"{int(m['sensors_healthy'])} of {int(m['sensors_total'])} reporting",
                "accent": "#24a148",
            },
            {
                "label": "Active routes",
                "value": f"{int(m['routes_active'])}",
                "caption": f"{int(m['routes_total'])} routes on record",
                "accent": "#0f62fe",
            },
            {
                "label": "Fleet available",
                "value": f"{int(m['vehicles_available'])}/{int(m['vehicles_total'])}",
                "caption": "Vehicles ready to dispatch",
                "accent": "#24a148",
            },
            {
                "label": "Waste collected (30d)",
                "value": f"{m['waste_kg_30d']:,.0f} kg",
                "caption": f"{_pct(m['recycled_kg_30d'], m['waste_kg_30d']):.0f}% recycled",
                "accent": "#8a3ffc",
            },
            {
                "label": "Monitored entities",
                "value": f"{int(m['entities'])}",
                "caption": f"{int(m['waste_types'])} configured waste types",
                "accent": "#525252",
            },
        ]

    @rx.var
    def visible_markers(self) -> list[Marker]:
        result: list[Marker] = []
        for marker in self.markers:
            if marker["kind"] == "BIN" and not self.show_bins:
                continue
            if marker["kind"] == "VEHICLE" and not self.show_vehicles:
                continue
            if (
                self.monitor_status != "All"
                and marker["status"] != self.monitor_status
            ):
                continue
            if (
                self.monitor_area != "All"
                and marker["area"] != self.monitor_area
            ):
                continue
            result.append(marker)
        return result

    @rx.var
    def marker_status_options(self) -> list[str]:
        return ["All"] + sorted({marker["status"] for marker in self.markers})

    @rx.var
    def selected_route_name(self) -> str:
        for route in self.routes:
            if route["id"] == self.selected_route_id:
                return route["name"]
        return ""

    @rx.var
    def selected_bin_count(self) -> int:
        return len(self.selected_bin_ids)

    # ---------------- loaders ---------------------------------------------
    @rx.event(background=True)
    async def load_workspace(self):
        async with self:
            self.loading = True
            self.error_message = ""
        async with rx.asession() as asession:
            created = await seed_demo_data(asession)
            rows = (
                await asession.execute(
                    text(
                        """
                        SELECT id, name, code, COALESCE(region, ''), source
                        FROM municipality
                        WHERE is_active = TRUE
                        ORDER BY name
                        """
                    )
                )
            ).all()
        async with self:
            self.seeded_now = created
            self.municipalities = [
                {
                    "id": int(r[0]),
                    "name": str(r[1]),
                    "code": str(r[2]),
                    "region": str(r[3]),
                    "source": str(r[4]),
                }
                for r in rows
            ]
            if self.municipalities and self.selected_municipality_id == 0:
                self.selected_municipality_id = self.municipalities[0]["id"]
            if not self.report_start:
                today = datetime.date.today()
                self.report_start = (
                    today - datetime.timedelta(days=29)
                ).isoformat()
                self.report_end = today.isoformat()
            self.loading = False
        yield WorkspaceState.refresh_all

    @rx.event
    def set_active_tab(self, tab: str):
        self.active_tab = tab

    @rx.event
    def set_municipality(self, value: str):
        self.selected_municipality_id = int(value) if value else 0
        self.selected_route_id = 0
        self.selected_bin_ids = []
        self.selected_marker = _EMPTY_MARKER
        return WorkspaceState.refresh_all

    @rx.event
    def refresh_all(self):
        return [
            WorkspaceState.load_overview,
            WorkspaceState.load_monitoring,
            WorkspaceState.load_routes,
            WorkspaceState.load_alerts,
            WorkspaceState.load_report_preview,
        ]

    @rx.event(background=True)
    async def load_overview(self):
        async with self:
            muni = self.selected_municipality_id
            self.loading = True
        if not muni:
            async with self:
                self.loading = False
            return
        async with rx.asession() as asession:
            kpi = (
                await asession.execute(
                    text(
                        """
                        SELECT
                          (SELECT COUNT(*) FROM bin WHERE municipality_id = :m AND is_active = TRUE),
                          (SELECT COALESCE(AVG(fill_percent), 0) FROM bin WHERE municipality_id = :m AND is_active = TRUE),
                          (SELECT COUNT(*) FROM bin WHERE municipality_id = :m AND is_active = TRUE
                             AND (fill_percent >= full_threshold_percent OR status IN ('FULL','OVERFLOW'))),
                          (SELECT COUNT(*) FROM alert WHERE municipality_id = :m AND status IN ('OPEN','ACKNOWLEDGED')),
                          (SELECT COUNT(*) FROM alert WHERE municipality_id = :m AND status IN ('OPEN','ACKNOWLEDGED') AND severity = 'CRITICAL'),
                          (SELECT COUNT(*) FROM sensor WHERE municipality_id = :m AND is_active = TRUE),
                          (SELECT COUNT(*) FROM sensor WHERE municipality_id = :m AND is_active = TRUE AND status = 'ACTIVE'),
                          (SELECT COUNT(*) FROM route WHERE municipality_id = :m AND is_active = TRUE AND status IN ('PLANNED','IN_PROGRESS')),
                          (SELECT COUNT(*) FROM route WHERE municipality_id = :m AND is_active = TRUE),
                          (SELECT COUNT(*) FROM vehicle WHERE municipality_id = :m AND is_active = TRUE),
                          (SELECT COUNT(*) FROM vehicle WHERE municipality_id = :m AND is_active = TRUE AND status = 'AVAILABLE'),
                          (SELECT COALESCE(SUM(quantity_kg), 0) FROM waste_record
                             WHERE municipality_id = :m AND is_active = TRUE AND collected_at >= :since),
                          (SELECT COALESCE(SUM(recycled_kg), 0) FROM waste_record
                             WHERE municipality_id = :m AND is_active = TRUE AND collected_at >= :since),
                          (SELECT COUNT(*) FROM entity WHERE municipality_id = :m AND is_active = TRUE),
                          (SELECT COUNT(*) FROM waste_type WHERE municipality_id = :m AND is_active = TRUE)
                        """
                    ),
                    {
                        "m": muni,
                        "since": datetime.datetime.now(datetime.timezone.utc)
                        - datetime.timedelta(days=30),
                    },
                )
            ).first()

            buckets = (
                await asession.execute(
                    text(
                        """
                        SELECT bucket, COUNT(*) FROM (
                          SELECT CASE
                            WHEN fill_percent < 25 THEN '0-24%'
                            WHEN fill_percent < 50 THEN '25-49%'
                            WHEN fill_percent < 75 THEN '50-74%'
                            WHEN fill_percent < 90 THEN '75-89%'
                            ELSE '90-100%' END AS bucket
                          FROM bin WHERE municipality_id = :m AND is_active = TRUE
                        ) b GROUP BY bucket ORDER BY bucket
                        """
                    ),
                    {"m": muni},
                )
            ).all()

            statuses = (
                await asession.execute(
                    text(
                        """
                        SELECT status, COUNT(*) FROM bin
                        WHERE municipality_id = :m AND is_active = TRUE
                        GROUP BY status ORDER BY COUNT(*) DESC
                        """
                    ),
                    {"m": muni},
                )
            ).all()

            bins = (
                await asession.execute(
                    text(
                        """
                        SELECT b.id, b.code, COALESCE(b.label, ''), COALESCE(e.name, 'Unassigned'),
                               COALESCE(b.area_name, '—'), COALESCE(w.name, '—'),
                               COALESCE(b.fill_percent, 0), b.status, COALESCE(b.capacity_liters, 0),
                               b.last_reading_at, b.source
                        FROM bin b
                        LEFT JOIN entity e ON e.id = b.entity_id
                        LEFT JOIN waste_type w ON w.id = b.waste_type_id
                        WHERE b.municipality_id = :m AND b.is_active = TRUE
                        ORDER BY b.fill_percent DESC
                        LIMIT 12
                        """
                    ),
                    {"m": muni},
                )
            ).all()

            sensor_rows = (
                await asession.execute(
                    text(
                        """
                        SELECT s.id, s.device_serial, s.status, COALESCE(s.battery_percent, 0),
                               COALESCE(s.signal_strength_dbm, 0), COALESCE(b.code, '—'),
                               s.last_seen_at, s.source
                        FROM sensor s
                        LEFT JOIN bin b ON b.id = s.bin_id
                        WHERE s.municipality_id = :m AND s.is_active = TRUE
                        ORDER BY CASE s.status WHEN 'FAULTY' THEN 0 WHEN 'LOW_BATTERY' THEN 1
                                 WHEN 'INACTIVE' THEN 2 ELSE 3 END, s.battery_percent
                        LIMIT 14
                        """
                    ),
                    {"m": muni},
                )
            ).all()

            vehicle_rows = (
                await asession.execute(
                    text(
                        """
                        SELECT id, plate_number, COALESCE(label, ''), status,
                               COALESCE(capacity_kg, 0), source
                        FROM vehicle
                        WHERE municipality_id = :m AND is_active = TRUE
                        ORDER BY status, plate_number
                        """
                    ),
                    {"m": muni},
                )
            ).all()

        total_bins = int(kpi[0]) if kpi else 0
        async with self:
            if kpi:
                self.metrics = {
                    "bins": float(kpi[0]),
                    "avg_fill": float(kpi[1]),
                    "critical_bins": float(kpi[2]),
                    "open_alerts": float(kpi[3]),
                    "critical_alerts": float(kpi[4]),
                    "sensors_total": float(kpi[5]),
                    "sensors_healthy": float(kpi[6]),
                    "routes_active": float(kpi[7]),
                    "routes_total": float(kpi[8]),
                    "vehicles_total": float(kpi[9]),
                    "vehicles_available": float(kpi[10]),
                    "waste_kg_30d": float(kpi[11]),
                    "recycled_kg_30d": float(kpi[12]),
                    "entities": float(kpi[13]),
                    "waste_types": float(kpi[14]),
                }
            self.fill_buckets = [
                {
                    "label": str(r[0]),
                    "count": int(r[1]),
                    "share": _pct(float(r[1]), float(total_bins)),
                    "color": [
                        "#24a148",
                        "#42be65",
                        "#f1c21b",
                        "#ff832b",
                        "#da1e28",
                    ][idx]
                    if idx < 5
                    else "#0f62fe",
                }
                for idx, r in enumerate(buckets)
            ]
            self.status_buckets = [
                {
                    "label": str(r[0]),
                    "count": int(r[1]),
                    "share": _pct(float(r[1]), float(total_bins)),
                    "color": _STATUS_COLORS.get(str(r[0]), "#525252"),
                }
                for r in statuses
            ]
            self.priority_bins = [
                {
                    "id": int(r[0]),
                    "code": str(r[1]),
                    "label": str(r[2]),
                    "entity": str(r[3]),
                    "area": str(r[4]),
                    "waste_type": str(r[5]),
                    "fill": float(r[6]),
                    "status": str(r[7]),
                    "color": _STATUS_COLORS.get(str(r[7]), "#525252"),
                    "capacity": float(r[8]),
                    "last_reading": _fmt_dt(r[9]),
                    "source": str(r[10]),
                }
                for r in bins
            ]
            self.sensors = [
                {
                    "id": int(r[0]),
                    "serial": str(r[1]),
                    "status": str(r[2]),
                    "battery": float(r[3]),
                    "signal": float(r[4]),
                    "bin_code": str(r[5]),
                    "last_seen": _fmt_dt(r[6]),
                    "color": "#24a148"
                    if str(r[2]) == "ACTIVE"
                    else (
                        "#f1c21b"
                        if str(r[2]) in ("LOW_BATTERY", "CALIBRATING")
                        else "#da1e28"
                    ),
                    "source": str(r[7]),
                }
                for r in sensor_rows
            ]
            self.vehicles = [
                {
                    "id": int(r[0]),
                    "plate": str(r[1]),
                    "label": str(r[2]),
                    "status": str(r[3]),
                    "capacity_kg": float(r[4]),
                    "color": _VEHICLE_COLORS.get(str(r[3]), "#525252"),
                    "source": str(r[5]),
                }
                for r in vehicle_rows
            ]
            if self.plan_vehicle_id == 0 and self.vehicles:
                self.plan_vehicle_id = self.vehicles[0]["id"]
            self.loading = False

    @rx.event(background=True)
    async def load_monitoring(self):
        async with self:
            muni = self.selected_municipality_id
        if not muni:
            return
        async with rx.asession() as asession:
            bin_rows = (
                await asession.execute(
                    text(
                        """
                        SELECT b.id, b.code, COALESCE(b.label, ''), b.status,
                               COALESCE(b.area_name, 'Unzoned'), COALESCE(b.fill_percent, 0),
                               b.latitude, b.longitude, COALESCE(e.name, 'Unassigned'),
                               COALESCE(w.name, '—'), b.source
                        FROM bin b
                        LEFT JOIN entity e ON e.id = b.entity_id
                        LEFT JOIN waste_type w ON w.id = b.waste_type_id
                        WHERE b.municipality_id = :m AND b.is_active = TRUE
                          AND b.latitude IS NOT NULL AND b.longitude IS NOT NULL
                        LIMIT 300
                        """
                    ),
                    {"m": muni},
                )
            ).all()
            vehicle_rows = (
                await asession.execute(
                    text(
                        """
                        SELECT id, plate_number, COALESCE(label, ''), status,
                               last_latitude, last_longitude, last_position_at, source
                        FROM vehicle
                        WHERE municipality_id = :m AND is_active = TRUE
                          AND last_latitude IS NOT NULL AND last_longitude IS NOT NULL
                        LIMIT 100
                        """
                    ),
                    {"m": muni},
                )
            ).all()

        points = [(float(r[6]), float(r[7])) for r in bin_rows] + [
            (float(r[4]), float(r[5])) for r in vehicle_rows
        ]
        markers: list[Marker] = []
        if points:
            lats = [p[0] for p in points]
            lons = [p[1] for p in points]
            lat_min, lat_max = min(lats), max(lats)
            lon_min, lon_max = min(lons), max(lons)
            lat_span = (lat_max - lat_min) or 0.001
            lon_span = (lon_max - lon_min) or 0.001

            def place(lat: float, lon: float) -> tuple[str, str]:
                x = 6.0 + (lon - lon_min) / lon_span * 88.0
                y = 6.0 + (lat_max - lat) / lat_span * 88.0
                return f"{x:.2f}%", f"{y:.2f}%"

            for r in bin_rows:
                left, top = place(float(r[6]), float(r[7]))
                markers.append(
                    {
                        "key": f"BIN-{int(r[0])}",
                        "kind": "BIN",
                        "code": str(r[1]),
                        "label": str(r[2]) or str(r[1]),
                        "status": str(r[3]),
                        "area": str(r[4]),
                        "fill": float(r[5]),
                        "detail": f"{str(r[8])} · {str(r[9])} · {float(r[5]):.0f}% full",
                        "color": _STATUS_COLORS.get(str(r[3]), "#525252"),
                        "left": left,
                        "top": top,
                        "source": str(r[10]),
                    }
                )
            for r in vehicle_rows:
                left, top = place(float(r[4]), float(r[5]))
                markers.append(
                    {
                        "key": f"VEHICLE-{int(r[0])}",
                        "kind": "VEHICLE",
                        "code": str(r[1]),
                        "label": str(r[2]) or str(r[1]),
                        "status": str(r[3]),
                        "area": "Fleet",
                        "fill": 0.0,
                        "detail": f"Last position {_fmt_dt(r[6])}",
                        "color": _VEHICLE_COLORS.get(str(r[3]), "#525252"),
                        "left": left,
                        "top": top,
                        "source": str(r[7]),
                    }
                )
        async with self:
            self.markers = markers
            self.area_options = ["All"] + sorted({m["area"] for m in markers})
            if self.monitor_area not in self.area_options:
                self.monitor_area = "All"

    @rx.event
    def toggle_bins(self):
        self.show_bins = not self.show_bins

    @rx.event
    def toggle_vehicles(self):
        self.show_vehicles = not self.show_vehicles

    @rx.event
    def set_monitor_status(self, value: str):
        self.monitor_status = value

    @rx.event
    def set_monitor_area(self, value: str):
        self.monitor_area = value

    @rx.event
    def select_marker(self, key: str):
        for marker in self.markers:
            if marker["key"] == key:
                self.selected_marker = marker
                return
        self.selected_marker = _EMPTY_MARKER

    @rx.event
    def clear_marker(self):
        self.selected_marker = _EMPTY_MARKER

    @rx.event(background=True)
    async def load_routes(self):
        async with self:
            muni = self.selected_municipality_id
        if not muni:
            return
        async with rx.asession() as asession:
            rows = (
                await asession.execute(
                    text(
                        """
                        SELECT r.id, r.name, COALESCE(r.code, '—'), r.status, r.scheduled_for,
                               COALESCE(v.plate_number, 'Unassigned'), COALESCE(v.capacity_kg, 0),
                               COUNT(s.id),
                               SUM(CASE WHEN s.status = 'COLLECTED' THEN 1 ELSE 0 END),
                               COALESCE(SUM(s.collected_kg), 0), r.source
                        FROM route r
                        LEFT JOIN vehicle v ON v.id = r.vehicle_id
                        LEFT JOIN route_stop s ON s.route_id = r.id
                        WHERE r.municipality_id = :m AND r.is_active = TRUE
                        GROUP BY r.id, r.name, r.code, r.status, r.scheduled_for,
                                 v.plate_number, v.capacity_kg, r.source
                        ORDER BY CASE r.status WHEN 'IN_PROGRESS' THEN 0 WHEN 'PLANNED' THEN 1
                                 WHEN 'DRAFT' THEN 2 ELSE 3 END, r.scheduled_for DESC
                        LIMIT 40
                        """
                    ),
                    {"m": muni},
                )
            ).all()
        routes: list[RouteRow] = []
        for r in rows:
            stops = int(r[7] or 0)
            done = int(r[8] or 0)
            capacity = float(r[6] or 0)
            load = float(r[9] or 0)
            routes.append(
                {
                    "id": int(r[0]),
                    "name": str(r[1]),
                    "code": str(r[2]),
                    "status": str(r[3]),
                    "scheduled_for": r[4].isoformat() if r[4] else "—",
                    "vehicle": str(r[5]),
                    "stops": stops,
                    "done": done,
                    "progress": _pct(float(done), float(stops)),
                    "capacity_kg": capacity,
                    "load_kg": load,
                    "load_pct": _pct(load, capacity),
                    "source": str(r[10]),
                }
            )
        async with self:
            self.routes = routes
            if routes and self.selected_route_id not in [
                r["id"] for r in routes
            ]:
                self.selected_route_id = routes[0]["id"]
        yield WorkspaceState.load_route_stops

    @rx.event(background=True)
    async def load_route_stops(self):
        async with self:
            muni = self.selected_municipality_id
            route_id = self.selected_route_id
        if not muni or not route_id:
            async with self:
                self.route_stops = []
            return
        async with rx.asession() as asession:
            rows = (
                await asession.execute(
                    text(
                        """
                        SELECT s.id, s.sequence, COALESCE(b.code, '—'),
                               COALESCE(b.area_name, COALESCE(e.area_name, '—')), s.status,
                               COALESCE(s.collected_kg, 0), s.eta
                        FROM route_stop s
                        LEFT JOIN bin b ON b.id = s.bin_id
                        LEFT JOIN entity e ON e.id = s.entity_id
                        WHERE s.route_id = :r AND s.municipality_id = :m
                        ORDER BY s.sequence
                        LIMIT 200
                        """
                    ),
                    {"r": route_id, "m": muni},
                )
            ).all()
        async with self:
            self.route_stops = [
                {
                    "id": int(r[0]),
                    "sequence": int(r[1]),
                    "bin_code": str(r[2]),
                    "area": str(r[3]),
                    "status": str(r[4]),
                    "collected_kg": float(r[5]),
                    "eta": _fmt_dt(r[6]),
                    "color": {
                        "COLLECTED": "#24a148",
                        "EN_ROUTE": "#0f62fe",
                        "PENDING": "#8d8d8d",
                        "SKIPPED": "#f1c21b",
                        "FAILED": "#da1e28",
                    }.get(str(r[4]), "#525252"),
                }
                for r in rows
            ]

    @rx.event
    def select_route(self, route_id: int):
        self.selected_route_id = route_id
        return WorkspaceState.load_route_stops

    @rx.event
    def toggle_bin_selection(self, bin_id: int):
        if bin_id in self.selected_bin_ids:
            self.selected_bin_ids = [
                b for b in self.selected_bin_ids if b != bin_id
            ]
        else:
            self.selected_bin_ids = [*self.selected_bin_ids, bin_id]

    @rx.event
    def clear_bin_selection(self):
        self.selected_bin_ids = []

    @rx.event
    def set_plan_route_name(self, value: str):
        self.plan_route_name = value

    @rx.event
    def set_plan_vehicle(self, value: str):
        self.plan_vehicle_id = int(value) if value else 0

    @rx.event
    def set_alert_query(self, value: str):
        self.alert_query = value
        return WorkspaceState.load_alerts

    @rx.event
    def set_alert_severity(self, value: str):
        self.alert_severity = value
        return WorkspaceState.load_alerts

    @rx.event
    def set_alert_status(self, value: str):
        self.alert_status = value
        return WorkspaceState.load_alerts

    @rx.event
    def set_alert_source(self, value: str):
        self.alert_source = value
        return WorkspaceState.load_alerts

    @rx.event(background=True)
    async def load_alerts(self):
        async with self:
            muni = self.selected_municipality_id
            query = self.alert_query.strip()
            severity = self.alert_severity
            status = self.alert_status
            source = self.alert_source
        if not muni:
            return
        where = "WHERE a.municipality_id = :m"
        params: dict[str, str | int] = {"m": muni}
        if query:
            where += " AND (LOWER(a.title) LIKE :q OR LOWER(COALESCE(a.message, '')) LIKE :q OR LOWER(COALESCE(b.code, '')) LIKE :q)"
            params["q"] = f"%{query.lower()}%"
        if severity != "All":
            where += " AND a.severity = :sev"
            params["sev"] = severity
        if status != "All":
            where += " AND a.status = :st"
            params["st"] = status
        if source != "All":
            where += " AND a.source = :src"
            params["src"] = source
        async with rx.asession() as asession:
            rows = (
                await asession.execute(
                    text(
                        f"""
                        SELECT a.id, a.title, COALESCE(a.message, ''), a.kind, a.severity,
                               a.status, a.source, COALESCE(b.code, '—'),
                               COALESCE(a.priority_score, 0), a.created_at
                        FROM alert a
                        LEFT JOIN bin b ON b.id = a.bin_id
                        {where}
                        ORDER BY CASE a.severity WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1
                                 WHEN 'MEDIUM' THEN 2 WHEN 'LOW' THEN 3 ELSE 4 END,
                                 a.created_at DESC
                        LIMIT 60
                        """
                    ),
                    params,
                )
            ).all()
        async with self:
            self.alerts = [
                {
                    "id": int(r[0]),
                    "title": str(r[1]),
                    "message": str(r[2]),
                    "kind": str(r[3]),
                    "severity": str(r[4]),
                    "status": str(r[5]),
                    "source": str(r[6]),
                    "bin_code": str(r[7]),
                    "priority": float(r[8]),
                    "created_at": _fmt_dt(r[9]),
                    "color": {
                        "CRITICAL": "#da1e28",
                        "HIGH": "#ff832b",
                        "MEDIUM": "#f1c21b",
                        "LOW": "#0f62fe",
                        "INFO": "#8d8d8d",
                    }.get(str(r[4]), "#525252"),
                }
                for r in rows
            ]

    # ---------------- reports ---------------------------------------------
    @rx.event
    def set_report_kind(self, value: str):
        self.report_kind = value
        return WorkspaceState.load_report_preview

    @rx.event
    def set_report_start(self, value: str):
        self.report_start = value
        return WorkspaceState.load_report_preview

    @rx.event
    def set_report_end(self, value: str):
        self.report_end = value
        return WorkspaceState.load_report_preview

    def _validate_range(self) -> str:
        if not self.report_start or not self.report_end:
            return "Select both a start and an end date."
        try:
            start = datetime.date.fromisoformat(self.report_start)
            end = datetime.date.fromisoformat(self.report_end)
        except ValueError:
            return "Dates must be valid calendar dates."
        if start > end:
            return "The start date must be on or before the end date."
        if (end - start).days > 366:
            return "Reporting ranges are limited to 366 days."
        return ""

    @rx.event(background=True)
    async def load_report_preview(self):
        async with self:
            muni = self.selected_municipality_id
            error = self._validate_range()
            self.report_error = error
            self.report_notice = ""
            start, end = self.report_start, self.report_end
            self.report_loading = not error
        if not muni or error:
            async with self:
                self.report_loading = False
            return
        params = {"m": muni, "start": start, "end": f"{end} 23:59:59"}
        async with rx.asession() as asession:
            by_type = (
                await asession.execute(
                    text(
                        """
                        SELECT COALESCE(w.name, 'Unclassified'), COALESCE(SUM(r.quantity_kg), 0)
                        FROM waste_record r
                        LEFT JOIN waste_type w ON w.id = r.waste_type_id
                        WHERE r.municipality_id = :m AND r.is_active = TRUE
                          AND r.collected_at >= CAST(:start AS timestamp)
                          AND r.collected_at <= CAST(:end AS timestamp)
                        GROUP BY w.name ORDER BY 2 DESC LIMIT 20
                        """
                    ),
                    params,
                )
            ).all()
            by_area = (
                await asession.execute(
                    text(
                        """
                        SELECT COALESCE(e.area_name, 'Unzoned'), COALESCE(SUM(r.quantity_kg), 0)
                        FROM waste_record r
                        LEFT JOIN entity e ON e.id = r.entity_id
                        WHERE r.municipality_id = :m AND r.is_active = TRUE
                          AND r.collected_at >= CAST(:start AS timestamp)
                          AND r.collected_at <= CAST(:end AS timestamp)
                        GROUP BY e.area_name ORDER BY 2 DESC LIMIT 20
                        """
                    ),
                    params,
                )
            ).all()
            kpi = (
                await asession.execute(
                    text(
                        """
                        SELECT
                          (SELECT COALESCE(SUM(quantity_kg), 0) FROM waste_record
                            WHERE municipality_id = :m AND is_active = TRUE
                              AND collected_at >= CAST(:start AS timestamp)
                              AND collected_at <= CAST(:end AS timestamp)),
                          (SELECT COALESCE(SUM(recycled_kg), 0) FROM waste_record
                            WHERE municipality_id = :m AND is_active = TRUE
                              AND collected_at >= CAST(:start AS timestamp)
                              AND collected_at <= CAST(:end AS timestamp)),
                          (SELECT COALESCE(SUM(landfill_kg), 0) FROM waste_record
                            WHERE municipality_id = :m AND is_active = TRUE
                              AND collected_at >= CAST(:start AS timestamp)
                              AND collected_at <= CAST(:end AS timestamp)),
                          (SELECT COUNT(*) FROM waste_record
                            WHERE municipality_id = :m AND is_active = TRUE
                              AND collected_at >= CAST(:start AS timestamp)
                              AND collected_at <= CAST(:end AS timestamp)),
                          (SELECT COUNT(*) FROM route_stop
                            WHERE municipality_id = :m AND status = 'COLLECTED'),
                          (SELECT COUNT(*) FROM alert
                            WHERE municipality_id = :m
                              AND created_at >= CAST(:start AS timestamp)
                              AND created_at <= CAST(:end AS timestamp))
                        """
                    ),
                    params,
                )
            ).first()
        total = float(kpi[0]) if kpi else 0.0
        days = max(
            1,
            (
                datetime.date.fromisoformat(end)
                - datetime.date.fromisoformat(start)
            ).days
            + 1,
        )
        async with self:
            self.report_by_type = [
                {
                    "label": str(r[0]),
                    "kg": float(r[1]),
                    "share": _pct(float(r[1]), total),
                }
                for r in by_type
            ]
            self.report_by_area = [
                {
                    "label": str(r[0]),
                    "kg": float(r[1]),
                    "share": _pct(float(r[1]), total),
                }
                for r in by_area
            ]
            if kpi:
                self.report_kpis = {
                    "total_kg": total,
                    "recycled_kg": float(kpi[1]),
                    "landfill_kg": float(kpi[2]),
                    "records": float(kpi[3]),
                    "recycling_rate": _pct(float(kpi[1]), total),
                    "collections_per_day": round(float(kpi[3]) / days, 2),
                    "stops_completed": float(kpi[4]),
                    "alerts_raised": float(kpi[5]),
                }
            self.report_loading = False

    # ---------------- guarded mutations -----------------------------------
    async def _authorized_actor(self) -> SessionUser | None:
        """Re-verify the signed-in account's role against PostgreSQL.

        Every mutation calls this immediately before it writes, so a stale
        or revoked session can never reach the database.
        """
        auth = await self.get_state(AuthState)
        return await auth.verify_privileged()

    async def _audit(
        self,
        asession,
        muni: int,
        actor: SessionUser,
        action: str,
        table_name: str,
        record_id: int | None,
        summary: str,
    ) -> None:
        await asession.execute(
            text(
                """
                INSERT INTO audit_log
                    (municipality_id, user_id, actor_label, actor_role, action,
                     table_name, record_id, summary, source)
                VALUES (:m, :uid, :actor, :role, :action, :table, :rec,
                        :summary, 'MANUAL')
                """
            ),
            {
                "m": muni,
                "uid": actor["id"],
                "actor": actor["label"],
                "role": actor["role"],
                "action": action,
                "table": table_name,
                "rec": record_id,
                "summary": summary,
            },
        )

    @rx.event
    async def acknowledge_alert(self, alert_id: int):
        actor = await self._authorized_actor()
        if actor is None:
            self.error_message = _DENIED
            return
        muni = self.selected_municipality_id
        async with rx.asession() as asession:
            result = await asession.execute(
                text(
                    """
                    UPDATE alert
                    SET status = 'ACKNOWLEDGED', acknowledged_at = :now,
                        acknowledged_by_user_id = :uid
                    WHERE id = :a AND municipality_id = :m AND status = 'OPEN'
                    """
                ),
                {
                    "a": alert_id,
                    "m": muni,
                    "uid": actor["id"],
                    "now": datetime.datetime.now(datetime.timezone.utc),
                },
            )
            if result.rowcount == 0:
                self.status_message = (
                    "Alert could not be acknowledged (already handled)."
                )
                return
            await self._audit(
                asession,
                muni,
                actor,
                "UPDATE",
                "alert",
                alert_id,
                f"Acknowledged alert {alert_id}.",
            )
            await asession.commit()
        self.status_message = (
            f"Alert {alert_id} acknowledged and recorded in the audit log."
        )
        yield WorkspaceState.load_alerts
        yield WorkspaceState.load_overview

    @rx.event
    async def resolve_alert(self, alert_id: int):
        actor = await self._authorized_actor()
        if actor is None:
            self.error_message = _DENIED
            return
        muni = self.selected_municipality_id
        now = datetime.datetime.now(datetime.timezone.utc)
        async with rx.asession() as asession:
            result = await asession.execute(
                text(
                    """
                    UPDATE alert
                    SET status = 'RESOLVED', resolved_at = :now,
                        acknowledged_by_user_id = COALESCE(acknowledged_by_user_id, :uid),
                        resolution_note = 'Resolved from the operations workspace.'
                    WHERE id = :a AND municipality_id = :m AND status IN ('OPEN','ACKNOWLEDGED')
                    """
                ),
                {"a": alert_id, "m": muni, "uid": actor["id"], "now": now},
            )
            if result.rowcount == 0:
                self.status_message = (
                    "Alert could not be resolved (already closed)."
                )
                return
            await self._audit(
                asession,
                muni,
                actor,
                "UPDATE",
                "alert",
                alert_id,
                f"Resolved alert {alert_id}.",
            )
            await asession.commit()
        self.status_message = (
            f"Alert {alert_id} resolved and recorded in the audit log."
        )
        yield WorkspaceState.load_alerts
        yield WorkspaceState.load_overview

    @rx.event
    async def plan_route(self):
        actor = await self._authorized_actor()
        if actor is None:
            self.error_message = _DENIED
            return
        muni = self.selected_municipality_id
        if not muni:
            self.error_message = "Select a municipality first."
            return
        if not self.selected_bin_ids:
            self.error_message = (
                "Select at least one priority bin to build a route."
            )
            return
        if len(self.selected_bin_ids) > 30:
            self.error_message = "A single route plan is limited to 30 stops."
            return
        name = self.plan_route_name.strip() or (
            f"Approved plan {datetime.datetime.now().strftime('%d %b %H:%M')}"
        )
        self.error_message = ""
        self.planning = True
        bin_ids = list(self.selected_bin_ids)
        vehicle_id = self.plan_vehicle_id or None
        async with rx.asession() as asession:
            route_id = (
                await asession.execute(
                    text(
                        """
                        INSERT INTO route
                            (municipality_id, name, code, vehicle_id, status,
                             scheduled_for, planned_distance_km, planned_duration_minutes,
                             approved_by_user_id, source, notes, is_active)
                        VALUES (:m, :name, :code, :v, 'DRAFT', :sched, NULL, :dur,
                                :uid, 'MANUAL', :notes, TRUE)
                        RETURNING id
                        """
                    ),
                    {
                        "m": muni,
                        "name": name,
                        "code": f"RT-APP-{datetime.datetime.now().strftime('%H%M%S')}",
                        "v": vehicle_id,
                        "sched": datetime.date.today(),
                        "dur": len(bin_ids) * 18,
                        "uid": actor["id"],
                        "notes": "Human-approved plan created from selected priority bins.",
                    },
                )
            ).scalar_one()
            for sequence, bin_id in enumerate(bin_ids, start=1):
                await asession.execute(
                    text(
                        """
                        INSERT INTO route_stop
                            (route_id, municipality_id, sequence, bin_id, entity_id,
                             status, latitude, longitude, source, notes)
                        SELECT :r, :m, :seq, b.id, b.entity_id, 'PENDING',
                               b.latitude, b.longitude, 'MANUAL',
                               'Stop approved by operator.'
                        FROM bin b
                        WHERE b.id = :b AND b.municipality_id = :m
                        """
                    ),
                    {"r": route_id, "m": muni, "seq": sequence, "b": bin_id},
                )
            await self._audit(
                asession,
                muni,
                actor,
                "CREATE",
                "route",
                route_id,
                f"Approved DRAFT route '{name}' with {len(bin_ids)} stops.",
            )
            await asession.commit()
        self.planning = False
        self.selected_bin_ids = []
        self.plan_route_name = ""
        self.selected_route_id = int(route_id)
        self.status_message = (
            f"DRAFT route '{name}' created with {len(bin_ids)} stops."
        )
        yield WorkspaceState.load_routes

    @rx.event
    async def generate_csv_report(self):
        actor = await self._authorized_actor()
        if actor is None:
            self.report_error = _DENIED
            return
        muni = self.selected_municipality_id
        error = self._validate_range()
        if not muni:
            error = "Select a municipality first."
        if error:
            self.report_error = error
            return
        self.report_error = ""
        self.report_notice = ""
        start, end = self.report_start, self.report_end
        kind = self.report_kind
        params = {"m": muni, "start": start, "end": f"{end} 23:59:59"}
        async with rx.asession() as asession:
            rows = (
                await asession.execute(
                    text(
                        """
                        SELECT r.collected_at, COALESCE(e.name, 'Unassigned'),
                               COALESCE(e.area_name, 'Unzoned'), COALESCE(w.name, 'Unclassified'),
                               COALESCE(b.code, '—'), COALESCE(r.quantity_kg, 0),
                               COALESCE(r.recycled_kg, 0), COALESCE(r.landfill_kg, 0),
                               COALESCE(r.disposal_site, ''), r.source
                        FROM waste_record r
                        LEFT JOIN entity e ON e.id = r.entity_id
                        LEFT JOIN waste_type w ON w.id = r.waste_type_id
                        LEFT JOIN bin b ON b.id = r.bin_id
                        WHERE r.municipality_id = :m AND r.is_active = TRUE
                          AND r.collected_at >= CAST(:start AS timestamp)
                          AND r.collected_at <= CAST(:end AS timestamp)
                        ORDER BY r.collected_at DESC
                        LIMIT 5000
                        """
                    ),
                    params,
                )
            ).all()

            if not rows:
                self.report_error = (
                    "No waste records fall inside the selected range."
                )
                return

            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["ZWaste Monitor AI municipal waste report"])
            writer.writerow(["Municipality", self.selected_municipality_name])
            writer.writerow(["Report type", kind])
            writer.writerow(["Period", f"{start} to {end}"])
            writer.writerow(
                [
                    "Notice",
                    "Contains SIMULATED demonstration data - not verified municipal fact.",
                ]
            )
            writer.writerow([])
            writer.writerow(
                [
                    "collected_at",
                    "entity",
                    "area",
                    "waste_type",
                    "bin_code",
                    "quantity_kg",
                    "recycled_kg",
                    "landfill_kg",
                    "disposal_site",
                    "source",
                ]
            )
            for r in rows:
                writer.writerow(
                    [
                        r[0].isoformat() if r[0] else "",
                        r[1],
                        r[2],
                        r[3],
                        r[4],
                        f"{float(r[5]):.1f}",
                        f"{float(r[6]):.1f}",
                        f"{float(r[7]):.1f}",
                        r[8],
                        r[9],
                    ]
                )
            csv_text = buffer.getvalue()
            file_name = f"zwaste_{kind.lower()}_{start}_{end}.csv"

            report_id = (
                await asession.execute(
                    text(
                        """
                        INSERT INTO report
                            (municipality_id, kind, export_format, status, title,
                             period_start, period_end, filters_summary, row_count,
                             file_name, generated_at, generated_by_user_id, source)
                        VALUES (:m, :kind, 'CSV', 'READY', :title, CAST(:start AS date),
                                CAST(:end_date AS date), :filters, :rows, :file, :now,
                                :uid, 'DERIVED')
                        RETURNING id
                        """
                    ),
                    {
                        "m": muni,
                        "kind": kind,
                        "title": f"{kind.title()} waste report {start} to {end}",
                        "start": start,
                        "end_date": end,
                        "filters": f"kind={kind}; period={start}..{end}",
                        "rows": len(rows),
                        "file": file_name,
                        "now": datetime.datetime.now(datetime.timezone.utc),
                        "uid": actor["id"],
                    },
                )
            ).scalar_one()
            await self._audit(
                asession,
                muni,
                actor,
                "EXPORT",
                "report",
                report_id,
                f"Generated {kind} CSV report ({len(rows)} rows) for {start}..{end}.",
            )
            await asession.commit()

        self.last_report_name = file_name
        self.report_notice = f"Report #{report_id} created with {len(rows)} rows and logged in the audit trail."
        return rx.download(data=csv_text, filename=file_name)

    @rx.event
    def dismiss_messages(self):
        self.status_message = ""
        self.error_message = ""
