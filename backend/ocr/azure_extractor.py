import os
import asyncio
import random
import httpx
from PyPDF2 import PdfReader
from .base import OCRExtractor


class AzureDocumentIntelligenceExtractor(OCRExtractor):
    """
    OCR extractor using Azure Document Intelligence (prebuilt-layout model).

    - Uses 2-page batching (F0 tier limit).
    - Uses Azure reading-order `content` field.
    - Implements exponential backoff + jitter for 429 handling.
    - Slower, but much more stable.
    """

    BATCH_SIZE = 2
    BASE_DELAY = 3
    MAX_BACKOFF = 30

    def __init__(self):
        self.endpoint = os.getenv("AZURE_ENDPOINT", "").rstrip("/")
        self.api_key = os.getenv("AZURE_API_KEY", "")
        if not self.endpoint or not self.api_key:
            raise ValueError("AZURE_ENDPOINT and AZURE_API_KEY must be set in .env")

    async def extract(self, file_path: str, max_pages: int = 0) -> str:

        with open(file_path, "rb") as f:
            pdf_bytes = f.read()

        reader = PdfReader(file_path)
        total_pages = len(reader.pages)
        last_page = min(max_pages, total_pages) if max_pages > 0 else total_pages

        print(f"PDF TOTAL PAGES: {total_pages}, PROCESSING UP TO: {last_page}")

        batches = [
            (start, min(start + self.BATCH_SIZE - 1, last_page))
            for start in range(1, last_page + 1, self.BATCH_SIZE)
        ]

        print(f"AZURE BATCHES: {batches}")

        page_texts = []

        base_url = (
            f"{self.endpoint}/formrecognizer/documentModels/"
            f"prebuilt-layout:analyze?api-version=2023-07-31"
        )

        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "application/pdf",
        }

        async with httpx.AsyncClient(timeout=300) as client:

            for batch_idx, (batch_start, batch_end) in enumerate(batches):

                if batch_idx > 0:
                    delay = self.BASE_DELAY + random.uniform(0.5, 2)
                    print(f"    ⏳ Waiting {round(delay,2)}s before next batch...")
                    await asyncio.sleep(delay)

                batch_url = f"{base_url}&pages={batch_start}-{batch_end}"
                print(f"  → Batch {batch_start}-{batch_end}")

                # ---------- SUBMIT WITH RETRY ----------
                submit_backoff = 3

                while True:
                    response = await client.post(
                        batch_url, headers=headers, content=pdf_bytes
                    )

                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After")
                        wait_time = (
                            int(retry_after)
                            if retry_after
                            else min(submit_backoff, self.MAX_BACKOFF)
                        )

                        wait_time += random.uniform(0.5, 2)
                        print(f"    ⚠ 429 on submit, waiting {round(wait_time,2)}s...")
                        await asyncio.sleep(wait_time)

                        submit_backoff *= 2
                        continue

                    response.raise_for_status()
                    break

                operation_url = response.headers["operation-location"]

                # ---------- POLL WITH BACKOFF ----------
                poll_backoff = 2

                while True:
                    poll_response = await client.get(
                        operation_url,
                        headers={"Ocp-Apim-Subscription-Key": self.api_key},
                    )

                    if poll_response.status_code == 429:
                        retry_after = poll_response.headers.get("Retry-After")
                        wait_time = (
                            int(retry_after)
                            if retry_after
                            else min(poll_backoff, self.MAX_BACKOFF)
                        )

                        wait_time += random.uniform(0.5, 2)
                        print(f"    ⚠ 429 on poll, waiting {round(wait_time,2)}s...")
                        await asyncio.sleep(wait_time)

                        poll_backoff *= 2
                        continue

                    poll_response.raise_for_status()
                    result = poll_response.json()
                    status = result.get("status", "")

                    if status == "succeeded":
                        ar = result["analyzeResult"]
                        content = ar.get("content", "")
                        batch_pages = ar.get("pages", [])

                        print(
                            f"    ✓ Got pages {[p.get('pageNumber') for p in batch_pages]}"
                        )

                        for page in batch_pages:
                            page_num = page.get("pageNumber", 1)
                            spans = page.get("spans", [])

                            if spans:
                                start_off = spans[0]["offset"]
                                end_off = start_off + spans[0]["length"]
                                page_text = content[start_off:end_off]
                            else:
                                page_text = ""

                            page_texts.append((page_num, page_text))

                        break

                    elif status == "failed":
                        error = result.get("error", {})
                        raise RuntimeError(
                            f"Azure failed on pages {batch_start}-{batch_end}: "
                            f"{error.get('message', 'Unknown error')}"
                        )

                    # Normal polling interval (slightly slower to avoid 429)
                    await asyncio.sleep(2.5)

        print(f"\n>>> TOTAL PAGES EXTRACTED: {len(page_texts)}")

        parts = []
        for page_num, text in sorted(page_texts, key=lambda x: x[0]):
            parts.append(f"\n\n=== PAGE {page_num} ===\n")
            parts.append(text)

        return "\n".join(parts)
