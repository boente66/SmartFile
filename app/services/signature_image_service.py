from __future__ import annotations

from PyQt6.QtCore import QBuffer, QByteArray, Qt
from PyQt6.QtGui import QImage

from app.errors.handwritten_signature_exceptions import SignatureImageError


class SignatureImageService:
    """Decodifica e normaliza assinaturas visuais sem persistir a fonte."""

    MAX_INPUT_SIZE = 5 * 1024 * 1024
    MAX_DIMENSION = 4096
    NORMALIZED_DIMENSION = 2048

    def normalize(self, data: bytes) -> bytes:
        if not data or len(data) > self.MAX_INPUT_SIZE:
            raise SignatureImageError("A imagem deve possuir no máximo 5 MB.")
        image = QImage.fromData(data)
        if image.isNull():
            raise SignatureImageError("O arquivo informado não é uma imagem válida.")
        if image.width() > self.MAX_DIMENSION or image.height() > self.MAX_DIMENSION:
            raise SignatureImageError("A imagem excede o limite de 4096 × 4096 pixels.")
        image = image.convertToFormat(QImage.Format.Format_ARGB32)
        if max(image.width(), image.height()) > self.NORMALIZED_DIMENSION:
            image = image.scaled(
                self.NORMALIZED_DIMENSION,
                self.NORMALIZED_DIMENSION,
                aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio,
                transformMode=Qt.TransformationMode.SmoothTransformation,
            )
        payload = QByteArray()
        buffer = QBuffer(payload)
        buffer.open(QBuffer.OpenModeFlag.WriteOnly)
        if not image.save(buffer, "PNG"):
            raise SignatureImageError("Não foi possível normalizar a imagem da assinatura.")
        return bytes(payload)
