"""
Database backup script
Run manually or via scheduler
"""
import os
import shutil
from datetime import datetime

# Directories
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "..", "backups")
DB_FILE = os.path.join(DATA_DIR, "bot.db")

# Config
MAX_BACKUPS = 7  # Keep last 7 days


def create_backup():
    """Create database backup"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    if not os.path.exists(DB_FILE):
        print(f"Database not found: {DB_FILE}")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"bot_backup_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    
    shutil.copy2(DB_FILE, backup_path)
    print(f"✅ Backup created: {backup_name}")
    
    # Cleanup old backups
    cleanup_old_backups()
    
    return backup_path


def cleanup_old_backups():
    """Remove old backups, keep only MAX_BACKUPS"""
    backups = sorted([
        f for f in os.listdir(BACKUP_DIR) 
        if f.startswith("bot_backup_") and f.endswith(".db")
    ], reverse=True)
    
    for old_backup in backups[MAX_BACKUPS:]:
        old_path = os.path.join(BACKUP_DIR, old_backup)
        os.remove(old_path)
        print(f"🗑 Deleted old: {old_backup}")


def list_backups():
    """List all backups"""
    if not os.path.exists(BACKUP_DIR):
        print("No backups found")
        return []
    
    backups = sorted([
        f for f in os.listdir(BACKUP_DIR)
        if f.startswith("bot_backup_") and f.endswith(".db")
    ], reverse=True)
    
    print(f"📦 Found {len(backups)} backups:")
    for b in backups:
        size = os.path.getsize(os.path.join(BACKUP_DIR, b)) / 1024
        print(f"  - {b} ({size:.1f} KB)")
    
    return backups


def restore_backup(backup_name: str):
    """Restore database from backup"""
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    
    if not os.path.exists(backup_path):
        print(f"❌ Backup not found: {backup_name}")
        return False
    
    os.makedirs(DATA_DIR, exist_ok=True)
    shutil.copy2(backup_path, DB_FILE)
    print(f"✅ Restored from: {backup_name}")
    return True


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python backup.py [create|list|restore <name>]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "create":
        create_backup()
    elif cmd == "list":
        list_backups()
    elif cmd == "restore" and len(sys.argv) > 2:
        restore_backup(sys.argv[2])
    else:
        print("Unknown command")
