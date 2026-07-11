from pathlib import Path

from PIL import Image, ImageSequence

from app.models.convert_job import ConvertJob


class ImageService:
    """Conversões de imagens sem decisões de interface ou sobrescrita."""

    @staticmethod
    def image_to_pdf(job: ConvertJob, progress=None) -> list[Path]:
        input_path, output_path = ImageService._validate_paths(job)
        if progress:
            progress(20, "Abrindo imagem")

        with Image.open(input_path) as source:
            frames = [
                ImageService._to_rgb(frame.copy())
                for frame in ImageSequence.Iterator(source)
            ]

        if not frames:
            raise ValueError("A imagem não possui páginas válidas.")

        if progress:
            progress(70, "Gerando PDF")

        first, *remaining = frames
        try:
            first.save(
                output_path,
                "PDF",
                save_all=bool(remaining),
                append_images=remaining,
            )
        finally:
            for frame in frames:
                frame.close()

        if progress:
            progress(90, "PDF gerado")
        return [output_path]

    @staticmethod
    def image_to_jpg(job: ConvertJob, progress=None) -> list[Path]:
        input_path, output_path = ImageService._validate_paths(job, check_output=False)

        with Image.open(input_path) as source:
            frames = [frame.copy() for frame in ImageSequence.Iterator(source)]

        if not frames:
            raise ValueError("A imagem não possui páginas válidas.")

        outputs = ImageService._jpg_output_paths(output_path, len(frames))
        existing = [path for path in outputs if path.exists()]
        if existing:
            raise FileExistsError(f"O arquivo de saída já existe: {existing[0]}")

        try:
            for index, (frame, destination) in enumerate(zip(frames, outputs), start=1):
                rgb = ImageService._to_rgb(frame)
                try:
                    rgb.save(destination, "JPEG")
                finally:
                    rgb.close()
                if progress:
                    value = 20 + int((index / len(frames)) * 70)
                    progress(value, f"Gerando imagem {index}/{len(frames)}")
        finally:
            for frame in frames:
                frame.close()

        return outputs

    @staticmethod
    def _validate_paths(
        job: ConvertJob,
        *,
        check_output: bool = True,
    ) -> tuple[Path, Path]:
        input_path = Path(job.input_path).expanduser().resolve()
        output_path = Path(job.output_path).expanduser().resolve()
        if not input_path.exists() or not input_path.is_file():
            raise FileNotFoundError(f"Imagem de entrada inválida: {input_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if check_output and output_path.exists():
            raise FileExistsError(f"O arquivo de saída já existe: {output_path}")
        return input_path, output_path

    @staticmethod
    def _jpg_output_paths(output_path: Path, frame_count: int) -> list[Path]:
        if frame_count == 1:
            return [output_path]
        return [
            output_path.with_name(f"{output_path.stem}_page_{index}.jpg")
            for index in range(1, frame_count + 1)
        ]

    @staticmethod
    def _to_rgb(image: Image.Image) -> Image.Image:
        if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, "white")
            background.paste(rgba, mask=rgba.getchannel("A"))
            rgba.close()
            return background
        if image.mode == "RGB":
            return image.copy()
        return image.convert("RGB")
