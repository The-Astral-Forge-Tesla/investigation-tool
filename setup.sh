#!/usr/bin/env bash
set -euo pipefail

echo "=============================================="
echo " Investigation Tool — One-Time Setup"
echo "=============================================="
echo ""

# ---------- 0. Sanity checks ----------
if ! command -v sudo >/dev/null 2>&1; then
  echo "ERROR: sudo is required to install system dependencies."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3 first."
  exit 1
fi

# ---------- 1. System dependencies ----------
echo "[1/7] Updating package lists..."
sudo apt update

echo "[2/7] Installing system dependencies..."
sudo apt install -y \
  python3 \
  python3-venv \
  python3-pip \
  python3-full \
  tesseract-ocr \
  tesseract-ocr-eng \
  poppler-utils \
  git

# ---------- 2. Verify Tesseract ----------
echo "[3/7] Verifying Tesseract OCR..."
if ! command -v tesseract >/dev/null 2>&1; then
  echo "ERROR: Tesseract failed to install."
  exit 1
fi
tesseract --version | head -n 1

# ---------- 3. Create virtual environment ----------
echo "[4/7] Creating Python virtual environment..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
else
  echo "  .venv already exists — reusing"
fi

# ---------- 4. Upgrade pip toolchain ----------
echo "[5/7] Upgrading pip tooling..."
./.venv/bin/pip install --upgrade pip setuptools wheel

# ---------- 5. Install Python dependencies ----------
if [ ! -f "requirements.txt" ]; then
  echo "ERROR: requirements.txt not found."
  exit 1
fi

echo "[6/7] Installing Python dependencies..."
./.venv/bin/pip install -r requirements.txt

# ---------- 6. Install spaCy model ----------
echo "[7/7] Installing spaCy language model..."
./.venv/bin/python -m spacy download en_core_web_sm

# ---------- 7. Create directory structure ----------
echo ""
echo "Creating project directories..."
mkdir -p \
  app \
  data/raw \
  data/extracted \
  data/index \
  data/registries

# ---------- 8. Permissions ----------
chmod -R u+rwX data || true

# ---------- DONE ----------
echo ""
echo "=============================================="
echo " Setup complete."
echo "=============================================="
echo ""
echo "Next steps:"
echo "  1. Put files into: data/raw/"
echo "  2. Run the tool:"
echo "     python run.py"
echo ""
echo "The program will auto-use the virtual environment."
echo "Open your browser at: http://localhost:8501"
echo ""
