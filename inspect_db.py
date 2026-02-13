import sqlite3

conn = sqlite3.connect('data/bot.db')
cursor = conn.cursor()

def get_columns(table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]

print("vpn_keys columns:", get_columns('vpn_keys'))
print("dns_access columns:", get_columns('dns_access'))

conn.close()
