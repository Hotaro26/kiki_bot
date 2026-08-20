import asyncpg
import logging
import os
from datetime import datetime

logger = logging.getLogger('ace_bot.database')

# Grab the database URL from Render's environment variables
DB_URL = os.getenv('DATABASE_URL')
pool = None

async def setup_db():
    global pool
    if not DB_URL:
        logger.error("DATABASE_URL is not set in environment variables!")
        return

    # Create a connection pool to Supabase
    pool = await asyncpg.create_pool(DB_URL)
    
    async with pool.acquire() as conn:
        # Create users table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                total_hours REAL DEFAULT 0.0,
                timezone TEXT DEFAULT 'UTC'
            )
        ''')
        
        # Create study sessions table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS study_sessions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                duration_hours REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        logger.info("Database tables verified.")

async def add_study_time(user_id: int, hours: float):
    """Add completed study time to a user's total."""
    if not pool: return
    async with pool.acquire() as conn:
        # Update or insert user's total hours
        await conn.execute('''
            INSERT INTO users (user_id, total_hours) 
            VALUES ($1, $2)
            ON CONFLICT(user_id) 
            DO UPDATE SET total_hours = users.total_hours + $2
        ''', user_id, hours)
        
        # Log the individual session
        await conn.execute('''
            INSERT INTO study_sessions (user_id, duration_hours)
            VALUES ($1, $2)
        ''', user_id, hours)

async def get_user_data(user_id: int):
    """Retrieve total hours and timezone for a user."""
    if not pool: return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT total_hours, timezone FROM users WHERE user_id = $1', user_id)
        if row:
            return {'total_hours': row['total_hours'], 'timezone': row['timezone']}
        return None

async def get_study_stats(user_id: int, timezone: str):
    """Calculate today and this month's study hours adjusted for the user's timezone."""
    if not pool: return 0.0, 0.0
    async with pool.acquire() as conn:
        # Today's hours
        today_query = '''
            SELECT SUM(duration_hours) as today_hours 
            FROM study_sessions 
            WHERE user_id = $1 
            AND date(timestamp AT TIME ZONE 'UTC' AT TIME ZONE $2) = date(CURRENT_TIMESTAMP AT TIME ZONE 'UTC' AT TIME ZONE $2)
        '''
        today_row = await conn.fetchrow(today_query, user_id, timezone)
        today_hours = today_row['today_hours'] if today_row and today_row['today_hours'] else 0.0
        
        # This month's hours
        month_query = '''
            SELECT SUM(duration_hours) as month_hours 
            FROM study_sessions 
            WHERE user_id = $1 
            AND date_trunc('month', timestamp AT TIME ZONE 'UTC' AT TIME ZONE $2) = date_trunc('month', CURRENT_TIMESTAMP AT TIME ZONE 'UTC' AT TIME ZONE $2)
        '''
        month_row = await conn.fetchrow(month_query, user_id, timezone)
        month_hours = month_row['month_hours'] if month_row and month_row['month_hours'] else 0.0
        
        return today_hours, month_hours

async def set_user_timezone(user_id: int, timezone: str):
    """Set the user's timezone."""
    if not pool: return
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO users (user_id, timezone) 
            VALUES ($1, $2)
            ON CONFLICT(user_id) 
            DO UPDATE SET timezone = $2
        ''', user_id, timezone)

async def get_leaderboard(period: str, limit: int = 10):
    """Get top users by study hours for a specific period (daily, weekly, alltime)."""
    if not pool: return []
    async with pool.acquire() as conn:
        if period == 'alltime':
            rows = await conn.fetch('SELECT user_id, total_hours FROM users ORDER BY total_hours DESC LIMIT $1', limit)
            return [(row['user_id'], row['total_hours']) for row in rows]
        
        elif period == 'weekly':
            query = '''
                SELECT user_id, SUM(duration_hours) as period_hours
                FROM study_sessions
                WHERE timestamp >= NOW() - INTERVAL '7 days'
                GROUP BY user_id
                ORDER BY period_hours DESC
                LIMIT $1
            '''
            rows = await conn.fetch(query, limit)
            return [(row['user_id'], row['period_hours']) for row in rows]
                
        elif period == 'daily':
            query = '''
                SELECT user_id, SUM(duration_hours) as period_hours
                FROM study_sessions
                WHERE timestamp >= NOW() - INTERVAL '1 day'
                GROUP BY user_id
                ORDER BY period_hours DESC
                LIMIT $1
            '''
            rows = await conn.fetch(query, limit)
            return [(row['user_id'], row['period_hours']) for row in rows]
            
        return []
