import os
import asyncpg
from datetime import datetime, date

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
            """SELECT id, name, message, points, level, is_vip, avatar_url,
                      referral_count, purchase_count, last_checkin, bonus_500_claimed
               FROM names WHERE telegram_user_id = $1""",
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
            INSERT INTO names (telegram_user_id, name, message, avatar_url, points, invited_by, purchase_count)
            VALUES ($1, $2, $3, $4, 10, $5, 1)
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


async def register_referral(telegram_user_id: int, referral_points: int = 50, milestone_bonus: int = 500, milestone_count: int = 10):
    """
    Increments the referrer's referral_count, adds standard referral points,
    and grants a one-time milestone bonus once the referral count reaches `milestone_count`.
    Returns a dict: {"referral_count": int, "milestone_hit": bool}
    """
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            """
            UPDATE names
            SET referral_count = referral_count + 1,
                points = points + $1
            WHERE telegram_user_id = $2
            RETURNING referral_count, bonus_500_claimed
            """,
            referral_points, telegram_user_id
        )
        if not row:
            return {"referral_count": 0, "milestone_hit": False}

        milestone_hit = False
        if row["referral_count"] >= milestone_count and not row["bonus_500_claimed"]:
            await conn.execute(
                """
                UPDATE names
                SET points = points + $1, bonus_500_claimed = true
                WHERE telegram_user_id = $2
                """,
                milestone_bonus, telegram_user_id
            )
            milestone_hit = True

        return {"referral_count": row["referral_count"], "milestone_hit": milestone_hit}
    finally:
        await conn.close()


async def upgrade_user_level(telegram_user_id: int):
    """
    Increments the participant avatar tier level after a repeat 'Level Up' purchase.
    Each subsequent purchase grants more points than the last (simple LTV mechanic):
    purchase #2 -> +30, purchase #3 -> +40, purchase #4 -> +50, etc.
    Returns a dict: {"level": int, "points_awarded": int, "purchase_count": int}
    """
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            "SELECT purchase_count FROM names WHERE telegram_user_id = $1",
            telegram_user_id
        )
        current_purchase_count = row["purchase_count"] if row else 1
        new_purchase_count = current_purchase_count + 1
        points_awarded = 20 + (new_purchase_count * 10)  # 2nd purchase -> 40, 3rd -> 50, etc.

        updated = await conn.fetchrow(
            """
            UPDATE names
            SET level = level + 1,
                points = points + $1,
                purchase_count = $2
            WHERE telegram_user_id = $3
            RETURNING level, purchase_count
            """,
            points_awarded, new_purchase_count, telegram_user_id
        )
        return {
            "level": updated["level"],
            "points_awarded": points_awarded,
            "purchase_count": updated["purchase_count"]
        }
    finally:
        await conn.close()


async def crown_new_king(telegram_user_id: int, points_to_add: int = 50):
    """
    Executes an atomic transaction to dethrone the old King of the Hill status
    and transfers the VIP crown to the new user while adding 50 leaderboard points.
    """
    conn = await get_db_connection()
    try:
        async with conn.transaction():
            # Step 1: Dethrone the previous active king
            await conn.execute("UPDATE names SET is_vip = false WHERE is_vip = true")

            # Step 2: Set the current user as the active king and award bonus points
            await conn.execute(
                "UPDATE names SET is_vip = true, points = points + $1 WHERE telegram_user_id = $2",
                points_to_add, telegram_user_id
            )
    finally:
        await conn.close()


async def get_current_king():
    """Returns the current King of the Hill (is_vip = true), or None if no one holds the crown."""
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow("SELECT name, telegram_user_id FROM names WHERE is_vip = true LIMIT 1")
        return dict(row) if row else None
    finally:
        await conn.close()


async def try_daily_checkin(telegram_user_id: int) -> bool:
    """
    Awards +1 point for a daily check-in, once per calendar day (UTC).
    Returns True if the check-in was newly awarded, False if already claimed today.
    """
    conn = await get_db_connection()
    try:
        today = date.today()
        row = await conn.fetchrow(
            "SELECT last_checkin FROM names WHERE telegram_user_id = $1",
            telegram_user_id
        )
        if not row:
            return False

        if row["last_checkin"] == today:
            return False  # Already checked in today

        await conn.execute(
            "UPDATE names SET points = points + 1, last_checkin = $1 WHERE telegram_user_id = $2",
            today, telegram_user_id
        )
        return True
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


async def get_user_rank(telegram_user_id: int):
    """
    Returns the user's current 1-based rank across ALL participants, ordered the
    same way as the public leaderboard (points DESC, then earliest registration first).
    Returns None if the user isn't found.
    """
    conn = await get_db_connection()
    try:
        rank = await conn.fetchval(
            """
            SELECT rank FROM (
                SELECT telegram_user_id,
                       RANK() OVER (ORDER BY points DESC, created_at ASC) AS rank
                FROM names
            ) ranked
            WHERE telegram_user_id = $1
            """,
            telegram_user_id
        )
        return rank
    finally:
        await conn.close()


async def get_top_leaderboard(limit: int = 10):
    """Returns the top N participants ordered by points, for the /leaderboard command."""
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            "SELECT name, points, level, is_vip FROM names ORDER BY points DESC, created_at ASC LIMIT $1",
            limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()
