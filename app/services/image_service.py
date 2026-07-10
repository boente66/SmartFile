from PIL import Image


class ImageService:
    """
    Serviço para conversões envolvendo imagens.
    """

    @staticmethod
    def image_to_pdf(job, progress=None):
        """
        Converte imagem (JPG/PNG/TIFF) em PDF.
        """

        if progress:
            progress(10, "Abrindo imagem")

        img = Image.open(job.input_path)

        if img.mode != "RGB":
            img = img.convert("RGB")

        if progress:
            progress(70, "Gerando PDF")

        img.save(job.output_path, "PDF")

        if progress:
            progress(100, "Conversão finalizada")

    @staticmethod
    def image_to_jpg(job, progress=None):
        """
        Converte PNG/TIFF para JPG.
        """

        img = Image.open(job.input_path)

        if img.mode != "RGB":
            img = img.convert("RGB")

        img.save(job.output_path, "JPEG")

        if progress:
            progress(100, "Conversão finalizada")