from pathlib import Path

import pytest
from PIL import Image

from app.models.convert_job import ConvertJob
from app.services.image_service import ImageService


def _job(source: Path, output: Path) -> ConvertJob:
    return ConvertJob(
        input_path=source,
        output_path=output,
        source_format=source.suffix.lstrip("."),
        target_format=output.suffix.lstrip("."),
    )


def test_png_transparency_is_composited_on_white(tmp_path: Path):
    source = tmp_path / "transparent.png"
    output = tmp_path / "result.jpg"
    image = Image.new("RGBA", (32, 32), (255, 0, 0, 0))
    image.putpixel((31, 31), (255, 0, 0, 255))
    image.save(source)
    image.close()

    results = ImageService.image_to_jpg(_job(source, output))

    assert results == [output]
    with Image.open(output) as converted:
        white_pixel = converted.getpixel((0, 0))
        assert all(channel > 240 for channel in white_pixel)


def test_multipage_tiff_generates_one_jpg_per_page(tmp_path: Path):
    source = tmp_path / "pages.tiff"
    output = tmp_path / "pages.jpg"
    first = Image.new("RGB", (3, 3), "red")
    second = Image.new("RGB", (3, 3), "blue")
    first.save(source, save_all=True, append_images=[second])
    first.close()
    second.close()

    results = ImageService.image_to_jpg(_job(source, output))

    assert [path.name for path in results] == ["pages_page_1.jpg", "pages_page_2.jpg"]
    assert all(path.exists() for path in results)


def test_image_service_does_not_overwrite_output(tmp_path: Path):
    source = tmp_path / "source.png"
    output = tmp_path / "existing.jpg"
    Image.new("RGB", (2, 2), "green").save(source)
    output.write_bytes(b"existing")

    with pytest.raises(FileExistsError):
        ImageService.image_to_jpg(_job(source, output))
