import aiosqlite

DATABASE_PATH = "beacon.db"

## Initialize the database
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

## Get guild settings from the database
async def get_guild_settings(guild_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT *
            FROM guild_settings
            WHERE guild_id = ?
            """,
            (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()

        return row

async def save_guild_settings(
        guild_id: int, 
        suggestion_channel_id: int, 
        archive_channel_id: int, 
        staff_role_id: int | None = None, 
        anonymous_enabled: bool = True, 
        voting_enabled: bool = True
):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO guild_settings (
                guild_id,
                suggestion_channel_id,
                archive_channel_id,
                staff_role_id,
                anonymous_enabled,
                voting_enabled
            ) VALUES (?, ?, ?, ?, ?, ?)

            ON CONFLICT(guild_id) DO UPDATE SET
                suggestion_channel_id=excluded.suggestion_channel_id,
                archive_channel_id=excluded.archive_channel_id,
                staff_role_id=excluded.staff_role_id,
                anonymous_enabled=excluded.anonymous_enabled,
                voting_enabled=excluded.voting_enabled
            """,
            (
                guild_id,
                suggestion_channel_id,
                archive_channel_id,
                staff_role_id,
                int(anonymous_enabled),
                int(voting_enabled)
            )
        )

        await db.commit()