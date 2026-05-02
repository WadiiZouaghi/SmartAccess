import sqlite3
import cv2
import os
import numpy as np
import mediapipe as mp
import time

class FaceService:
    def __init__(self, model_path="trainer.yml"):
        # 1. DNN Face Detector Initialization (ResNet-10 SSD)
        prototxt_path = "models/deploy.prototxt"
        caffemodel_path = "models/res10_300x300_ssd_iter_140000.caffemodel"
        
        if os.path.exists(prototxt_path) and os.path.exists(caffemodel_path):
            self.detector = cv2.dnn.readNetFromCaffe(prototxt_path, caffemodel_path)
            self.use_dnn = True
            print("[OK] DNN Face Detector Initialized")
        else:
            self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            self.use_dnn = False
            print("[WARN] DNN models not found, falling back to Haar Cascade")

        # 2. Recognizer Initialization
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.model_path = model_path
        self.load_users_from_db()
        
        if os.path.exists(self.model_path):
            self.recognizer.read(self.model_path)

        # 3. MediaPipe Face Mesh for Landmarks & Anti-Spoofing
        self.use_mesh = False
        try:
            self.mp_face_mesh = mp.solutions.face_mesh
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            self.use_mesh = True
            print("[OK] MediaPipe Face Mesh Initialized")
        except AttributeError:
            print("[WARN] MediaPipe solutions not found (Python 3.14 compatibility). Mesh disabled.")
        except Exception as e:
            print(f"[WARN] MediaPipe Mesh failed: {e}")
        
        # EAR (Eye Aspect Ratio) state for blink detection
        self.blink_counter = 0
        self.total_blinks = 0
        self.ear_threshold = 0.2
        self.consec_frames = 2

    def load_users_from_db(self, db_path="data/access_control.db"):
        """Load authorized users and roles from database."""
        try:
            if not os.path.exists(db_path):
                self.known_users = {0: "Unknown"}
                self.known_roles = {0: "impostor"}
                return
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, role FROM users")
                
            self.known_users = {0: "Unknown"}
            self.known_roles = {0: "impostor"}
            for user_id, username, role in cursor.fetchall():
                self.known_users[user_id] = username
                self.known_roles[user_id] = role
            conn.close()
            print(f"[OK] Loaded {len(self.known_users) - 1} users from database")
        except Exception as e:
            print(f"[FAIL] Error loading users: {e}")
            self.known_users = {0: "Unknown"}
            self.known_roles = {0: "impostor"}

    def detect_faces(self, frame):
        """Detect faces using DNN or Haar Cascade."""
        (h, w) = frame.shape[:2]
        
        if self.use_dnn:
            blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
            self.detector.setInput(blob)
            detections = self.detector.forward()
            
            faces = []
            for i in range(0, detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                if confidence > 0.5:
                    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                    (startX, startY, endX, endY) = box.astype("int")
                    faces.append((startX, startY, endX - startX, endY - startY))
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            return faces, gray
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 5)
            return faces, gray

    def recognize(self, gray_frame, face_rect):
        """Recognize face and return detailed result."""
        x, y, w, h = face_rect
        if x < 0 or y < 0: return None
        
        face_roi = gray_frame[max(0, y):y+h, max(0, x):x+w]
        if face_roi.size == 0: return None
        
        # Enhanced Preprocessing
        face_roi = cv2.equalizeHist(face_roi)
        face_roi = cv2.GaussianBlur(face_roi, (3, 3), 0)
        
        try:
            label, confidence = self.recognizer.predict(face_roi)
            # LBPH confidence is a distance; lower is better. 
            # We normalize it to a 0-1 scale.
            norm_confidence = max(0, 1 - (confidence / 120.0))
            
            name = self.known_users.get(label, "Unknown")
            role = self.known_roles.get(label, "impostor")
            
            # Adaptive thresholding: higher confidence needed for restricted areas
            threshold = 0.65 if role == "authorized" else 0.75
            status = "recognized" if name != "Unknown" and norm_confidence > threshold else "unknown"
            
            # LBP Texture Check (Anti-Spoofing Proxy)
            # Real skin has specific texture variance
            texture_score = np.var(face_roi) / 1000.0
            is_real_texture = texture_score > 0.5 # Simple heuristic
            
            result = {
                "name": name if status == "recognized" else "Unknown",
                "role": role if status == "recognized" else "impostor",
                "confidence": round(norm_confidence, 4),
                "status": status,
                "texture_score": round(texture_score, 2),
                "liveness": is_real_texture,
                "raw_confidence": confidence
            }
            
            result["classification"] = self.classify(result)
            return result
        except cv2.error:
            return None

    def classify(self, recognition_result):
        """Classify actor type based on database role."""
        status = recognition_result["status"]
        role = recognition_result.get("role", "impostor")
        
        if status == "unknown":
            return "Unknown (Impostor)"
        elif role == "authorized":
            return "Authorized"
        elif role == "restricted":
            return "Known but unauthorized"
        else:
            return "Unauthorized"

    def get_mesh_landmarks(self, frame):
        """Extract landmarks and perform anti-spoofing (blink detection)."""
        if not self.use_mesh:
            return None, False
            
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        try:
            results = self.face_mesh.process(rgb_frame)
            
            blinked = False
            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    # EAR calculation for anti-spoofing
                    blinked = self._check_blink(face_landmarks.landmark)
            
            return results.multi_face_landmarks, blinked
        except:
            return None, False

    def _check_blink(self, landmarks):
        """Calculate Eye Aspect Ratio (EAR) to detect real human blink."""
        # Simple EAR calculation using specific landmark indices for MediaPipe
        # Left eye: 362, 385, 387, 263, 373, 380
        # Right eye: 33, 160, 158, 133, 153, 144
        
        def get_ear(p1, p2, p3, p4, p5, p6):
            # Vertical distances
            v1 = np.linalg.norm(np.array([p2.x, p2.y]) - np.array([p6.x, p6.y]))
            v2 = np.linalg.norm(np.array([p3.x, p3.y]) - np.array([p5.x, p5.y]))
            # Horizontal distance
            h = np.linalg.norm(np.array([p1.x, p1.y]) - np.array([p4.x, p4.y]))
            return (v1 + v2) / (2.0 * h)

        # Indices for eyes (simplified selection)
        left_ear = get_ear(landmarks[362], landmarks[385], landmarks[387], landmarks[263], landmarks[373], landmarks[380])
        right_ear = get_ear(landmarks[33], landmarks[160], landmarks[158], landmarks[133], landmarks[153], landmarks[144])
        
        avg_ear = (left_ear + right_ear) / 2.0
        
        if avg_ear < self.ear_threshold:
            self.blink_counter += 1
            return False
        else:
            if self.blink_counter >= self.consec_frames:
                self.total_blinks += 1
                self.blink_counter = 0
                return True # Blink detected
            self.blink_counter = 0
            return False

    def train(self, dataset_path="dataset"):
        """Train model with enhanced preprocessing."""
        if not os.path.exists(dataset_path): return False
        face_samples = []
        ids = []
        
        for filename in os.listdir(dataset_path):
            if filename.lower().endswith((".jpg", ".png", ".jpeg")):
                path = os.path.join(dataset_path, filename)
                img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                
                try:
                    user_id = int(filename.split('.')[1])
                except: continue
                
                # Use cascade for training data extraction (legacy compatibility)
                faces = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml').detectMultiScale(img)
                for (x, y, w, h) in faces:
                    roi = cv2.equalizeHist(img[y:y+h, x:x+w])
                    roi = cv2.GaussianBlur(roi, (3, 3), 0)
                    face_samples.append(roi)
                    ids.append(user_id)
                    
        if len(face_samples) > 0:
            self.recognizer.train(face_samples, np.array(ids))
            self.recognizer.save(self.model_path)
            return True
        return False
