from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .config import DATABASE_URL, DB_CONNECT_TIMEOUT


def serialize_value(value):
    if isinstance(value, dict):
        return {key: serialize_value(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [serialize_value(item) for item in value]
    if isinstance(value, tuple):
        return [serialize_value(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def serialize_row(row):
    if row is None:
        return None
    return {key: serialize_value(value) for key, value in row.items()}


@contextmanager
def get_conn(dsn=None):
    conn = psycopg.connect(
        dsn or DATABASE_URL,
        row_factory=dict_row,
        connect_timeout=DB_CONNECT_TIMEOUT,
    )
    try:
        yield conn
    finally:
        conn.close()
