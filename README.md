# Investigation Tool (Forensic Browser)
A public-facing, offline-first forensic document search tool for rapid analysis of large data drops.

## Project Philosophy (Internal, Non-Negotiable)

**This project does not accuse.
It does not identify faces.
It does not declare guilt.

It exposes structures, documents patterns, and removes ambiguity.
Conclusions are left to the observer.**

This tool:
- Ingests PDFs, text files, and images (OCR)
- Builds a fast keyword index (SQLite FTS5)
- Extracts entities (people, orgs, places, dates)
- Lets users search by keyword or by entity
- Keeps results traceable to source filename + page number

No cloud. No accounts. No AI hallucinations. Everything is verifiable.

---

## Supported File Types
- PDF: `.pdf` (page-aware)
- Text: `.txt`, `.md`, `.log`
- Images (OCR): `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp`

---

## Platform
- Ubuntu Linux (native)
- Windows via WSL (recommended)

---

## System Dependencies (Ubuntu / WSL)

```bash
sudo apt update
sudo apt install -y \
  python3 \
  python3-venv \
  python3-pip \
  python3-full \
  tesseract-ocr \
  tesseract-ocr-eng \
  poppler-utils



## Running the Application

This project uses **Streamlit** for the UI. Due to how Streamlit executes scripts, the project root must be on `PYTHONPATH` for imports to resolve correctly.

### Prerequisites
- Python 3.10+
- Virtual environment activated
- Dependencies installed (`pip install -r requirements.txt`)

### Run the Streamlit UI (Correct Way)

From the **project root directory**:

```bash
PYTHONPATH=. streamlit run app/ui.py
