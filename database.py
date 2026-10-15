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

        await db.execute("""
            CREATE TABLE IF NOT EXISTS suggestions (
                guild_id INTEGER NOT NULL,
                suggestion_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER,
                thread_id INTEGER,
                author_id INTEGER NOT NULL,
                anonymous INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                decided_by INTEGER,
                decided_at TEXT,
                PRIMARY KEY (guild_id, suggestion_id)
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

##Saves guild settings to the database
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

##Updates guild settings in the database
async def update_guild_settings(guild_id: int, **changes):
        
        current_settings = await get_guild_settings(guild_id)

        if current_settings is None:
             return False

        settings = dict(current_settings)
        settings.update(changes)

        await save_guild_settings(
            guild_id=guild_id,
            suggestion_channel_id=settings.get("suggestion_channel_id"),
            archive_channel_id=settings.get("archive_channel_id"),
            staff_role_id=settings.get("staff_role_id"),
            anonymous_enabled=bool(settings.get("anonymous_enabled")),
            voting_enabled=bool(settings.get("voting_enabled"))
        )
        return True

##Helper function that creates a suggestion record in the database
async def create_suggestion_record(
        guild_id: int, 
        channel_id: int,
        author_id: int,
        anonymous: bool
):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")

        async with db.execute(
            """
            SELECT COALESCE(MAX(suggestion_id), 0) + 1
            FROM suggestions
            WHERE guild_id = ?
            """,
            (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            suggestion_id = row[0]


        await db.execute(
            """
            INSERT INTO suggestions (
                guild_id,
                suggestion_id,
                channel_id,
                author_id,
                anonymous
            ) 
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                suggestion_id,
                channel_id,
                author_id,
                int(anonymous)
            )
        )
        await db.commit()

        return suggestion_id

async def update_suggestion_discord_ids(
        guild_id: int, 
        suggestion_id: int, 
        message_id: int, 
        thread_id: int
    ):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            UPDATE suggestions
            SET message_id = ?, thread_id = ?
            WHERE guild_id = ? AND suggestion_id = ?
            """,
            (
                message_id, 
                thread_id, 
                guild_id, 
                suggestion_id
            )
        )
        await db.commit()

async def get_suggestion_record(
        guild_id: int, 
        suggestion_id: int
    ):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT *
            FROM suggestions
            WHERE guild_id = ? AND suggestion_id = ?
            """,
            (
                guild_id, 
                suggestion_id
                )
        ) as cursor:
            row = await cursor.fetchone()

        return row
