"""Idempotent first-load demo seed.

Every row created here is labelled SIMULATED. It is demonstration data and
must never be presented as verified municipal fact.
"""

from __future__ import annotations

import datetime
import random

from sqlalchemy import text

SIM = "SIMULATED"

_WASTE_TYPES = [
    ("General waste", "GEN", "Mixed", "#525252", False, False, 180.0),
    ("Organic", "ORG", "Biodegradable", "#24a148", False, True, 400.0),
    ("Plastics", "PLA", "Recyclable", "#0f62fe", False, True, 60.0),
    ("Paper & card", "PAP", "Recyclable", "#8a3ffc", False, True, 90.0),
    ("Glass", "GLS", "Recyclable", "#009d9a", False, True, 320.0),
    ("Clinical", "CLI", "Hazardous", "#da1e28", True, False, 150.0),
]

_ENTITIES = [
    (
        "INSTITUTION",
        "Riverside Technical College",
        "ENT-COL-01",
        "Riverside",
        620.0,
    ),
    (
        "HOSPITAL",
        "Greenfield General Hospital",
        "ENT-HOS-01",
        "Greenfield",
        940.0,
    ),
    ("BUSINESS", "Central Market Traders", "ENT-BUS-01", "Central", 780.0),
    ("BUSINESS", "Lakeview Retail Park", "ENT-BUS-02", "Lakeview", 510.0),
    ("PUBLIC_SPACE", "Unity Civic Park", "ENT-PUB-01", "Central", 210.0),
]

_STATUS_BY_FILL = [
    (100.0, "OVERFLOW"),
    (92.0, "FULL"),
    (75.0, "NEAR_FULL"),
    (40.0, "FILLING"),
    (0.0, "OK"),
]


def _bin_status(fill: float) -> str:
    for threshold, status in _STATUS_BY_FILL:
        if fill >= threshold:
            return status
    return "OK"


