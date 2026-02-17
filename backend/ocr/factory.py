from .base import OCRExtractor
from .azure_extractor import AzureDocumentIntelligenceExtractor
from .paddle_extractor import PaddleOCRExtractor
from .tesseract_extractor import TesseractExtractor


def get_extractor(engine_name: str) -> OCRExtractor:
    """
    Factory function to return the appropriate OCR extractor.

    Args:
        engine_name: One of 'azure', 'paddle', 'tesseract'.

    Returns:
        An instance of the corresponding OCRExtractor.

    Raises:
        ValueError: If the engine name is not recognized.
    """
    engines = {
        "azure": AzureDocumentIntelligenceExtractor,
        "paddle": PaddleOCRExtractor,
        "tesseract": TesseractExtractor,
    }

    if engine_name not in engines:
        raise ValueError(
            f"Unknown engine: '{engine_name}'. "
            f"Supported engines: {', '.join(engines.keys())}"
        )

    return engines[engine_name]()
