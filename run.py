import sys
import os

# Add src to python path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from gui.app import SmartAccessApp

if __name__ == "__main__":
    print("Starting Smart Access Biometric System...")
    app = SmartAccessApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
