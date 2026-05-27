from __future__ import annotations

import logging
from threading import Lock

import easyocr

logger = logging.getLogger(__name__)


class OCRManager:
    def __init__(self) -> None:
        self._reader: easyocr.Reader | None = None
        self._lock = Lock()

    def initialize(self) -> None:
        if self._reader is not None:
            return
        with self._lock:
            if self._reader is None:
                logger.info("OCR engine initialized")
                self._reader = easyocr.Reader(["en"], gpu=False)
                logger.info("OCR model loaded successfully")

    def get_reader(self) -> easyocr.Reader:
        if self._reader is None:
            self.initialize()
        return self._reader


ocr_manager = OCRManager()

