import sqlite3

DB_FILE = "hospital.db"


def get_db_connection():
  conn = sqlite3.connect(DB_FILE)
  conn.row_factory = (
      sqlite3.Row
  )  # This allows accessing columns by name like a dictionary
  return conn


# Automatically create the table if it doesn't exist
def init_db():
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS patient_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_identifier TEXT NOT NULL,
            treatment TEXT NOT NULL,
            surgery TEXT NOT NULL,
            doctor TEXT NOT NULL,
            prescription TEXT NOT NULL,
            hospital_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
  conn.commit()
  conn.close()


init_db()