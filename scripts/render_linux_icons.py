#!/usr/bin/env python3
"""Renderiza o SVG oficial nos tamanhos exigidos pelo tema hicolor."""

from __future__ import annotations

import argparse
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer


SIZES = (16, 24, 32, 48, 64, 128, 256)


def render(source: Path, output_root: Path) -> None:
    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        raise ValueError(f"SVG inválido: {source}")
    for size in SIZES:
        target = output_root / f"{size}x{size}" / "apps" / "smartfile.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        if not image.save(str(target), "PNG"):
            raise OSError(f"Não foi possível gravar {target}")

    scalable = output_root / "scalable" / "apps" / "smartfile.svg"
    scalable.parent.mkdir(parents=True, exist_ok=True)
    scalable.write_bytes(source.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_root", type=Path)
    args = parser.parse_args()
    render(args.source.resolve(), args.output_root.resolve())


if __name__ == "__main__":
    main()
