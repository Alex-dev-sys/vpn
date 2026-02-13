import shutil
import os
import logging
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)

BACKUP_DIR = "backups"
DB_FILE = "data/bot.db"
MAX_BACKUPS = 7  # Keep last 7 backups

class BackupService:
    @staticmethod
    def ensure_backup_dir():
        """Ensure backup directory exists"""
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)

    @staticmethod
    def create_backup() -> str:
        """
        Create a backup of the database
        Returns: Path to the backup file
        """
        BackupService.ensure_backup_dir()
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = f"bot_backup_{timestamp}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        try:
            # Check if db exists
            if not os.path.exists(DB_FILE):
                raise FileNotFoundError(f"Database file {DB_FILE} not found")
                
            # Copy file
            shutil.copy2(DB_FILE, backup_path)
            logger.info(f"Backup created: {backup_path}")
            
            # Cleanup old backups
            BackupService.cleanup_old_backups()
            
            return backup_path
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise

    @staticmethod
    def cleanup_old_backups():
        """Delete old backups, keeping only MAX_BACKUPS"""
        try:
            files = []
            for f in os.listdir(BACKUP_DIR):
                if f.startswith("bot_backup_") and f.endswith(".db"):
                    files.append(os.path.join(BACKUP_DIR, f))
            
            # Sort by modification time (newest first)
            files.sort(key=os.path.getmtime, reverse=True)
            
            # Delete excess files
            if len(files) > MAX_BACKUPS:
                for f in files[MAX_BACKUPS:]:
                    os.remove(f)
                    logger.info(f"Deleted old backup: {f}")
                    
        except Exception as e:
            logger.error(f"Failed to cleanup backups: {e}")

    @staticmethod
    async def send_backup_to_admins(bot):
        """Create backup and send to all admins"""
        from bot.handlers.admin import ADMIN_IDS
        from aiogram.types import FSInputFile
        
        try:
            backup_path = BackupService.create_backup()
            
            file = FSInputFile(backup_path)
            success_count = 0
            
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_document(
                        admin_id, 
                        file,
                        caption=f"📦 <b>Автоматический бэкап</b>\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                    )
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to send backup to {admin_id}: {e}")
            
            logger.info(f"Backup sent to {success_count} admins")
            return True
            
        except Exception as e:
            logger.error(f"Backup process failed: {e}")
            return False
