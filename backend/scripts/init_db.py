import asyncio

import psycopg2

from app.db.session import engine
from app.models.db_models import Base


def ensure_database() -> None:
    conn = psycopg2.connect(
        host="60.13.232.229",
        port=5432,
        user="postgres",
        password="mSCiRD8SstxKhnMk",
        dbname="postgres",
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname='ai_test'")
        exists = cur.fetchone()
        if not exists:
            cur.execute("CREATE DATABASE ai_test")
    conn.close()


async def init_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


if __name__ == "__main__":
    ensure_database()
    asyncio.run(init_tables())
    print("database initialized")
