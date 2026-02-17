import asyncio
import pytesseract
from pdf2image import convert_from_path
from .base import OCRExtractor


class TesseractExtractor(OCRExtractor):
    """
    OCR extractor using Tesseract (local).

    Converts each PDF page to an image, runs pytesseract,
    and combines all page texts sequentially.

    Uses --psm 4 (single column of variable-size text) to force
    Tesseract to read rows left-to-right instead of column-by-column.
    """

    async def extract(self, file_path: str, max_pages: int = 0) -> str:
        # Run CPU-bound work in a thread pool
        return await asyncio.to_thread(self._extract_sync, file_path, max_pages)

    def _extract_sync(self, file_path: str, max_pages: int = 0) -> str:
        kwargs = {}
        if max_pages > 0:
            kwargs["last_page"] = max_pages
        images = convert_from_path(file_path, dpi=300, **kwargs)
        all_text: list[str] = []

        # --psm 4: Assume a single column of text of variable sizes
        # This forces row-by-row reading instead of column-by-column
        custom_config = r"--psm 4"

        for page_image in images:
            text = pytesseract.image_to_string(page_image, config=custom_config)
            all_text.append(text)

        return "\n\n".join(all_text)
