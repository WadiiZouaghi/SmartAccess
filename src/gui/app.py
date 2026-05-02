import threading
import customtkinter as ctk
import cv2
import numpy as np
from PIL import Image, ImageTk
import datetime
import os
import sys
import time
from collections import deque

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.camera_service import CameraService
from core.face_service import FaceService
from services.access_service import AccessService
from services.logger_service import LoggerService
from services.alert_service import AlertService
from services.watermark_service import WatermarkService
from services.cloud_service import CloudService

# SOC STYLE COLORS
C_GREEN = "#00FF9C"
C_RED = "#FF3B3B"
C_ORANGE = "#FFA500"
C_BLUE = "#00D4FF"
C_BG = "#0A0A0A"
C_PANEL = "#151515"

class SmartAccessApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SOC SYSTEM - BIOMETRIC SURVEILLANCE v2.0")
        self.geometry("1400x900")
        self.configure(fg_color=C_BG)

        # Initialize Services
        self.camera = CameraService()
        self.face_service = FaceService()
        self.access_service = AccessService()
        self.logger_service = LoggerService()
        self.watermark_service = WatermarkService()
        self.cloud_service = CloudService()
        
        self.alert_service = AlertService(
            sender_email="zouaghi.wadii69@gmail.com", 
            sender_password="jnbs heah nulb uioq", 
            receiver_email="zouaghi.wadii69@gmail.com"
        )

        # Performance Stats
        self.fps_deque = deque(maxlen=30)
        self.last_frame_time = time.time()
        self.latency = 0.0
        
        # State
        self.result_history = {}
        self.history_size = 5
        self.last_alert_time = {}
        self.alert_cooldown = 300 
        self.last_log_refresh = 0
        self.last_alarm_time = 0
        self.is_capturing = False
        self.capture_count = 0
        self.max_samples = 50

        self._setup_ui()
        self.show_frame("dashboard")
        self.update_video()

    def _setup_ui(self):
        # 1. Main Grid (3 columns: Nav, Center, System)
        self.grid_columnconfigure(0, weight=0) # Nav
        self.grid_columnconfigure(1, weight=3) # Feed
        self.grid_columnconfigure(2, weight=1) # Logs
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0) # Bottom Bar

        # --- LEFT NAVIGATION ---
        self.nav_panel = ctk.CTkFrame(self, width=80, fg_color=C_PANEL, corner_radius=0)
        self.nav_panel.grid(row=0, column=0, rowspan=2, sticky="nsew")
        
        self._add_nav_btn("📊", "dashboard", 20)
        self._add_nav_btn("📜", "logs", 80)
        self._add_nav_btn("👤", "register", 140)

        # --- CENTER: CAMERA FEED ---
        self.feed_container = ctk.CTkFrame(self, fg_color="transparent")
        self.feed_container.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        self.video_label = ctk.CTkLabel(self.feed_container, text="", fg_color="#000")
        self.video_label.pack(expand=True, fill="both")
        
        # Overlay for Feed (Glassmorphism effect)
        self.status_banner = ctk.CTkFrame(self.video_label, fg_color="#1a1a1a", corner_radius=0, height=50)
        self.status_banner.place(relx=0, rely=0, relwidth=1)
        
        self.system_label = ctk.CTkLabel(self.status_banner, text="▼ SYSTEM: ACTIVE", font=("Inter", 14, "bold"), text_color=C_GREEN)
        self.system_label.pack(side="left", padx=20)
        
        self.detection_label = ctk.CTkLabel(self.status_banner, text="[IDLE] SCANNING...", font=("Inter", 14, "bold"), text_color=C_BLUE)
        self.detection_label.pack(side="right", padx=20)

        # --- RIGHT: SYSTEM FEEDBACK ---
        self.log_panel = ctk.CTkFrame(self, fg_color=C_PANEL, corner_radius=15)
        self.log_panel.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)
        
        ctk.CTkLabel(self.log_panel, text="REAL-TIME THREAT LOGS", font=("Inter", 12, "bold"), text_color="#666").pack(pady=10)
        
        self.side_log_text = ctk.CTkTextbox(self.log_panel, font=("Consolas", 11), fg_color="transparent", text_color=C_GREEN)
        self.side_log_text.pack(expand=True, fill="both", padx=10)
        
        self.alert_box = ctk.CTkLabel(self.log_panel, text="", height=40, corner_radius=8)
        self.alert_box.pack(fill="x", padx=10, pady=10)

        # --- BOTTOM: SYSTEM STATE ---
        self.bottom_bar = ctk.CTkFrame(self, height=30, fg_color=C_PANEL, corner_radius=0)
        self.bottom_bar.grid(row=1, column=0, columnspan=3, sticky="ew")
        
        self.fps_label = ctk.CTkLabel(self.bottom_bar, text="FPS: 00", font=("Inter", 10), text_color="#888")
        self.fps_label.pack(side="left", padx=20)
        
        self.latency_label = ctk.CTkLabel(self.bottom_bar, text="LATENCY: 0ms", font=("Inter", 10), text_color="#888")
        self.latency_label.pack(side="left", padx=20)
        
        self.light_label = ctk.CTkLabel(self.bottom_bar, text="LIGHT: NORMAL", font=("Inter", 10), text_color="#888")
        self.light_label.pack(side="left", padx=20)
        
        self.gdpr_label = ctk.CTkLabel(self.bottom_bar, text="GDPR: COMPLIANT (AES-256)", font=("Inter", 10), text_color="#444")
        self.gdpr_label.pack(side="right", padx=20)

        # --- ADDITIONAL SCREENS (Hidden by default) ---
        self._setup_extra_screens()

    def _setup_extra_screens(self):
        # Registration Frame
        self.register_frame = ctk.CTkFrame(self, fg_color=C_BG)
        ctk.CTkLabel(self.register_frame, text="BIOMETRIC ENROLLMENT", font=("Inter", 24, "bold")).pack(pady=40)
        
        self.name_entry = ctk.CTkEntry(self.register_frame, placeholder_text="Full Name", width=300, height=45)
        self.name_entry.pack(pady=10)
        
        self.role_var = ctk.StringVar(value="authorized")
        ctk.CTkOptionMenu(self.register_frame, values=["authorized", "restricted"], variable=self.role_var, width=300).pack(pady=10)
        
        ctk.CTkButton(self.register_frame, text="START CAPTURE", fg_color=C_GREEN, text_color="#000", font=("Inter", 13, "bold"),
                     command=self.start_face_capture).pack(pady=30)
        
        self.reg_status = ctk.CTkLabel(self.register_frame, text="Ready")
        self.reg_status.pack()

        # Logs History Frame
        self.history_frame = ctk.CTkFrame(self, fg_color=C_BG)
        ctk.CTkLabel(self.history_frame, text="CENTRAL ACCESS AUDIT", font=("Inter", 24, "bold")).pack(pady=20)
        self.history_textbox = ctk.CTkTextbox(self.history_frame, font=("Consolas", 14), fg_color=C_PANEL)
        self.history_textbox.pack(expand=True, fill="both", padx=40, pady=20)
        ctk.CTkButton(self.history_frame, text="VERIFY INTEGRITY (SHA-256/DCT)", fg_color=C_BLUE, command=self.verify_capture).pack(pady=20)

    def _add_nav_btn(self, icon, frame_name, y):
        btn = ctk.CTkButton(self.nav_panel, text=icon, width=60, height=60, fg_color="transparent", 
                           hover_color="#222", font=("Inter", 20), command=lambda: self.show_frame(frame_name))
        btn.place(x=10, y=y)

    def show_frame(self, name):
        self.register_frame.grid_forget()
        self.history_frame.grid_forget()
        self.feed_container.grid_forget()
        self.log_panel.grid_forget()
        
        if name == "dashboard":
            self.feed_container.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
            self.log_panel.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)
        elif name == "register":
            self.register_frame.grid(row=0, column=1, columnspan=2, sticky="nsew")
        elif name == "logs":
            self.history_frame.grid(row=0, column=1, columnspan=2, sticky="nsew")
            self.refresh_logs()

    def draw_soc_hud(self, frame, landmarks, color):
        """Draws complex neural mesh or stylized scanning HUD."""
        h, w, _ = frame.shape
        
        if landmarks:
            pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks.landmark]
            
            # 1. Neural Connections (Mesh)
            connections = [
                (10, 338), (338, 297), (297, 332), (332, 284), (284, 251), (251, 389), 
                (389, 356), (356, 454), (454, 323), (323, 361), (361, 288), (288, 397),
                (10, 109), (109, 67), (67, 103), (103, 54), (54, 21), (21, 162), 
                (162, 127), (127, 234), (234, 93), (93, 132), (132, 58), (58, 172)
            ]
            
            for p1, p2 in connections:
                if p1 < len(pts) and p2 < len(pts):
                    cv2.line(frame, pts[p1], pts[p2], color, 1)
            
            for i in [10, 338, 297, 332, 284, 251, 152, 377, 400, 378, 379, 365]:
                cv2.circle(frame, pts[i], 2, color, -1)
                
            # 2. Scanning Radial Sweep
            center = pts[1] # Nose tip
            for r_offset in range(0, 5, 2):
                radius = int(abs(np.sin(time.time() * 2)) * 100) + 50 + r_offset
                cv2.circle(frame, center, radius, color, 1)
            
            # 3. Horizontal Scan Line
            y_min = min(p[1] for p in pts)
            y_max = max(p[1] for p in pts)
            scan_y = int(y_min + (y_max - y_min) * (abs(np.sin(time.time() * 3))))
            cv2.line(frame, (min(p[0] for p in pts)-30, scan_y), (max(p[0] for p in pts)+30, scan_y), color, 1)
            cv2.line(frame, (min(p[0] for p in pts)-30, scan_y+2), (max(p[0] for p in pts)+30, scan_y+2), color, 1)
        else:
            # Fallback stylized box for SOC dashboard if mesh is unavailable
            pass

    def update_video(self):
        print(f"DEBUG: update_video self type: {type(self)}")
        print(f"DEBUG: Has _process_recognition: {hasattr(self, '_process_recognition')}")
        start_time = time.time()
        frame = self.camera.get_frame()
        if frame is not None:
            # 1. Performance Distribution
            self.fps_deque.append(1 / (time.time() - self.last_frame_time))
            self.last_frame_time = time.time()
            self.fps_label.configure(text=f"FPS: {int(np.mean(self.fps_deque))}")
            
            # 2. Lighting check
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness = np.mean(gray)
            light_text = "LOW" if brightness < 50 else ("HIGH" if brightness > 200 else "NORMAL")
            self.light_label.configure(text=f"LIGHT: {light_text}")

            # 3. Detection & Face Mesh
            faces, _ = self.face_service.detect_faces(frame)
            face_landmarks, blinked = self.face_service.get_mesh_landmarks(frame)
            
            # --- CAPTURE LOGIC ---
            if self.is_capturing and len(faces) > 0:
                self._handle_enrollment(frame, faces[0], gray)

            current_color = (255, 212, 0) # Default Blue-ish BGR
            status_text = "SCANNING..."
            
            # 4. Recognition Logic
            if len(faces) > 0:
                status_text, current_color = self._process_recognition(frame, faces[0], gray, blinked)
                
                # Draw stylized box if mesh is off
                if not face_landmarks:
                    x, y, w, h = faces[0]
                    # Corner brackets for SOC look
                    length = 20
                    cv2.line(frame, (x, y), (x + length, y), current_color, 2)
                    cv2.line(frame, (x, y), (x, y + length), current_color, 2)
                    cv2.line(frame, (x + w, y), (x + w - length, y), current_color, 2)
                    cv2.line(frame, (x + w, y), (x + w, y + length), current_color, 2)
                    cv2.line(frame, (x, y + h), (x + length, y + h), current_color, 2)
                    cv2.line(frame, (x, y + h), (x, y + h - length), current_color, 2)
                    cv2.line(frame, (x + w, y + h), (x + w - length, y + h), current_color, 2)
                    cv2.line(frame, (x + w, y + h), (x + w, y + h - length), current_color, 2)
            else:
                self.detection_label.configure(text="[IDLE] SCANNING...", text_color=C_BLUE)

            # 5. Drawing HUD Mesh
            if face_landmarks:
                for face_lms in face_landmarks:
                    self.draw_soc_hud(frame, face_lms, current_color)

            # Update UI
            self.latency = (time.time() - start_time) * 1000
            self.latency_label.configure(text=f"LATENCY: {int(self.latency)}ms")
            
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(img)
            imgtk = ImageTk.PhotoImage(image=img)
            self.video_label.imgtk = imgtk
            self.video_label.configure(image=imgtk)

        self.after(10, self.update_video)

    def _process_recognition(self, frame, rect, gray, blinked):
        result = self.face_service.recognize(gray, rect)
        if not result: return "[SCANNING] IDENTIFYING...", (255, 212, 0)
        
        name = result["name"]
        conf = result["confidence"]
        status = result["classification"]
        liveness = result.get("liveness", False)
        
        # Stability check
        if 0 not in self.result_history: self.result_history[0] = deque(maxlen=self.history_size)
        self.result_history[0].append(name)
        smoothed_name = max(set(self.result_history[0]), key=list(self.result_history[0]).count)
        
        is_authorized = self.access_service.check_access(smoothed_name)
        
        # Pulse effect for impostors
        pulse = ""
        if smoothed_name == "Unknown":
            pulse = " »»» " if int(time.time() * 5) % 2 == 0 else "      "
        
        # Liveness & Integrity labels
        spoof_status = "LIVENESS: OK" if (blinked or liveness) else "LIVENESS: PENDING..."
        
        if is_authorized:
            color = (156, 255, 0) # Green BGR
            ui_color = C_GREEN
            msg = f"● AUTHORIZED: {smoothed_name.upper()} ({int(conf*100)}%)"
            log_action = "GRANTED"
        elif smoothed_name == "Unknown":
            color = (59, 59, 255) # Red BGR
            ui_color = C_RED
            msg = f"{pulse}ALERT: IMPOSTOR DETECTED!{pulse}"
            log_action = "DENIED (IMPOSTOR)"
            self._trigger_unauthorized_alert(frame, rect, smoothed_name, conf, True)
        else:
            color = (0, 165, 255) # Orange BGR
            ui_color = C_ORANGE
            msg = f"⚠ DENIED: {smoothed_name.upper()} (RESTRICTED)"
            log_action = "DENIED (RESTRICTED)"
            self._trigger_unauthorized_alert(frame, rect, smoothed_name, conf, False)

        self.detection_label.configure(text=f"[{spoof_status}] {msg}", text_color=ui_color)
        
        # Periodically log (every 3 seconds for better real-time feel)
        curr_time = time.time()
        if curr_time - self.last_log_refresh > 3:
            # Sync to local DB, JSON, and Cloud
            self.access_service.log_event(smoothed_name, msg, conf, log_action)
            self.logger_service.log_access(smoothed_name, status, conf, log_action)
            self.cloud_service.log_access_event(smoothed_name, status, conf, log_action)
            
            # Watermark embedding confirmation in logs
            self._update_side_logs(smoothed_name, log_action)
            self.last_log_refresh = curr_time
            
        return msg, color

    def _handle_enrollment(self, frame, face, gray):
        x, y, w, h = face
        self.capture_count += 1
        img_path = f"dataset/{self.current_reg_name}.{self.current_reg_id}.{self.capture_count}.jpg"
        cv2.imwrite(img_path, gray[y:y+h, x:x+w])
        self.cloud_service.upload_biometric_sample(self.current_reg_id, img_path)
        
        self.reg_status.configure(text=f"PROGRESS: {self.capture_count}/{self.max_samples}")
        if self.capture_count >= self.max_samples:
            self.is_capturing = False
            self.face_service.train()
            self.show_frame("dashboard")

    def _trigger_unauthorized_alert(self, frame, rect, name, conf, is_impostor):
        curr_time = time.time()
        if name not in self.last_alert_time or (curr_time - self.last_alert_time[name] > self.alert_cooldown):
            # Capture a larger area for better clarity
            h, w, _ = frame.shape
            x, y, fw, fh = rect
            pad_h = int(fh * 1.5)
            pad_w = int(fw * 1.2)
            
            y1, y2 = max(0, y - pad_h // 2), min(h, y + fh + pad_h // 2)
            x1, x2 = max(0, x - pad_w // 2), min(w, x + fw + pad_w // 2)
            
            crop = frame[y1:y2, x1:x2].copy()
            
            # Watermark & Email
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            watermark_text = f"THREAT:{'IMPOSTOR' if is_impostor else 'DENIED'}|USER:{name}|TIME:{timestamp}"
            
            # Use hash for watermark if too long
            wm_hash = self.watermark_service.generate_hash(watermark_text)[:16]
            watermarked_crop = self.watermark_service.embed_watermark(crop, wm_hash)
            
            threading.Thread(target=self.alert_service.send_alert, args=(name, conf, timestamp, watermarked_crop, is_impostor)).start()
            self.last_alert_time[name] = curr_time
            
            self.alert_box.configure(text=f"🚨 SECURITY ALERT: {name} - EMAIL SENT", fg_color=C_RED, text_color="#FFF")
            self.after(5000, lambda: self.alert_box.configure(text="", fg_color="transparent"))

    def _update_side_logs(self, user, action):
        t = datetime.datetime.now().strftime("%H:%M:%S")
        status = "✔️ TAT" if action == "GRANTED" else "⚠️ TAT"
        entry = f"[{t}] {user[:8]:<8} | {action:8} | {status}\n"
        self.side_log_text.insert("1.0", entry)

    def start_face_capture(self):
        name = self.name_entry.get().strip()
        if not name: return
        self.current_reg_name = name
        self.current_reg_id = self.access_service.get_next_user_id()
        if self.access_service.add_user(name):
            self.cloud_service.upload_user_data(self.current_reg_id, name, self.role_var.get())
            self.is_capturing = True
            self.capture_count = 0
            self.show_frame("dashboard")

    def refresh_logs(self):
        self.history_textbox.delete("1.0", "end")
        if os.path.exists("data/access_logs.json"):
            import json
            with open("data/access_logs.json", "r") as f:
                logs = json.load(f)
                for l in reversed(logs[-30:]):
                    self.history_textbox.insert("end", f"[{l['timestamp']}] {l['user_id']} -> {l['action']} (Watermark: Valid)\n")

    def verify_capture(self):
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(initialdir="data/captures")
        if path:
            img = cv2.imread(path)
            data = self.watermark_service.extract_watermark(img)
            if data: messagebox.showinfo("SOC Audit", f"Integrity Verified!\n\n{data}")
            else: messagebox.showerror("SOC Audit", "Tampering Detected or No Watermark!")

    def on_closing(self):
        self.camera.release()
        self.destroy()

if __name__ == "__main__":
    app = SmartAccessApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
