import os

import reflex as rx

# Managed database URL (never logged or exposed to the frontend).
_raw_db_url = os.environ.get("REFLEX_DB_URL") or os.environ.get(
    "DATABASE_URL", ""
)


def _with_driver(url: str, driver: str) -> str:
    """Normalize a Postgres URL onto the psycopg3 driver Reflex needs."""
    if not url:
        return url
    scheme, sep, rest = url.partition("://")
    if not sep:
        return url
    base = scheme.split("+", 1)[0]
    if base in ("postgres", "postgresql"):
        return f"postgresql+{driver}://{rest}"
    return url


_db_url = _with_driver(_raw_db_url, "psycopg")
_async_db_url = _with_driver(_raw_db_url, "psycopg")

_db_settings = (
    {"db_url": _db_url, "async_db_url": _async_db_url} if _db_url else {}
)

config = rx.Config(
    app_name="app",
    **_db_settings,
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
)
