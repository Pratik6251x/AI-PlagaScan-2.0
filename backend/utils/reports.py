"""Report generation: PDF, DOCX, Excel exports."""
import importlib
import os
import io
from typing import Dict, Optional
# Pre-import heavy libraries at module load to avoid concurrent-import
# BlockingIOError under the Flask debug reloader.

openpyxl = importlib.import_module("openpyxl")
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from config import REPORT_FOLDER
LOGO_TEXT = "PlagiaScan AI Lite"
def _ensure_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def generate_pdf(report: Dict, user: Dict, document: Dict) -> str:
    """Generate a professional PDF report. Returns absolute file path."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                    TableStyle, HRFlowable)
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    out_name = f"report_{report['id']}.pdf"
    out_path = os.path.join(REPORT_FOLDER, out_name)
    _ensure_dir(out_path)

    doc = SimpleDocTemplate(out_path, pagesize=A4,
                           leftMargin=20*mm, rightMargin=20*mm,
                           topMargin=18*mm, bottomMargin=18*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleX", parent=styles["Title"],
                                 textColor=colors.HexColor("#6366f1"),
                                 fontSize=22, alignment=TA_CENTER, spaceAfter=4)
    sub_style = ParagraphStyle("Sub", parent=styles["Normal"],
                               fontSize=10, textColor=colors.grey, alignment=TA_CENTER, spaceAfter=10)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"],
                        textColor=colors.HexColor("#1e3a8a"), fontSize=13, spaceBefore=12, spaceAfter=6)
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=15)
    mono = ParagraphStyle("Mono", parent=styles["Code"], fontSize=9, leading=12,
                         backColor=colors.HexColor("#f1f5f9"), borderPadding=6)

    story = []
    story.append(Paragraph(LOGO_TEXT, title_style))
    story.append(Paragraph("AI-Based Plagiarism Detection Report", sub_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#6366f1")))
    story.append(Spacer(1, 8))

    meta = [
        ["Student Name", user.get("full_name", "N/A")],
        ["Email", user.get("email", "N/A")],
        ["Document Name", document.get("original_name", "N/A")],
        ["Upload Date", report.get("created_at", "N/A")],
        ["Report ID", str(report["id"])],
    ]
    t = Table(meta, colWidths=[40*mm, 120*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2ff")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1e3a8a")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c7d2fe")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c7d2fe")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Analysis Summary", h2))
    score_data = [
        ["Metric", "Value"],
        ["Similarity %", f"{report['similarity_percent']}%"],
        ["Original %", f"{report['original_percent']}%"],
        ["AI Probability %", f"{report['ai_probability']}%"],
        ["Human Probability %", f"{report['human_probability']}%"],
        ["Confidence Score", f"{report['confidence_score']}%"],
        ["Category", report["category"]],
    ]
    st = Table(score_data, colWidths=[60*mm, 100*mm])
    st.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6366f1")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#a5b4fc")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c7d2fe")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(st)
    story.append(Spacer(1, 8))

    story.append(Paragraph(report.get("summary", ""), body))
    story.append(Spacer(1, 6))

    matched_sources = report.get("matched_sources") or []
    story.append(Paragraph(f"Matched Sources ({len(matched_sources)})", h2))
    if not matched_sources:
        story.append(Paragraph("No significant matches found in the repository.", body))
    else:
        for i, m in enumerate(matched_sources, 1):
            story.append(Paragraph(f"<b>Source {i}: {m.get('source_title','')}</b>", body))
            story.append(Paragraph(f"Reference: {m.get('source_reference','')}", body))
            story.append(Paragraph(f"Similarity: {m.get('similarity_percent',0)}%", body))
            for p in m.get("matched_paragraphs", []):
                story.append(Paragraph(f"<b>Matched text:</b> {_escape(p.get('matched_text',''))}", mono))
                story.append(Paragraph(f"<b>Source text:</b> {_escape(p.get('source_text',''))}", mono))
                story.append(Paragraph(f"Citation: {_escape(p.get('citation_suggestion',''))}", body))
                story.append(Spacer(1, 4))
            story.append(Spacer(1, 6))

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "This report is generated by PlagiaScan AI Lite and presents probabilistic analysis. "
        "It does not constitute legal proof of plagiarism, copyright ownership, or authorship.",
        ParagraphStyle("Foot", parent=body, fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
    ))
    story.append(Paragraph(f"Generated on {report.get('created_at','')}", 
                           ParagraphStyle("Foot2", parent=body, fontSize=8, textColor=colors.grey, alignment=TA_CENTER)))

    doc.build(story)
    return out_path
def generate_docx(report: Dict, user: Dict, document: Dict) -> str:
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    out_name = f"report_{report['id']}.docx"
    out_path = os.path.join(REPORT_FOLDER, out_name)
    _ensure_dir(out_path)

    doc = Document()
    h = doc.add_heading(LOGO_TEXT, level=0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph("AI-Based Plagiarism Detection Report")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.runs[0].font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    doc.add_paragraph()
    doc.add_heading("Document Information", level=1)
    info = [
        ("Student Name", user.get("full_name", "N/A")),
        ("Email", user.get("email", "N/A")),
        ("Document Name", document.get("original_name", "N/A")),
        ("Upload Date", report.get("created_at", "N/A")),
        ("Report ID", str(report["id"])),
    ]
    for k, v in info:
        p = doc.add_paragraph()
        p.add_run(f"{k}: ").bold = True
        p.add_run(v)

    doc.add_heading("Analysis Summary", level=1)
    scores = [
        ("Similarity %", f"{report['similarity_percent']}%"),
        ("Original %", f"{report['original_percent']}%"),
        ("AI Probability %", f"{report['ai_probability']}%"),
        ("Human Probability %", f"{report['human_probability']}%"),
        ("Confidence Score", f"{report['confidence_score']}%"),
        ("Category", report["category"]),
    ]
    for k, v in scores:
        p = doc.add_paragraph()
        p.add_run(f"{k}: ").bold = True
        p.add_run(v)

    doc.add_paragraph(report.get("summary", ""))
    matched_sources = report.get("matched_sources") or []
    doc.add_heading(f"Matched Sources ({len(matched_sources)})", level=1)
    if not matched_sources:
        doc.add_paragraph("No significant matches found in the repository.")
    else:
        for i, m in enumerate(matched_sources, 1):
            doc.add_heading(f"Source {i}: {m.get('source_title','')}", level=2)
            doc.add_paragraph(f"Reference: {m.get('source_reference','')}")
            doc.add_paragraph(f"Similarity: {m.get('similarity_percent',0)}%")
            for p in m.get("matched_paragraphs", []):
                doc.add_paragraph(f"Matched text: {p.get('matched_text','')}")
                doc.add_paragraph(f"Source text: {p.get('source_text','')}")
                doc.add_paragraph(f"Citation: {p.get('citation_suggestion','')}")

    doc.add_paragraph()
    foot = doc.add_paragraph(
        "This report is generated by PlagiaScan AI Lite and presents probabilistic analysis. "
        "It does not constitute legal proof of plagiarism, copyright ownership, or authorship."
    )
    foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    foot.runs[0].font.size = Pt(8)
    foot.runs[0].font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    doc.save(out_path)
    return out_path
def generate_excel(report: Dict, user: Dict, document: Dict) -> str:
    out_name = f"report_{report['id']}.xlsx"
    out_path = os.path.join(REPORT_FOLDER, out_name)
    _ensure_dir(out_path)

    wb = Workbook()
    ws = wb.active
    ws.title = "Report Summary"

    header_fill = PatternFill("solid", fgColor="6366F1")
    header_font = Font(color="FFFFFF", bold=True)
    title_font = Font(size=16, bold=True, color="1E3A8A")

    ws["A1"] = LOGO_TEXT
    ws["A1"].font = title_font
    ws.merge_cells("A1:B1")
    ws["A2"] = "AI-Based Plagiarism Detection Report"
    ws.merge_cells("A2:B2")

    info = [
        ("Student Name", user.get("full_name", "N/A")),
        ("Email", user.get("email", "N/A")),
        ("Document Name", document.get("original_name", "N/A")),
        ("Upload Date", report.get("created_at", "N/A")),
        ("Report ID", str(report["id"])),
        ("Similarity %", f"{report['similarity_percent']}%"),
        ("Original %", f"{report['original_percent']}%"),
        ("AI Probability %", f"{report['ai_probability']}%"),
        ("Human Probability %", f"{report['human_probability']}%"),
        ("Confidence Score", f"{report['confidence_score']}%"),
        ("Category", report["category"]),
    ]
    row = 4
    for k, v in info:
        ws.cell(row=row, column=1, value=k).font = Font(bold=True)
        ws.cell(row=row, column=2, value=v)
        row += 1

    row += 1
    ws.cell(row=row, column=1, value="Summary").font = Font(bold=True, size=12)
    row += 1
    ws.cell(row=row, column=1, value=report.get("summary", ""))
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=8)
    ws.cell(row=row, column=1).alignment = Alignment(wrap_text=True)
    row += 2

    matched_sources = report.get("matched_sources") or []
    ws.cell(row=row, column=1, value="Matched Sources").font = Font(bold=True, size=12)
    row += 1
    headers = ["#", "Source Title", "Reference", "Similarity %", "Matched Text", "Source Text", "Citation"]
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=col, value=h)
        c.fill = header_fill
        c.font = header_font
    row += 1
    for i, m in enumerate(matched_sources, 1):
        for p in m.get("matched_paragraphs", []):
            ws.cell(row=row, column=1, value=i)
            ws.cell(row=row, column=2, value=m.get("source_title", ""))
            ws.cell(row=row, column=3, value=m.get("source_reference", ""))
            ws.cell(row=row, column=4, value=m.get("similarity_percent", 0))
            ws.cell(row=row, column=5, value=p.get("matched_text", ""))
            ws.cell(row=row, column=6, value=p.get("source_text", ""))
            ws.cell(row=row, column=7, value=p.get("citation_suggestion", ""))
            row += 1

    for col in range(1, 8):
        ws.column_dimensions[chr(64 + col)].width = 28
    ws.column_dimensions["E"].width = 40
    ws.column_dimensions["F"].width = 40
    wb.save(out_path)
    return out_path
def _escape(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
