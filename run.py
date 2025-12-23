import os
import sys
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
RAW = DATA / "raw"
EXTRACTED = DATA / "extracted"
INDEX = DATA / "index"
REGISTRIES = DATA / "registries"
DB_PATH = INDEX / "forensic.db"

def check_python():
    if sys.version_info < (3, 10):
        print("ERROR: Python 3.10+ required.")
        sys.exit(1)

def check_venv():
    # allow auto-run if user forgets to activate venv
    venv_py = BASE / ".venv" / "bin" / "python"
    if sys.prefix == sys.base_prefix:
        if venv_py.exists():
            os.execv(str(venv_py), [str(venv_py)] + sys.argv)
        print("ERROR: Virtual environment not active and .venv not found.")
        print("Run setup.sh first.")
        sys.exit(1)

def check_tesseract():
    try:
        subprocess.run(["tesseract", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except FileNotFoundError:
        print("ERROR: Tesseract OCR not installed.")
        print("Install with:")
        print("  sudo apt install -y tesseract-ocr tesseract-ocr-eng")
        sys.exit(1)
    except subprocess.CalledProcessError:
        print("ERROR: Tesseract exists but failed to run.")
        sys.exit(1)

def ensure_dirs():
    for d in (RAW, EXTRACTED, INDEX, REGISTRIES):
        d.mkdir(parents=True, exist_ok=True)

def init_db():
    from app.db import init_db
    init_db(DB_PATH)
    try:
        os.chmod(DB_PATH, 0o600)
    except Exception:
        pass

def ingest_prompt() -> bool:
    ans = input("Ingest files from data/raw now? [Y/n]: ").strip().lower()
    return ans != "n"

def launch_ui():
    print("Launching UI at http://localhost:8501")
    subprocess.run(["streamlit", "run", "app/ui.py"], check=False)

if __name__ == "__main__":
    check_python()
    check_venv()
    check_tesseract()
    ensure_dirs()
    init_db()

    if ingest_prompt():
        from app.ingest import ingest_all
        ingest_all(raw_dir=RAW, db_path=DB_PATH)

    launch_ui()
