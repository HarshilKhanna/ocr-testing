import os
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_enable_pir_in_executor"] = "0"
os.environ["OMP_NUM_THREADS"] = "1"
import time
import hashlib
import tempfile
import logging

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from fastapi.responses import PlainTextResponse
from models import UploadResponse, CaseResponse
from ocr.factory import get_extractor
from segmentation import segment_cases

# Limit to first page only for debugging (set to 0 for all pages)
MAX_PAGES = 1

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="OCR Case Extractor API")

# CORS – allow the Next.js frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory cache  {file_hash: {"cases": {...}, "engine": str, "pages": int, "raw_text": str}}
# ---------------------------------------------------------------------------
cache: dict[str, dict] = {}

# Store the most recently processed file hash so /case can look it up
current_file_hash: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    selected_engine: str = Form(...),
):
    """Upload a PDF and run OCR + case segmentation."""
    global current_file_hash

    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    pdf_bytes = await file.read()
    file_hash = _sha256(pdf_bytes)
    cache_key = f"{file_hash}:{selected_engine}"

    # Return cached result if same file + engine was already processed
    if cache_key in cache:
        logger.info("Cache hit for %s (%s)", file_hash[:12], selected_engine)
        cached = cache[cache_key]
        current_file_hash = cache_key
        return UploadResponse(
            total_cases_detected=len(cached["cases"]),
            pages_processed=cached["pages"],
            extraction_time=0.0,
            engine_used=cached["engine"],
        )

    # Write to temp file for OCR engines that need a file path
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    try:
        tmp.write(pdf_bytes)
        tmp.close()

        start = time.time()

        extractor = get_extractor(selected_engine)
        raw_text = await extractor.extract(tmp.name, max_pages=MAX_PAGES)

        # ── DEBUG: Print raw OCR text to console ──
        print("\n" + "=" * 60)
        print("RAW OCR TEXT START")
        print("=" * 60)
        print(raw_text)
        print("=" * 60)
        print("RAW OCR TEXT END")
        print("=" * 60 + "\n")

        cases = segment_cases(raw_text,selected_engine)

        # ── DEBUG: Print segmented cases to console ──
        print(f"\n>>> CASES DETECTED: {len(cases)}")
        for k, v in cases.items():
            print(f"\n--- CASE {k} ---")
            print(v[:200] + ("..." if len(v) > 200 else ""))
        print()

        elapsed = round(time.time() - start, 2)

        # Rough page count – count form-feed characters or fall back to 1
        pages = max(raw_text.count("\f") + 1, 1) if raw_text else 0

        logger.info(
            "Extracted %d cases in %.2fs using %s (%s)",
            len(cases),
            elapsed,
            selected_engine,
            file_hash[:12],
        )

        cache[cache_key] = {
            "cases": cases,
            "engine": selected_engine,
            "pages": pages,
            "raw_text": raw_text,
        }
        current_file_hash = cache_key

        return UploadResponse(
            total_cases_detected=len(cases),
            pages_processed=pages,
            extraction_time=elapsed,
            engine_used=selected_engine,
        )
    finally:
        os.unlink(tmp.name)


@app.get("/case", response_model=CaseResponse)
async def get_case(sno: int):
    """Retrieve a single case block by serial number."""
    if current_file_hash is None or current_file_hash not in cache:
        raise HTTPException(status_code=404, detail="No document has been processed yet.")

    cases = cache[current_file_hash]["cases"]
    key = str(sno)

    if key not in cases:
        available = ", ".join(sorted(cases.keys(), key=lambda x: int(x)))
        raise HTTPException(
            status_code=404,
            detail=f"No case found with serial number {sno}. Available: {available}",
        )

    return CaseResponse(sno=sno, content=cases[key])


@app.get("/debug", response_class=PlainTextResponse)
async def debug_raw_text():
    """Return the raw OCR text from the last processed document (for debugging)."""
    if current_file_hash is None or current_file_hash not in cache:
        return "No document has been processed yet."

    cached = cache[current_file_hash]
    raw = cached.get("raw_text", "No raw text stored.")
    cases = cached.get("cases", {})

    sorted_keys = sorted(cases.keys(), key=lambda x: int(x))
    output = f"=== ENGINE: {cached['engine']} ===\n"
    output += f"=== CASES DETECTED: {len(cases)} ===\n"
    output += f"=== CASE KEYS: {', '.join(sorted_keys)} ===\n\n"
    output += "=== RAW OCR TEXT ===\n"
    output += raw + "\n\n"
    output += "=== SEGMENTED CASES ===\n"
    for k in sorted_keys:
        output += f"\n--- CASE {k} ---\n"
        output += cases[k] + "\n"

    return output

