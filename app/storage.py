import aiosqlite
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from app.config import settings
from app.models import WebhookPayload

INIT_SCRIPT = """
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    from_msisdn TEXT NOT NULL,
    to_msisdn TEXT NOT NULL,
    ts TEXT NOT NULL,
    text TEXT,
    created_at TEXT NOT NULL
);
"""

def get_db_path():
    """
    Converts 'sqlite:////data/app.db' -> '/data/app.db'
    """
    url = settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "")
    return url

async def init_db():
    db_path = get_db_path()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(INIT_SCRIPT)
        await db.commit()

async def insert_message(payload: WebhookPayload) -> str:
    now = datetime.now(timezone.utc).isoformat()
    db_path = get_db_path() 
    
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT message_id FROM messages WHERE message_id = ?", (payload.message_id,))
        if await cursor.fetchone():
            return "duplicate"

        await db.execute(
            "INSERT INTO messages (message_id, from_msisdn, to_msisdn, ts, text, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (payload.message_id, payload.from_msisdn, payload.to_msisdn, payload.ts, payload.text, now)
        )
        await db.commit()
        return "created"

async def get_messages(
    limit: int, 
    offset: int, 
    from_msisdn: Optional[str] = None, 
    since: Optional[str] = None, 
    q: Optional[str] = None
) -> Dict[str, Any]:
    db_path = get_db_path() 
    
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        where_clauses = ["1=1"]
        params = []

        if from_msisdn:
            where_clauses.append("from_msisdn = ?")
            params.append(from_msisdn)
        
        if since:
            where_clauses.append("ts >= ?")
            params.append(since)
            
        if q:
            where_clauses.append("text LIKE ?")
            params.append(f"%{q}%")

        where_str = " AND ".join(where_clauses)

        count_query = f"SELECT COUNT(*) FROM messages WHERE {where_str}"
        cursor = await db.execute(count_query, tuple(params))
        total_count = (await cursor.fetchone())[0]

        data_query = f"""
            SELECT * FROM messages 
            WHERE {where_str}
            ORDER BY ts ASC, message_id ASC
            LIMIT ? OFFSET ?
        """
        full_params = params + [limit, offset]
        
        cursor = await db.execute(data_query, tuple(full_params))
        rows = await cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                "message_id": row["message_id"],
                "from": row["from_msisdn"],
                "to": row["to_msisdn"],
                "ts": row["ts"],
                "text": row["text"],
                "created_at": row["created_at"]
            })

        return {"data": data, "total": total_count}

async def get_stats() -> Dict[str, Any]:
    db_path = get_db_path() # Use the helper here
    
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        
        query = """
            SELECT 
                COUNT(*) as total,
                COUNT(DISTINCT from_msisdn) as senders,
                MIN(ts) as first_ts,
                MAX(ts) as last_ts
            FROM messages
        """
        cursor = await db.execute(query)
        stats = await cursor.fetchone()

        sender_query = """
            SELECT from_msisdn, COUNT(*) as count
            FROM messages
            GROUP BY from_msisdn
            ORDER BY count DESC
            LIMIT 10
        """
        cursor = await db.execute(sender_query)
        sender_rows = await cursor.fetchall()
        
        senders_list = [
            {"from": row["from_msisdn"], "count": row["count"]} 
            for row in sender_rows
        ]

        return {
            "total_messages": stats["total"],
            "senders_count": stats["senders"],
            "messages_per_sender": senders_list,
            "first_message_ts": stats["first_ts"],
            "last_message_ts": stats["last_ts"]
        }