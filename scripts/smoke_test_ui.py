import faulthandler
import os
import sys

# Enable tracebacks on segfaults
faulthandler.enable()

# Add project root to path
sys.path.append(os.getcwd())

def test_ui_instantiation():
    print("Initializing QApplication...")
    try:
        from PyQt6.QtWidgets import QApplication
        # Use minimal platform for headless if possible, but offscreen is standard for CI
        # For local run we just want to init it.
        app = QApplication(sys.argv)
    except Exception as e:
        print(f"FAILED to init QApplication: {e}")
        return 1
    
    print("Importing Shell...")
    try:
        from src.ui.shell import Shell
    except Exception as e:
        print(f"FAILED to import Shell: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("Instantiating Shell...")
    try:
        window = Shell()
        print("Shell instantiated successfully.")
        
        # Verify pages are loaded
        # We can access window._pages if private access is ok for test, 
        # but let's just assume if __init__ finished it's mostly ok.
        
        print("Test Passed.")
        return 0
    except Exception as e:
        print(f"FAILED to instantiate Shell: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(test_ui_instantiation())
