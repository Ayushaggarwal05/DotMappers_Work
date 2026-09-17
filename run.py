import subprocess
import sys
import time
import os

def run_services():
    """Launch FastAPI backend and Streamlit frontend concurrently."""
    print("🚀 Starting SupportLens AI Backend (FastAPI)...")
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
    )

    # Allow backend to initialize database & auto-ingest dataset
    time.sleep(2)

    print("🌐 Starting SupportLens AI Frontend (Streamlit)...")
    frontend_proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "frontend/app.py", "--server.port", "8501", "--server.headless", "true"]
    )

    try:
        backend_proc.wait()
        frontend_proc.wait()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down SupportLens AI...")
        backend_proc.terminate()
        frontend_proc.terminate()

if __name__ == "__main__":
    run_services()
