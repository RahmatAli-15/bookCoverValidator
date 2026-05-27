from __future__ import annotations

import logging
from threading import Lock
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    import easyocr

logger = logging.getLogger(__name__)


class OCRManager:
    def __init__(self) -> None:
        self._reader: Any | None = None
        self._lock = Lock()

    def initialize(self) -> None:
        if self._reader is not None:
            return
        with self._lock:
            if self._reader is None:
                # Lazy import to avoid loading heavy OCR/torch stack at app startup.
                import easyocr

                logger.info("OCR engine initialized")
                self._reader = easyocr.Reader(["en"], gpu=False)
                logger.info("OCR model loaded successfully")

    def get_reader(self):
        if self._reader is None:
            self.initialize()
        return self._reader


ocr_manager = OCRManager()
