import aiosqlite
import logging
from datetime import datetime
import pytz

logger = logging.getLogger('kiki_bot.database')

DB_NAME = 'kiki.db'

async def setup_db():
    """Create the necessary tables if they don't exist."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                total_hours REAL DEFAULT 0.0,
                goal_hours REAL DEFAULT 0.0,
                goal_period TEXT DEFAULT 'weekly',
                timezone TEXT DEFAULT 'UTC'
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS study_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                duration_hours REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        try:
            await db.execute('ALTER TABLE users ADD COLUMN timezone TEXT DEFAULT "UTC"')
        except aiosqlite.OperationalError:
            pass # Column already exists
        await db.commit()
    logger.info("Database tables verified.")

async def add_study_time(user_id: int, hours: float):
    """Add study time to a user's total and log the session."""
    async with aiosqlite.connect(DB_NAME) as db:
        # Update overall total
        await db.execute('''
            INSERT INTO users (user_id, total_hours) 
            VALUES (?, ?)
            ON CONFLICT(user_id) 
            DO UPDATE SET total_hours = total_hours + ?
        ''', (user_id, hours, hours))
        # Log session
        await db.execute('''
            INSERT INTO study_sessions (user_id, duration_hours)
            VALUES (?, ?)
        ''', (user_id, hours))
        await db.commit()

async def get_user_data(user_id: int):
    """Retrieve user data."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT total_hours, goal_hours, goal_period, timezone FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"total_hours": row[0], "goal_hours": row[1], "goal_period": row[2], "timezone": row[3]}
            return None

async def get_study_stats(user_id: int, tz_name: str):
    """Calculate daily and monthly stats based on the user's timezone."""
    try:
        user_tz = pytz.timezone(tz_name)
    except:
        user_tz = pytz.timezone('UTC')

    now_utc = datetime.now(pytz.utc)
    now_local = now_utc.astimezone(user_tz)
    
    today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
    month_start = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc)

    today_hours = 0.0
    month_hours = 0.0

    async with aiosqlite.connect(DB_NAME) as db:
        # We fetch all sessions for the user and filter in Python for accuracy with timezones
        async with db.execute('SELECT duration_hours, timestamp FROM study_sessions WHERE user_id = ?', (user_id,)) as cursor:
            async for row in cursor:
                duration = row[0]
                # SQLite CURRENT_TIMESTAMP is UTC
                session_time = datetime.strptime(row[1], '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.utc)
                
                if session_time >= month_start:
                    month_hours += duration
                if session_time >= today_start:
                    today_hours += duration

    return today_hours, month_hours

async def set_user_timezone(user_id: int, timezone: str):
    """Set the user's timezone."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT INTO users (user_id, timezone) 
            VALUES (?, ?)
            ON CONFLICT(user_id) 
            DO UPDATE SET timezone = ?
        ''', (user_id, timezone, timezone))
        await db.commit()

async def get_leaderboard(period: str, limit: int = 10):
    """Get top users by study hours for a specific period (daily, weekly, alltime)."""
    async with aiosqlite.connect(DB_NAME) as db:
        if period == 'alltime':
            async with db.execute('SELECT user_id, total_hours FROM users ORDER BY total_hours DESC LIMIT ?', (limit,)) as cursor:
                return await cursor.fetchall()
        
        elif period == 'weekly':
            # Last 7 days rolling
            query = '''
                SELECT user_id, SUM(duration_hours) as period_hours
                FROM study_sessions
                WHERE timestamp >= datetime('now', '-7 days')
                GROUP BY user_id
                ORDER BY period_hours DESC
                LIMIT ?
            '''
            async with db.execute(query, (limit,)) as cursor:
                return await cursor.fetchall()
                
        elif period == 'daily':
            # Last 24 hours rolling
            query = '''
                SELECT user_id, SUM(duration_hours) as period_hours
                FROM study_sessions
                WHERE timestamp >= datetime('now', '-1 day')
                GROUP BY user_id
                ORDER BY period_hours DESC
                LIMIT ?
            '''
            async with db.execute(query, (limit,)) as cursor:
                return await cursor.fetchall()
        return []
