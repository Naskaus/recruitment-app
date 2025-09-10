import os
import sqlite3

DB_PATH = os.path.join('data', 'recruitment-dev.db')

def table_columns(conn, table):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info('{table}')")
    return [row[1] for row in cur.fetchall()]

def main():
    exists = os.path.exists(DB_PATH)
    print(f"DB exists: {exists} at {DB_PATH}")
    if not exists:
        print("Database file not found. Start the app once to initialize it.")
        return

    con = sqlite3.connect(DB_PATH)
    try:
        for table in ['agency', 'user', 'staff_profile', 'venue', 'assignment', 'performance_record', 'contract_calculations', 'agency_contract', 'agency_position']:
            try:
                cols = table_columns(con, table)
                print(f"{table} columns: {cols}")
            except sqlite3.Error as e:
                print(f"{table} error: {e}")
    finally:
        con.close()

if __name__ == '__main__':
    main()
