from __future__ import annotations

from pathlib import Path

import cv2
import fitz
import numpy as np
from PIL import Image


class PDFProcessingError(Exception):
    pass


class ImageProcessingError(Exception):
    pass


def load_pdf_first_page_as_bgr(pdf_path: Path, scale: float = 1.3) -> np.ndarray:
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise PDFProcessingError("Failed to open PDF file.") from exc

    try:
        if doc.page_count == 0:
            raise PDFProcessingError("PDF has no pages.")

        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        return bgr
    except PDFProcessingError:
        raise
    except Exception as exc:
        raise PDFProcessingError("Failed to render first PDF page.") from exc
    finally:
        doc.close()


def load_png_as_bgr(image_path: Path) -> np.ndarray:
    try:
        image = Image.open(image_path).convert("RGB")
        rgb = np.array(image)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    except Exception as exc:
        raise ImageProcessingError("Failed to read PNG image.") from exc


def preprocess_for_ocr(image_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    # Faster preprocessing path for latency-sensitive OCR.
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary
