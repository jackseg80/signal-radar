import sqlite3

def check():
    conn = sqlite3.connect('data/signal_radar.db')
    conn.row_factory = sqlite3.Row
    cur = conn.execute("SELECT strategy, symbol, verdict FROM validations WHERE verdict='VALIDATED'")
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        print(r)
    conn.close()

if __name__ == "__main__":
    check()
