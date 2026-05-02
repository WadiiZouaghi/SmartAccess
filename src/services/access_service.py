import sqlite3
import datetime
import os

class AccessService:
    def __init__(self, db_name="data/access_control.db"):
        self.db_name = db_name
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_name), exist_ok=True)
        self._initialize_db()

    def _initialize_db(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Table for authorized users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                role TEXT DEFAULT 'authorized',
                added_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table for logs (Module 2 specific)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS access_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id TEXT,
                status TEXT,
                confidence REAL,
                action TEXT
            )
        ''')
        
        # Add default authorized user if table is empty
        cursor.execute("SELECT count(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO users (username, role) VALUES ('wadii', 'authorized')")
        
        conn.commit()
        conn.close()

    def check_access(self, username):
        """Returns True if user is authorized, False otherwise."""
        if username == "Unknown":
            return False
            
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE username = ?", (username.lower(),))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] == 'authorized':
            return True
        return False

    def add_user(self, username, role='authorized'):
        """Adds a new user to the database."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, role) VALUES (?, ?)", (username.lower(), role))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False
        except Exception as e:
            print(f"Error adding user: {e}")
            return False

    def get_next_user_id(self):
        """Returns the next available ID for training."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(id) FROM users")
        result = cursor.fetchone()[0]
        conn.close()
        return (result + 1) if result else 1

    def log_event(self, user_id, status, confidence, action):
        """Logs an access event to the database."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO access_logs (user_id, status, confidence, action)
            VALUES (?, ?, ?, ?)
        ''', (user_id, status, confidence, action))
        conn.commit()
        conn.close()

    def cleanup_old_logs(self, days=30):
        """GDPR: Delete logs older than X days."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM access_logs WHERE timestamp < date('now', '-' || ? || ' days')", (days,))
            count = cursor.rowcount
            conn.commit()
            conn.close()
            if count > 0:
                print(f"🧹 GDPR Cleanup: Deleted {count} old logs.")
            return True
        except Exception as e:
            print(f"Error during GDPR cleanup: {e}")
            return False

    def delete_user(self, username):
        """GDPR: Remove user from DB and dataset."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = ?", (username.lower(),))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return False
            
            user_id = row[0]
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            conn.close()
            
            # Remove images from dataset
            import glob
            dataset_path = "dataset"
            for f in glob.glob(f"{dataset_path}/{username.lower()}.{user_id}.*.jpg"):
                try:
                    os.remove(f)
                except Exception:
                    pass
            return True
        except Exception as e:
            print(f"Error deleting user: {e}")
            return False

if __name__ == "__main__":
    # Test initialization
    service = AccessService()
    print("Database initialized and 'wadii' added as authorized.")
    print(f"Access for 'wadii': {service.check_access('wadii')}")
    print(f"Access for 'Unknown': {service.check_access('Unknown')}")
