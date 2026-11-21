from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.settings import database_dsn


def create_pool() -> ConnectionPool:
  return ConnectionPool(
    database_dsn(), min_size=4, max_size=20, kwargs={"row_factory": dict_row}, open=True
  )
