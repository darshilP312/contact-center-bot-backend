import asyncio
from sqlalchemy import text
from app.database.session import async_session_factory

async def main():
    async with async_session_factory() as db:
        res = await db.execute(text("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name, ordinal_position"))
        cols = res.fetchall()
        print("=== Columns by Table ===")
        current_table = None
        for table, col in cols:
            if table != current_table:
                print(f"\n[{table}]")
                current_table = table
            print(f"  - {col}")

        for t in ["conversation_state", "conversation", "message", "account", "invoice", "agent", "service_type", "appointment", "billing_transaction"]:
            try:
                res = await db.execute(text(f"SELECT COUNT(*) FROM {t}"))
                print(f"Total rows in '{t}': {res.scalar()}")
            except Exception as e:
                print(f"Error querying '{t}': {e}")

if __name__ == "__main__":
    asyncio.run(main())
