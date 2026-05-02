import smtplib
import cv2
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

class AlertService:
    def __init__(self, smtp_server="smtp.gmail.com", port=587, 
                 sender_email=None, sender_password=None, receiver_email=None):
        self.smtp_server = smtp_server
        self.port = port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.receiver_email = receiver_email
        self.enabled = all([sender_email, sender_password, receiver_email])

    def send_alert(self, user_id, confidence, timestamp, face_image=None, is_impostor=False):
        """Sends an alert with an optional face image attachment."""
        if not self.enabled:
            return False

        if is_impostor:
            subject = f"🔴 CRITICAL ALARM: Impostor Detected!"
            prefix = "IMPOSTOR IDENTIFIED"
        else:
            subject = f"⚠️ SECURITY ALERT: Unauthorized Access ({user_id})"
            prefix = "RESTRICTED USER ATTEMPT"

        body = f"""
        {prefix}
        ------------------------------
        Identified as: {user_id}
        Confidence Score: {int(confidence * 100)}%
        Timestamp: {timestamp}
        
        Action Taken: ACCESS DENIED & IMAGE CAPTURED
        """

        message = MIMEMultipart()
        message["From"] = self.sender_email
        message["To"] = self.receiver_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        # Attach image if provided
        if face_image is not None:
            try:
                # Encode image to buffer
                _, buffer = cv2.imencode('.jpg', face_image)
                image_attachment = MIMEImage(buffer.tobytes())
                image_attachment.add_header('Content-Disposition', 'attachment', filename="intruder_face.jpg")
                message.attach(image_attachment)
            except Exception as e:
                print(f"Error attaching image: {e}")

        try:
            with smtplib.SMTP(self.smtp_server, self.port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            return True
        except Exception as e:
            print(f"Error sending email alert: {e}")
            return False

if __name__ == "__main__":
    # Test (without credentials)
    alert = AlertService()
    print(f"Alert service enabled: {alert.enabled}")
