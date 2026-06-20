import sqlite3
import json
import os
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage, AIMessage

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "chats.db"))

def get_db_chats(tenant_id, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT c.id, c.name, c.tenant_id, c.created_at,
               COALESCE(MAX(m.created_at), c.created_at) AS last_active
        FROM chats c
        LEFT JOIN messages m ON c.id = m.chat_id
        WHERE c.tenant_id = ?
        GROUP BY c.id
        ORDER BY last_active DESC
        """,
        (tenant_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "tenant_id": r["tenant_id"], "created_at": r["last_active"]} for r in rows]

def create_db_chat(chat_id, name, tenant_id, db_path=DB_PATH):
    created_at = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chats (id, name, tenant_id, created_at) VALUES (?, ?, ?, ?)",
        (chat_id, name, tenant_id, created_at)
    )
    conn.commit()
    conn.close()
    return {"id": chat_id, "name": name, "tenant_id": tenant_id, "created_at": created_at}

def rename_db_chat(chat_id, name, tenant_id, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE chats SET name = ? WHERE id = ? AND tenant_id = ?",
        (name, chat_id, tenant_id)
    )
    conn.commit()
    success = cursor.rowcount > 0
    
    created_at = None
    if success:
        cursor.execute("SELECT created_at FROM chats WHERE id = ?", (chat_id,))
        row = cursor.fetchone()
        if row:
            created_at = row[0]
            
    conn.close()
    if not success:
        return None
    return {"id": chat_id, "name": name, "tenant_id": tenant_id, "created_at": created_at}

def delete_db_chat(chat_id, tenant_id, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute(
        "DELETE FROM chats WHERE id = ? AND tenant_id = ?",
        (chat_id, tenant_id)
    )
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success

def get_db_chat_history(chat_id, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT type, content, sources FROM messages WHERE chat_id = ? ORDER BY id ASC",
        (chat_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for r in rows:
        msg_type = r["type"]
        content = r["content"]
        sources_str = r["sources"]
        sources = json.loads(sources_str) if sources_str else []
        
        if msg_type == "human":
            history.append(HumanMessage(content=content))
        else:
            ai_msg = AIMessage(content=content)
            ai_msg.additional_kwargs["sources"] = sources
            history.append(ai_msg)
    return history

def append_db_message(chat_id, msg_type, content, sources=None, db_path=DB_PATH):
    created_at = datetime.now(timezone.utc).isoformat()
    sources_str = json.dumps(sources) if sources else None
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (chat_id, type, content, sources, created_at) VALUES (?, ?, ?, ?, ?)",
        (chat_id, msg_type, content, sources_str, created_at)
    )
    conn.commit()
    conn.close()
