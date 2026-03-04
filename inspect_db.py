import sqlite3

def inspect():
    conn = sqlite3.connect('data/signal_radar.db')
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"Tables: {tables}")
    
    for table in tables:
        print(f"\nTable: {table}")
        cur = conn.execute(f"PRAGMA table_info({table})")
        columns = [r[1] for r in cur.fetchall()]
        print(f"Columns: {columns}")
        
        # Check first row for samples
        try:
            cur = conn.execute(f"SELECT * FROM {table} LIMIT 1")
            row = cur.fetchone()
            if row:
                print(f"Sample row: {row}")
        except:
            pass
    conn.close()

if __name__ == "__main__":
    inspect()
