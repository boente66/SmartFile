"""Compatibilidade do serviço com o adaptador puro de normalização."""
from app.imaging.signature_image import SignatureImageNormalizer


class SignatureImageService(SignatureImageNormalizer):
    pass
