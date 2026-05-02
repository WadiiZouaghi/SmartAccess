import firebase_admin
from firebase_admin import credentials, firestore
from cryptography.fernet import Fernet
import os
import datetime
import base64

class CloudService:
    def __init__(self, key_path="firebase-key.json", secret_key_path="secret.key"):
        self.enabled = False
        self.secret_key_path = secret_key_path
        self._init_encryption()
        
        if os.path.exists(key_path):
            try:
                cred = credentials.Certificate(key_path)
                firebase_admin.initialize_app(cred)
                self.db = firestore.client(database_id='facial-recognition')
                self.enabled = True
                print("[OK] Firebase Cloud Service Initialized (Firestore Mode)")
            except Exception as e:
                print(f"[FAIL] Firebase Init Error: {e}")
        else:
            print("[WARN] Firebase key not found. Cloud features disabled.")

    def _init_encryption(self):
        """Initializes or loads the symmetric encryption key."""
        if not os.path.exists(self.secret_key_path):
            key = Fernet.generate_key()
            with open(self.secret_key_path, "wb") as key_file:
                key_file.write(key)
            print("[OK] New Encryption Key Generated")
        
        with open(self.secret_key_path, "rb") as key_file:
            self.fernet = Fernet(key_file.read())

    def upload_user_data(self, user_id, username, role):
        """Uploads user metadata to Firestore."""
        if not self.enabled: return False
        try:
            doc_ref = self.db.collection('users').document(str(user_id))
            doc_ref.set({
                'username': username,
                'role': role,
                'added_on': datetime.datetime.now()
            })
            return True
        except Exception as e:
            print(f"Error uploading to Firestore: {e}")
            return False

    def upload_biometric_sample(self, user_id, file_path):
        """Encrypts, encodes to Base64, and uploads to Firestore (Free Plan Bypass)."""
        if not self.enabled: return False
        try:
            filename = os.path.basename(file_path)
            # Read local file
            with open(file_path, "rb") as f:
                data = f.read()
            
            # 1. Encrypt data
            encrypted_data = self.fernet.encrypt(data)
            
            # 2. Convert to Base64 string for storage in Firestore
            b64_data = base64.b64encode(encrypted_data).decode('utf-8')
            
            # 3. Save to Firestore 'biometric_samples' collection
            # Document ID is a combination of user_id and filename to prevent collisions
            doc_id = f"{user_id}_{filename.replace('.', '_')}"
            self.db.collection('biometric_samples').document(doc_id).set({
                'user_id': user_id,
                'filename': filename,
                'data': b64_data,
                'timestamp': datetime.datetime.now()
            })
            return True
        except Exception as e:
            print(f"Error saving sample to Firestore: {e}")
            return False

    def download_and_decrypt_sample(self, user_id, filename, dest_path):
        """Downloads from Firestore, decodes, and decrypts."""
        if not self.enabled: return False
        try:
            doc_id = f"{user_id}_{filename.replace('.', '_')}"
            doc = self.db.collection('biometric_samples').document(doc_id).get()
            
            if not doc.exists:
                print(f"Sample {doc_id} not found in cloud.")
                return False
                
            b64_data = doc.to_dict().get('data')
            
            # 1. Decode Base64
            encrypted_data = base64.b64decode(b64_data)
            
            # 2. Decrypt
            decrypted_data = self.fernet.decrypt(encrypted_data)
            
            with open(dest_path, "wb") as f:
                f.write(decrypted_data)
            return True
        except Exception as e:
            print(f"Error retrieving sample from Firestore: {e}")
            return False

    def log_access_event(self, user_id, status, confidence, action):
        """Syncs an access log entry to Firestore."""
        if not self.enabled: return False
        try:
            self.db.collection('access_logs').add({
                'user_id': user_id,
                'status': status,
                'confidence': confidence,
                'action': action,
                'timestamp': datetime.datetime.now()
            })
            return True
        except Exception as e:
            print(f"Error logging to Firestore: {e}")
            return False
