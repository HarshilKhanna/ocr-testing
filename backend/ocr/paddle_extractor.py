import asyncio
import numpy as np
import paddle
from pdf2image import convert_from_path
from paddleocr import PaddleOCR
from .base import OCRExtractor


class PaddleOCRExtractor(OCRExtractor):
    """
    OCR extractor using PaddleOCR.

    Converts each PDF page to an image, runs PaddleOCR,
    and combines all detected text in reading order.
    """

    def __init__(self):
        # Initialize PaddleOCR once (downloads models on first run)
        self.ocr = PaddleOCR(use_angle_cls=True, lang="en")

    async def extract(self, file_path: str, max_pages: int = 0) -> str:
        # Run CPU-bound PDF conversion and OCR in a thread pool
        return await asyncio.to_thread(self._extract_sync, file_path, max_pages)

    def _extract_sync(self, file_path: str, max_pages: int = 0) -> str:
        kwargs = {}
        if max_pages > 0:
            kwargs["last_page"] = max_pages
        images = convert_from_path(file_path, **kwargs)
        all_text: list[str] = []

        for page_image in images:
            img_array = np.array(page_image)
            result = self.ocr.ocr(img_array)

            page_lines: list[str] = []
            if result and result[0]:
                for line in result[0]:
                    text = line[1][0]  # (text, confidence)
                    page_lines.append(text)

            all_text.append("\n".join(page_lines))

        return "\n\n".join(all_text)
