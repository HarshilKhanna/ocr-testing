from abc import ABC, abstractmethod


class OCRExtractor(ABC):
    """Abstract base class for OCR extractors."""

    @abstractmethod
    async def extract(self, file_path: str, max_pages: int = 0) -> str:
        """
        Extract text from a PDF file.

        Args:
            file_path: Path to the PDF file on disk.
            max_pages: Maximum number of pages to process.
                       0 means process all pages.

        Returns:
            Full raw text string in correct reading order.
        """
        ...
