"""Gera o PDF distribuível a partir do Manual_Usuario.md."""

import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import CondPageBreak, Image, Paragraph, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "Manual_Usuario.md"
OUTPUT = ROOT / "docs" / "Manual_Usuario.pdf"
IMAGE_PATTERN = re.compile(r"^!\[(?P<alt>[^]]*)\]\(<(?P<angle>[^>]+)>\)$|^!\[(?P<plain_alt>[^]]*)\]\((?P<plain>[^)]+)\)$")


def _manual_image(line: str):
    match = IMAGE_PATTERN.match(line)
    if match is None:
        return None
    relative = match.group("angle") or match.group("plain")
    alt = match.group("alt") or match.group("plain_alt") or "Captura de tela"
    path = (SOURCE.parent / relative).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError:
        return None
    if not path.is_file():
        return None
    picture = Image(str(path))
    max_width, max_height = 174 * mm, 105 * mm
    scale = min(max_width / picture.imageWidth, max_height / picture.imageHeight, 1)
    picture.drawWidth = picture.imageWidth * scale
    picture.drawHeight = picture.imageHeight * scale
    return picture, alt


def build() -> None:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "ManualCode", parent=styles["BodyText"], fontName="Courier", fontSize=8,
        leading=10, backColor=colors.HexColor("#eef2f7"), leftIndent=6, rightIndent=6,
        spaceBefore=3, spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        "ManualCaption", parent=styles["BodyText"], fontSize=8,
        leading=10, textColor=colors.HexColor("#475569"), alignment=1,
        spaceBefore=2, spaceAfter=5,
    ))
    styles["Title"].textColor = colors.HexColor("#15803d")
    styles["Heading1"].textColor = colors.HexColor("#0f172a")
    styles["Heading2"].textColor = colors.HexColor("#166534")
    story = []
    in_code = False
    code_lines: list[str] = []
    for raw in SOURCE.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            if in_code and code_lines:
                story.append(Paragraph("<br/>".join(escape(item) for item in code_lines), styles["ManualCode"]))
                code_lines.clear()
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line or " ")
            continue
        manual_image = _manual_image(line)
        if manual_image is not None:
            picture, alt = manual_image
            story.append(CondPageBreak(picture.drawHeight + 12 * mm))
            story.append(picture)
            story.append(Paragraph(f"<i>{escape(alt)}</i>", styles["ManualCaption"]))
            story.append(Spacer(1, 4 * mm))
        elif not line:
            story.append(Spacer(1, 2.5 * mm))
        elif line.startswith("# "):
            story.append(Paragraph(escape(line[2:]), styles["Title"]))
        elif line.startswith("## "):
            story.append(Paragraph(escape(line[3:]), styles["Heading1"]))
        elif line.startswith("### "):
            story.append(Paragraph(escape(line[4:]), styles["Heading2"]))
        elif line.startswith("- "):
            story.append(Paragraph("• " + escape(line[2:]), styles["BodyText"]))
        else:
            text = escape(line).replace("**", "").replace("`", "")
            story.append(Paragraph(text, styles["BodyText"]))
    document = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="SmartFile — Manual do Usuário", author="SmartFile",
        pageCompression=1,
    )
    document.build(story)


if __name__ == "__main__":
    build()
