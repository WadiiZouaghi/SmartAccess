import logging
import json
import os
from datetime import datetime

class LoggerService:
    def __init__(self, log_file="data/access_logs.json"):
        self.log_file = log_file
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        # Configure the standard logger for console output
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger("Module2_Logger")

    def log_access(self, user_id, status, confidence, action):
        """Creates a structured log entry in JSON format and logs to console."""
        log_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_id": user_id,
            "status": status,
            "confidence": confidence,
            "action": action
        }
        
        # Console output
        self.logger.info(f"Access Result: {json.dumps(log_entry)}")
        
        # JSON File output (appending)
        try:
            logs = []
            if os.path.exists(self.log_file):
                with open(self.log_file, "r") as f:
                    try:
                        logs = json.load(f)
                    except json.JSONDecodeError:
                        logs = []
                        
            logs.append(log_entry)
            
            with open(self.log_file, "w") as f:
                json.dump(logs, f, indent=4)
                
        except Exception as e:
            self.logger.error(f"Error writing to JSON log: {e}")

if __name__ == "__main__":
    # Test
    logger = LoggerService()
    logger.log_access("wadii", "Authorized", 0.95, "GRANTED")
    logger.log_access("Unknown", "Unknown (Impostor)", 0.20, "DENIED")
