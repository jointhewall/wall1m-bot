import os
import asyncpg
from datetime import datetime

# Connection string will be fetched from your environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db_connection():
    """Establishes and returns an asynchronous connection to the Supabase PostgreSQL instance."""
    return await asyncpg.connect(DATABASE_URL)

async def get_user_by_id(telegram_user_id: int):
    """Retrieves user profile data from the database using their unique Telegram ID."""
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            "SELECT id, name, message, points, level, is_vip, avatar_url FROM names WHERE telegram_user_id = $1",
            telegram_user_id
        )
        if row:
            return dict(row)
        return None
    finally:
        await conn.close()

async def create_new_participant(telegram_user_id: int, name: str, message: str, avatar_url: str, invited_by: int = None):
    """
    Inserts a first-time participant into the database.
    Grants the initial 10 points for buying a slot.
    Returns the newly generated global sequential placement ID.
    """
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO names (telegram_user_id, name, message, avatar_url, points, invited_by) 
            VALUES ($1, $2, $3, $4, 10, $5) 
            RETURNING id
            """,
            telegram_user_id, name, message, avatar_url, invited_by
        )
        return row['id']
    finally:
        await conn.close()

async def add_points_to_user(telegram_user_id: int, points_to_add: int):
    """Adds a targeted amount of points to a user's balance (used for rewarding referrers)."""
    conn = await get_db_connection()
    try:
        await conn.execute(
            "UPDATE names SET points = points + $1 WHERE telegram_user_id = $2",
            points_to_add, telegram_user_id
        )
    finally:
        await conn.close()

async def upgrade_user_level(telegram_user_id: int, points_to_add: int = 30):
    """Increments the participant avatar tier level and adds 30 bonus points to leaderboard."""
    conn = await get_db_connection()
    try:
        await conn.execute(
            "UPDATE names SET level = level + 1, points = points + $1 WHERE telegram_user_id = $2",
            points_to_add, telegram_user_id
        )
    finally:
        await conn.close()

async def crown_new_king(telegram_user_id: int, points_to_add: int = 50):
    """
    Executes an atomic transaction to dethrone the old King of the Hill status 
    and transfers the VIP crown to the new user while adding 50 leaderboard points.
    """
    conn = await get_db_connection()
    async with conn.transaction():
        try:
            # Step 1: Dethrone the previous active king
            await conn.execute("UPDATE names SET is_vip = false WHERE is_vip = true")
            
            # Step 2: Set the current user as the active king and award bonus points
            await conn.execute(
                "UPDATE names SET is_vip = true, points = points + $1 WHERE telegram_user_id = $2",
                points_to_add, telegram_user_id
            )
        finally:
            await conn.close()

async def get_total_participants_count():
    """Retrieves the total number of registered rows inside the names table."""
    conn = await get_db_connection()
    try:
        count = await conn.fetchval("SELECT COUNT(*) FROM names")
        return count if count else 0
    finally:
        await conn.close()