async def seed_demo_data(asession) -> bool:
    """Create the SIMULATED demo municipality if the database is empty."""
    existing = (
        await asession.execute(text("SELECT COUNT(*) FROM municipality"))
    ).scalar_one()
    if existing:
        return False

    rnd = random.Random(20240607)
    now = datetime.datetime.now(datetime.timezone.utc)
    center_lat, center_lon = -1.2921, 36.8219

    muni_id = (
        await asession.execute(
            text(
                """
                INSERT INTO municipality
                    (name, code, region, country, population, area_km2,
                     contact_email, contact_phone, timezone, latitude, longitude,
                     performance_score, source, notes, is_active)
                VALUES
                    (:name, :code, :region, :country, :population, :area,
                     :email, :phone, :tz, :lat, :lon, :score, :source, :notes, TRUE)
                RETURNING id
                """
            ),
            {
                "name": "Nairobi Central (SIMULATED)",
                "code": "SIM-NBO-01",
                "region": "Nairobi County",
                "country": "Kenya",
                "population": 480000,
                "area": 84.5,
                "email": "operations@simulated.zwaste.example",
                "phone": "+254 700 000 000",
                "tz": "Africa/Nairobi",
                "lat": center_lat,
                "lon": center_lon,
                "score": 78.4,
                "source": SIM,
                "notes": "Demonstration municipality. All records are SIMULATED.",
            },
        )
    ).scalar_one()

    waste_type_ids: list[int] = []
    for (
        name,
        code,
        category,
        color,
        hazardous,
        recyclable,
        density,
    ) in _WASTE_TYPES:
        wid = (
            await asession.execute(
                text(
                    """
                    INSERT INTO waste_type
                        (municipality_id, name, code, category, color_hex,
                         is_hazardous, is_recyclable, density_kg_per_m3,
                         disposal_cost_per_kg, source, is_active)
                    VALUES
                        (:m, :name, :code, :category, :color, :haz, :rec,
                         :density, :cost, :source, TRUE)
                    RETURNING id
                    """
                ),
                {
                    "m": muni_id,
                    "name": name,
                    "code": code,
                    "category": category,
                    "color": color,
                    "haz": hazardous,
                    "rec": recyclable,
                    "density": density,
                    "cost": round(rnd.uniform(0.04, 0.35), 3),
                    "source": SIM,
                },
            )
        ).scalar_one()
        waste_type_ids.append(wid)

    entity_ids: list[int] = []
    for idx, (kind, name, code, area, daily_kg) in enumerate(_ENTITIES):
        lat = center_lat + rnd.uniform(-0.018, 0.018)
        lon = center_lon + rnd.uniform(-0.018, 0.018)
        eid = (
            await asession.execute(
                text(
                    """
                    INSERT INTO entity
                        (municipality_id, kind, name, code, area_name, address,
                         latitude, longitude, contact_email, expected_daily_kg,
                         source, notes, is_active, is_future_architecture)
                    VALUES
                        (:m, :kind, :name, :code, :area, :address, :lat, :lon,
                         :email, :daily, :source, :notes, TRUE, FALSE)
                    RETURNING id
                    """
                ),
                {
                    "m": muni_id,
                    "kind": kind,
                    "name": name,
                    "code": code,
                    "area": area,
                    "address": f"{100 + idx * 17} {area} Road",
                    "lat": lat,
                    "lon": lon,
                    "email": f"facilities{idx}@simulated.zwaste.example",
                    "daily": daily_kg,
                    "source": SIM,
                    "notes": "SIMULATED demonstration entity.",
                },
            )
        ).scalar_one()
        entity_ids.append(eid)

    bins: list[
        tuple[int, float, str, int]
    ] = []  # (bin_id, fill, area, entity_id)
    bin_ids: list[int] = []
    for idx in range(18):
        entity_idx = idx % len(entity_ids)
        entity_id = entity_ids[entity_idx]
        area = _ENTITIES[entity_idx][3]
        waste_type_id = waste_type_ids[idx % len(waste_type_ids)]
        fill = round(min(100.0, max(4.0, rnd.gauss(62, 26))), 1)
        capacity = rnd.choice([240.0, 660.0, 1100.0])
        lat = center_lat + rnd.uniform(-0.022, 0.022)
        lon = center_lon + rnd.uniform(-0.022, 0.022)
        bin_id = (
            await asession.execute(
                text(
                    """
                    INSERT INTO bin
                        (municipality_id, entity_id, waste_type_id, code, label,
                         container_type, capacity_liters, capacity_kg, fill_percent,
                         current_weight_kg, status, latitude, longitude, area_name,
                         last_reading_at, last_emptied_at, full_threshold_percent,
                         source, notes, is_active)
                    VALUES
                        (:m, :e, :w, :code, :label, :ctype, :cap_l, :cap_kg, :fill,
                         :weight, :status, :lat, :lon, :area, :read_at, :empt_at,
                         85.0, :source, :notes, TRUE)
                    RETURNING id
                    """
                ),
                {
                    "m": muni_id,
                    "e": entity_id,
                    "w": waste_type_id,
                    "code": f"BIN-{idx + 1:03d}",
                    "label": f"{area} container {idx + 1}",
                    "ctype": rnd.choice(
                        ["Wheeled bin", "Skip", "Front loader"]
                    ),
                    "cap_l": capacity,
                    "cap_kg": round(capacity * 0.28, 1),
                    "fill": fill,
                    "weight": round(capacity * 0.28 * fill / 100.0, 1),
                    "status": _bin_status(fill),
                    "lat": lat,
                    "lon": lon,
                    "area": area,
                    "read_at": now
                    - datetime.timedelta(minutes=rnd.randint(5, 320)),
                    "empt_at": now
                    - datetime.timedelta(hours=rnd.randint(8, 96)),
                    "source": SIM,
                    "notes": "SIMULATED container.",
                },
            )
        ).scalar_one()
        bin_ids.append(bin_id)
        bins.append((bin_id, fill, area, entity_id))

    sensor_ids: list[int] = []
    for idx, (bin_id, fill, _area, _entity_id) in enumerate(bins):
        status = "ACTIVE"
        battery = round(rnd.uniform(35, 100), 1)
        if idx % 9 == 4:
            status, battery = "LOW_BATTERY", round(rnd.uniform(5, 18), 1)
        elif idx % 11 == 7:
            status = "FAULTY"
        last_seen = now - datetime.timedelta(
            minutes=rnd.randint(3, 90)
            if status == "ACTIVE"
            else rnd.randint(400, 2000)
        )
        sid = (
            await asession.execute(
                text(
                    """
                    INSERT INTO sensor
                        (municipality_id, bin_id, device_serial, model,
                         firmware_version, status, battery_percent,
                         signal_strength_dbm, reporting_interval_minutes,
                         last_seen_at, last_calibrated_at, source, is_active)
                    VALUES
                        (:m, :b, :serial, 'GateZ-1', '1.4.2', :status, :battery,
                         :signal, 30, :seen, :cal, :source, TRUE)
                    RETURNING id
                    """
                ),
                {
                    "m": muni_id,
                    "b": bin_id,
                    "serial": f"GZ-{20240000 + idx}",
                    "status": status,
                    "battery": battery,
                    "signal": round(rnd.uniform(-105, -58), 1),
                    "seen": last_seen,
                    "cal": now - datetime.timedelta(days=rnd.randint(20, 200)),
                    "source": SIM,
                },
            )
        ).scalar_one()
        sensor_ids.append(sid)

        for step in range(10):
            recorded = now - datetime.timedelta(hours=(10 - step) * 3)
            reading_fill = round(
                max(
                    0.0, min(100.0, fill - (10 - step) * rnd.uniform(1.5, 5.0))
                ),
                1,
            )
            await asession.execute(
                text(
                    """
                    INSERT INTO sensor_reading
                        (municipality_id, sensor_id, bin_id, recorded_at,
                         fill_percent, weight_kg, temperature_c, battery_percent,
                         is_valid, source)
                    VALUES
                        (:m, :s, :b, :ts, :fill, :weight, :temp, :battery, TRUE, :source)
                    """
                ),
                {
                    "m": muni_id,
                    "s": sid,
                    "b": bin_id,
                    "ts": recorded,
                    "fill": reading_fill,
                    "weight": round(reading_fill * 1.8, 1),
                    "temp": round(rnd.uniform(19, 34), 1),
                    "battery": battery,
                    "source": "GATEZ_DEVICE",
                },
            )

    vehicle_ids: list[int] = []
    vehicle_specs = [
        ("KDA 411X", "Compactor 1", 8200.0, "ON_ROUTE"),
        ("KDB 902M", "Compactor 2", 7600.0, "AVAILABLE"),
        ("KDC 118T", "Tipper 1", 4200.0, "AVAILABLE"),
        ("KDD 774R", "Clinical van", 2400.0, "MAINTENANCE"),
        ("KDE 350P", "Compactor 3", 8200.0, "ON_ROUTE"),
    ]
    for idx, (plate, label, cap, status) in enumerate(vehicle_specs):
        vid = (
            await asession.execute(
                text(
                    """
                    INSERT INTO vehicle
                        (municipality_id, plate_number, label, make, model, year,
                         capacity_kg, capacity_liters, fuel_type, odometer_km,
                         status, last_latitude, last_longitude, last_position_at,
                         next_service_due_on, source, is_active)
                    VALUES
                        (:m, :plate, :label, 'Isuzu', 'FVR', :year, :cap, :cap_l,
                         'Diesel', :odo, :status, :lat, :lon, :pos_at, :service,
                         :source, TRUE)
                    RETURNING id
                    """
                ),
                {
                    "m": muni_id,
                    "plate": plate,
                    "label": label,
                    "year": 2018 + idx,
                    "cap": cap,
                    "cap_l": cap * 3.2,
                    "odo": round(rnd.uniform(38000, 210000), 0),
                    "status": status,
                    "lat": center_lat + rnd.uniform(-0.02, 0.02),
                    "lon": center_lon + rnd.uniform(-0.02, 0.02),
                    "pos_at": now
                    - datetime.timedelta(minutes=rnd.randint(2, 45)),
                    "service": (
                        now + datetime.timedelta(days=rnd.randint(10, 120))
                    ).date(),
                    "source": SIM,
                },
            )
        ).scalar_one()
        vehicle_ids.append(vid)

    route_specs = [
        ("Central morning sweep", "RT-CEN-AM", "IN_PROGRESS", 0),
        ("Riverside & Lakeview", "RT-RIV-PM", "PLANNED", 1),
        ("Clinical priority run", "RT-CLI-01", "COMPLETED", 4),
    ]
    bin_cursor = 0
    for idx, (name, code, status, vehicle_idx) in enumerate(route_specs):
        route_id = (
            await asession.execute(
                text(
                    """
                    INSERT INTO route
                        (municipality_id, name, code, vehicle_id, status,
                         scheduled_for, started_at, completed_at,
                         planned_distance_km, planned_duration_minutes,
                         total_collected_kg, source, notes, is_active)
                    VALUES
                        (:m, :name, :code, :v, :status, :sched, :started,
                         :completed, :dist, :dur, :collected, :source, :notes, TRUE)
                    RETURNING id
                    """
                ),
                {
                    "m": muni_id,
                    "name": name,
                    "code": code,
                    "v": vehicle_ids[vehicle_idx],
                    "status": status,
                    "sched": now.date(),
                    "started": now - datetime.timedelta(hours=3)
                    if status in ("IN_PROGRESS", "COMPLETED")
                    else None,
                    "completed": now - datetime.timedelta(hours=1)
                    if status == "COMPLETED"
                    else None,
                    "dist": round(rnd.uniform(18, 62), 1),
                    "dur": rnd.randint(120, 340),
                    "collected": round(rnd.uniform(900, 4200), 1),
                    "source": SIM,
                    "notes": "SIMULATED route plan.",
                },
            )
        ).scalar_one()

        stop_count = 5 + idx
        for seq in range(1, stop_count + 1):
            bin_id, fill, area, entity_id = bins[bin_cursor % len(bins)]
            bin_cursor += 1
            if status == "COMPLETED":
                stop_status = "COLLECTED"
            elif status == "IN_PROGRESS":
                stop_status = (
                    "COLLECTED"
                    if seq <= 3
                    else ("EN_ROUTE" if seq == 4 else "PENDING")
                )
            else:
                stop_status = "PENDING"
            collected = (
                round(rnd.uniform(60, 380), 1)
                if stop_status == "COLLECTED"
                else None
            )
            await asession.execute(
                text(
                    """
                    INSERT INTO route_stop
                        (route_id, municipality_id, sequence, bin_id, entity_id,
                         status, latitude, longitude, eta, completed_at,
                         collected_kg, source, notes)
                    VALUES
                        (:r, :m, :seq, :b, :e, :status, :lat, :lon, :eta,
                         :completed, :collected, :source, :notes)
                    """
                ),
                {
                    "r": route_id,
                    "m": muni_id,
                    "seq": seq,
                    "b": bin_id,
                    "e": entity_id,
                    "status": stop_status,
                    "lat": center_lat + rnd.uniform(-0.02, 0.02),
                    "lon": center_lon + rnd.uniform(-0.02, 0.02),
                    "eta": now + datetime.timedelta(minutes=seq * 22),
                    "completed": now - datetime.timedelta(minutes=seq * 15)
                    if stop_status == "COLLECTED"
                    else None,
                    "collected": collected,
                    "source": SIM,
                    "notes": f"SIMULATED stop in {area}.",
                },
            )

    alert_specs = [
        ("BIN_FULL", "CRITICAL", "OPEN", "Container reported overflow", 0),
        ("BIN_FULL", "HIGH", "OPEN", "Container above full threshold", 1),
        (
            "OVERFLOW_FORECAST",
            "HIGH",
            "OPEN",
            "Overflow forecast within 6 hours",
            2,
        ),
        (
            "SENSOR_FAULT",
            "MEDIUM",
            "OPEN",
            "Sensor returning implausible readings",
            3,
        ),
        (
            "SENSOR_OFFLINE",
            "MEDIUM",
            "ACKNOWLEDGED",
            "Sensor has not reported in 18 hours",
            4,
        ),
        ("ANOMALY", "LOW", "OPEN", "Unusual fill pattern detected", 5),
        (
            "HAZARDOUS_WASTE",
            "CRITICAL",
            "OPEN",
            "Clinical waste container needs collection",
            6,
        ),
        (
            "ROUTE_DELAY",
            "MEDIUM",
            "ACKNOWLEDGED",
            "Route running behind schedule",
            7,
        ),
        (
            "MISSED_COLLECTION",
            "HIGH",
            "OPEN",
            "Scheduled collection was missed",
            8,
        ),
        ("BIN_FULL", "LOW", "RESOLVED", "Container emptied after alert", 9),
    ]
    for kind, severity, status, title, idx in alert_specs:
        bin_id = bins[idx % len(bins)][0]
        sensor_id = sensor_ids[idx % len(sensor_ids)]
        await asession.execute(
            text(
                """
                INSERT INTO alert
                    (municipality_id, kind, severity, status, title, message,
                     priority_score, bin_id, sensor_id, acknowledged_at,
                     resolved_at, resolution_note, source)
                VALUES
                    (:m, :kind, :sev, :status, :title, :message, :score, :b, :s,
                     :ack, :res, :note, :source)
                """
            ),
            {
                "m": muni_id,
                "kind": kind,
                "sev": severity,
                "status": status,
                "title": title,
                "message": f"SIMULATED alert generated from demonstration sensor data ({kind}).",
                "score": round(rnd.uniform(20, 99), 1),
                "b": bin_id,
                "s": sensor_id,
                "ack": now - datetime.timedelta(hours=2)
                if status in ("ACKNOWLEDGED", "RESOLVED")
                else None,
                "res": now - datetime.timedelta(hours=1)
                if status == "RESOLVED"
                else None,
                "note": "Demo resolution note."
                if status == "RESOLVED"
                else None,
                "source": "DERIVED",
            },
        )

    for day in range(45):
        collected_day = now - datetime.timedelta(days=day)
        for _ in range(4):
            entity_idx = rnd.randrange(len(entity_ids))
            quantity = round(rnd.uniform(40, 520), 1)
            recycled = round(quantity * rnd.uniform(0.05, 0.55), 1)
            await asession.execute(
                text(
                    """
                    INSERT INTO waste_record
                        (municipality_id, entity_id, bin_id, waste_type_id,
                         collected_at, quantity_kg, volume_liters, recycled_kg,
                         landfill_kg, disposal_site, cost, source, notes, is_active)
                    VALUES
                        (:m, :e, :b, :w, :ts, :qty, :vol, :rec, :land, :site,
                         :cost, :source, :notes, TRUE)
                    """
                ),
                {
                    "m": muni_id,
                    "e": entity_ids[entity_idx],
                    "b": bin_ids[rnd.randrange(len(bin_ids))],
                    "w": waste_type_ids[rnd.randrange(len(waste_type_ids))],
                    "ts": collected_day
                    - datetime.timedelta(minutes=rnd.randint(0, 600)),
                    "qty": quantity,
                    "vol": round(quantity * rnd.uniform(2.0, 6.0), 1),
                    "rec": recycled,
                    "land": round(quantity - recycled, 1),
                    "site": rnd.choice(
                        ["Dandora transfer", "Kibera MRF", "Ruai landfill"]
                    ),
                    "cost": round(quantity * rnd.uniform(0.05, 0.3), 2),
                    "source": SIM,
                    "notes": "SIMULATED collection record.",
                },
            )

    await asession.execute(
        text(
            """
            INSERT INTO audit_log
                (municipality_id, actor_label, action, table_name, record_id,
                 summary, source)
            VALUES (:m, 'system seed', 'SIMULATE', 'municipality', :m,
                    'Seeded SIMULATED demonstration municipality and operations data.',
                    :source)
            """
        ),
        {"m": muni_id, "source": SIM},
    )
    await asession.commit()
    return True
