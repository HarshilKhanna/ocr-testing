# OCR Case Extractor 📜🔍

A powerful, multi-engine OCR pipeline designed to extract structured legal case data from PDF cause lists. Built with **FastAPI** (Backend) and **Next.js** (Frontend).

## 🚀 Features
- **Multi-Engine OCR Strategy**: choose between Tesseract (local/privacy), Azure Document Intelligence (precision), or PaddleOCR (layout-heavy).
- **Intelligent Segmentation**: Automatically detects case boundaries, merges split columns (Tesseract), and stitches broken text blocks.
- **Smart Caching**: In-memory caching prevents redundant OCR processing for the same file.
- **Azure F0 Optimization**: Batched processing implementation to work around the Azure Free Tier 2-page limit.

## 🛠 Prerequisites

### 1. System Dependencies (Windows)
- **Python 3.10+**
- **Node.js 18+**
- **[Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)**: Install formatting binary and add `Tesseract-OCR` folder to your System PATH.
- **[Poppler](https://github.com/oschwartz10612/poppler-windows/releases/)**: Required for `pdf2image`. Download release, extract, and add `bin/` folder to System PATH.

### 2. Python Packages
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r ../requirements.txt
```
> **Note:** For PaddleOCR on Windows, if you encounter DLL errors or issues with `shapely`, you may need to install the CPU-specific wheel:
> `pip install paddlepaddle==2.6.0 -f https://www.paddlepaddle.org.cn/whl/windows/mkl/avx/stable.html`

### 3. Frontend Packages
```bash
npm install
```

## ⚙️ Configuration

Create a `.env` file in the `backend/` directory:

```env
# Required for Azure OCR
AZURE_ENDPOINT=https://<your-resource>.cognitiveservices.azure.com/
AZURE_API_KEY=<your-key>

# Optional
LOG_LEVEL=INFO
```

## ▶️ Running Locally

### Start Backend (FastAPI)
```bash
cd backend
uvicorn main:app --reload --port 8000
```
API Docs will be available at: http://localhost:8000/docs

### Start Frontend (Next.js)
```bash
npm run dev
```
App will run at: http://localhost:3000

## 🏗 Architecture
For a deep dive into the system design, OCR strategy pattern, and segmentation logic, see [backend/system_architecture.md](./backend/system_architecture.md).
