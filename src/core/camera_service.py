import cv2

class CameraService:
    def __init__(self, camera_index=0, use_mock=False):
        self.use_mock = use_mock
        if not use_mock:
            self.camera = cv2.VideoCapture(camera_index)
            if not self.camera.isOpened():
                print("Warning: Could not open camera. Falling back to mock mode.")
                self.use_mock = True
        
        if self.use_mock:
            self.camera = None
            print("CameraService: Running in MOCK mode.")

    def get_frame(self):
        if self.use_mock:
            # Return a black frame with some text
            import numpy as np
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "MOCK CAMERA MODE", (150, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            return frame

        ret, frame = self.camera.read()
        if not ret:
            return None
        return frame

    def release(self):
        if self.camera:
            self.camera.release()

if __name__ == "__main__":
    service = CameraService()
    while True:
        frame = service.get_frame()
        if frame is not None:
            cv2.imshow("Module 1 - Camera Service", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    service.release()
    cv2.destroyAllWindows()
