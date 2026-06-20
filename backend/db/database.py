import sqlite3
import json
import os
import sys

# Ensure this directory is in path if needed by legacy scripts
if os.path.dirname(__file__) not in sys.path:
    sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "chats.db"))

def db_migrate_legacy_data(db_path=DB_PATH):
    CHATS_METADATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chats.json")
    DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app_data")
    
    if not os.path.exists(CHATS_METADATA_FILE):
        return
        
    print("Found legacy chats.json. Starting migration to SQLite...")
    try:
        with open(CHATS_METADATA_FILE, "r") as f:
            chats = json.load(f)
    except Exception as e:
        print(f"Error loading chats.json for migration: {e}")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    migrated_count = 0
    for chat_id, chat_info in chats.items():
        name = chat_info.get("name", "New Scroll")
        tenant_id = chat_info.get("tenant_id")
        if not tenant_id:
            continue
            
        created_at = chat_info.get("created_at")
        if not created_at:
            hist_path = os.path.join(DATA_DIR, tenant_id, "chats", chat_id, "history.json")
            if os.path.exists(hist_path):
                mtime = os.path.getmtime(hist_path)
                created_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
            else:
                created_at = datetime.now(timezone.utc).isoformat()
                
        # Check if chat already exists in DB
        cursor.execute("SELECT id FROM chats WHERE id = ?", (chat_id,))
        if cursor.fetchone():
            continue
            
        # Insert chat
        cursor.execute(
            "INSERT INTO chats (id, name, tenant_id, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, name, tenant_id, created_at)
        )
        
        # Load history
        hist_path = os.path.join(DATA_DIR, tenant_id, "chats", chat_id, "history.json")
        if os.path.exists(hist_path):
            try:
                with open(hist_path, "r") as f:
                    history_data = json.load(f)
                for msg in history_data:
                    msg_type = msg.get("type", "human")
                    content = msg.get("content", "")
                    sources = msg.get("sources")
                    sources_str = json.dumps(sources) if sources else None
                    cursor.execute(
                        "INSERT INTO messages (chat_id, type, content, sources, created_at) VALUES (?, ?, ?, ?, ?)",
                        (chat_id, msg_type, content, sources_str, created_at)
                    )
            except Exception as e:
                print(f"Error migrating history for chat {chat_id}: {e}")
        migrated_count += 1
                
    conn.commit()
    conn.close()
    print(f"Successfully migrated {migrated_count} chat records to SQLite.")
    
    # Backup chats.json
    try:
        os.rename(CHATS_METADATA_FILE, CHATS_METADATA_FILE + ".bak")
        print("Renamed chats.json to chats.json.bak")
    except Exception as e:
        print(f"Error backing up chats.json: {e}")
        
    # Clean up app_data tenant chats directory (only the chats folder)
    if os.path.exists(DATA_DIR):
        import shutil
        for tenant_dir in os.listdir(DATA_DIR):
            chats_dir = os.path.join(DATA_DIR, tenant_dir, "chats")
            if os.path.exists(chats_dir):
                try:
                    shutil.rmtree(chats_dir)
                    print(f"Removed legacy chat folder: {chats_dir}")
                except Exception as e:
                    print(f"Error removing {chats_dir}: {e}")

def init_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            sources TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (chat_id) REFERENCES chats (id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

    # Apply any pending SQL migrations (users, subjects, sources, …)
    try:
        from db.migrate import run_migrations
        run_migrations(db_path)
    except Exception as exc:
        print(f"[database] WARNING: migration runner failed: {exc}")

    # Seed the database
    try:
        from db.seed import seed as run_seed, seed_students as run_seed_students
        run_seed()
        run_seed_students()
    except Exception as exc:
        print(f"[database] WARNING: seeding failed: {exc}")

    # Run data migration from legacy JSON structure
    db_migrate_legacy_data(db_path)
