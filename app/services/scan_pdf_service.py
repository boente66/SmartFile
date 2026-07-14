from io import BytesIO
from PIL import Image


class ScanPDFService:
    """
    Converte imagens escaneadas em PDF.
    """

    @staticmethod
    def save_as_pdf(images: list[Image.Image], output_file):
        if not images:
            raise ValueError("Nenhuma imagem para salvar")

        images_rgb = [img.convert("RGB") for img in images]
        try:
            first, *rest = images_rgb
            first.save(output_file, save_all=True, append_images=rest)
        finally:
            for image in images_rgb:
                image.close()

    @staticmethod
    def to_pdf_bytes(images: list[Image.Image]) -> bytes:
        """
        Gera PDF em memória (bytes).
        """
        if not images:
            raise ValueError("Nenhuma imagem para converter")

        buffer = BytesIO()
        ScanPDFService.save_as_pdf(images, buffer)
        buffer.seek(0)
        return buffer.read()
