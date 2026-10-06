import aiosqlite

DATABASE_PATH = "beacon.db"

async def init_database():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                suggestion_channel_id INTEGER,
                archive_channel_id INTEGER,
                staff_role_id INTEGER,
                anonymous_enabled INTEGER NOT NULL DEFAULT 1,
                voting_enabled INTEGER NOT NULL DEFAULT 1
                )
        """)

        await db.commit()