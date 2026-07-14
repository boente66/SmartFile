"""Gera o PDF distribuível a partir do Manual_Usuario.md."""

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "Manual_Usuario.md"
OUTPUT = ROOT / "docs" / "Manual_Usuario.pdf"


def build() -> None:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "ManualCode", parent=styles["BodyText"], fontName="Courier", fontSize=8,
        leading=10, backColor=colors.HexColor("#eef2f7"), leftIndent=6, rightIndent=6,
        spaceBefore=3, spaceAfter=3,
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
        if not line:
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
