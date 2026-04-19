"""
Premium PDF Report Generator — Professional DDR layout.
Modeled after high-end architectural / engineering inspection reports (UrbanRoof style).
"""
import os
import logging
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, KeepTogether, PageBreak, NextPageTemplate, CondPageBreak
)

logger = logging.getLogger(__name__)

# ──────────────────── Color System ────────────────────
NAVY      = HexColor("#1a2332")
DARK_BLUE = HexColor("#2c3e50")
ACCENT    = HexColor("#3b82f6")
LIGHT_BG  = HexColor("#f1f5f9")
WHITE_BG  = HexColor("#ffffff")
BORDER    = HexColor("#e2e8f0")
TABLE_HEAD = HexColor("#334155")
TABLE_ALT  = HexColor("#f8fafc")

TEXT_PRIMARY   = HexColor("#1e293b")
TEXT_SECONDARY = HexColor("#64748b")
TEXT_MUTED     = HexColor("#94a3b8")

SEV_LOW      = HexColor("#22c55e")
SEV_MODERATE = HexColor("#eab308")
SEV_HIGH     = HexColor("#ef4444")
SEV_CRITICAL = HexColor("#dc2626")

SEVERITY_COLORS = {
    "low":      SEV_LOW,
    "moderate": SEV_MODERATE,
    "high":     SEV_HIGH,
    "critical": SEV_CRITICAL,
}

PAGE_W, PAGE_H = A4
MARGIN_L = 22 * mm
MARGIN_R = 22 * mm
MARGIN_T = 28 * mm
MARGIN_B = 22 * mm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R


# ──────────────────── Typography ────────────────────
def _styles():
    """Build the complete typography system."""
    s = getSampleStyleSheet()

    s.add(ParagraphStyle("CoverLabel", fontName="Helvetica", fontSize=11,
        leading=14, textColor=TEXT_MUTED, spaceAfter=6, alignment=TA_LEFT))

    s.add(ParagraphStyle("CoverTitle", fontName="Helvetica-Bold", fontSize=32,
        leading=38, textColor=NAVY, spaceAfter=4, alignment=TA_LEFT))

    s.add(ParagraphStyle("CoverSub", fontName="Helvetica", fontSize=12,
        leading=16, textColor=TEXT_SECONDARY, spaceAfter=16, alignment=TA_LEFT))

    s.add(ParagraphStyle("SectionNum", fontName="Helvetica-Bold", fontSize=9,
        leading=12, textColor=ACCENT, spaceBefore=24, spaceAfter=0))

    s.add(ParagraphStyle("SectionTitle", fontName="Helvetica-Bold", fontSize=14,
        leading=18, textColor=TEXT_PRIMARY, spaceBefore=2, spaceAfter=10))

    s.add(ParagraphStyle("Body", fontName="Helvetica", fontSize=10,
        leading=15, textColor=TEXT_PRIMARY, spaceAfter=8, alignment=TA_JUSTIFY))

    s.add(ParagraphStyle("BodySmall", fontName="Helvetica", fontSize=9,
        leading=13, textColor=TEXT_SECONDARY, spaceAfter=4))

    s.add(ParagraphStyle("ObsTitle", fontName="Helvetica-Bold", fontSize=11,
        leading=15, textColor=TEXT_PRIMARY, spaceAfter=3))

    s.add(ParagraphStyle("ObsBody", fontName="Helvetica", fontSize=9.5,
        leading=14, textColor=TEXT_PRIMARY, spaceAfter=4, leftIndent=12))

    s.add(ParagraphStyle("ObsThermal", fontName="Helvetica-Oblique", fontSize=9,
        leading=13, textColor=TEXT_SECONDARY, spaceAfter=4, leftIndent=12))

    s.add(ParagraphStyle("BulletItem", fontName="Helvetica", fontSize=10,
        leading=15, textColor=TEXT_PRIMARY, spaceAfter=5, leftIndent=16,
        firstLineIndent=-12))

    s.add(ParagraphStyle("Caption", fontName="Helvetica-Oblique", fontSize=7.5,
        leading=10, textColor=TEXT_MUTED, alignment=TA_CENTER, spaceBefore=2, spaceAfter=8))

    s.add(ParagraphStyle("Footer", fontName="Helvetica", fontSize=7.5,
        leading=10, textColor=TEXT_MUTED, alignment=TA_CENTER))

    s.add(ParagraphStyle("MetaLabel", fontName="Helvetica-Bold", fontSize=8.5,
        leading=11, textColor=TEXT_MUTED))

    s.add(ParagraphStyle("MetaValue", fontName="Helvetica", fontSize=9,
        leading=12, textColor=TEXT_PRIMARY, spaceAfter=6))

    s.add(ParagraphStyle("DashLabel", fontName="Helvetica-Bold", fontSize=8,
        leading=10, textColor=white, alignment=TA_CENTER))

    s.add(ParagraphStyle("DashCount", fontName="Helvetica-Bold", fontSize=18,
        leading=22, textColor=white, alignment=TA_CENTER))

    s.add(ParagraphStyle("SevBadge", fontName="Helvetica-Bold", fontSize=8,
        leading=10, textColor=white, alignment=TA_CENTER))

    s.add(ParagraphStyle("TocEntry", fontName="Helvetica", fontSize=10,
        leading=16, textColor=TEXT_PRIMARY, spaceAfter=4, leftIndent=10))

    s.add(ParagraphStyle("TocSection", fontName="Helvetica-Bold", fontSize=10,
        leading=16, textColor=NAVY, spaceAfter=4))

    s.add(ParagraphStyle("TableHeader", fontName="Helvetica-Bold", fontSize=8.5,
        leading=11, textColor=white, alignment=TA_CENTER))

    s.add(ParagraphStyle("TableCell", fontName="Helvetica", fontSize=8.5,
        leading=12, textColor=TEXT_PRIMARY))

    s.add(ParagraphStyle("TableCellCenter", fontName="Helvetica", fontSize=8.5,
        leading=12, textColor=TEXT_PRIMARY, alignment=TA_CENTER))

    s.add(ParagraphStyle("Disclaimer", fontName="Helvetica", fontSize=8,
        leading=12, textColor=TEXT_SECONDARY, spaceAfter=6, alignment=TA_JUSTIFY))

    s.add(ParagraphStyle("DisclaimerBold", fontName="Helvetica-Bold", fontSize=8,
        leading=12, textColor=TEXT_PRIMARY, spaceAfter=4))

    return s


# ──────────────────── Page Decorators ────────────────────
_site_address_for_footer = ""

def _cover_page(canvas, doc):
    """Draw the cover page background."""
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, PAGE_H - 90 * mm, PAGE_W, 90 * mm, fill=1, stroke=0)
    canvas.setStrokeColor(ACCENT)
    canvas.setLineWidth(3)
    canvas.line(MARGIN_L, PAGE_H - 92 * mm, MARGIN_L + 50 * mm, PAGE_H - 92 * mm)
    canvas.setFillColor(LIGHT_BG)
    canvas.rect(0, 0, PAGE_W, 30 * mm, fill=1, stroke=0)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawCentredString(PAGE_W / 2, 12 * mm,
        "This report is generated using AI-assisted analysis. Verify findings with on-site inspection.")
    canvas.restoreState()


def _content_page(canvas, doc):
    """Draw header and footer on content pages."""
    canvas.saveState()

    # Top accent line
    canvas.setStrokeColor(ACCENT)
    canvas.setLineWidth(2)
    canvas.line(MARGIN_L, PAGE_H - 12 * mm, MARGIN_L + 20 * mm, PAGE_H - 12 * mm)

    # Header text (include site address if available)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(TEXT_MUTED)
    header_text = "DETAILED DIAGNOSTIC REPORT"
    if _site_address_for_footer:
        # Truncate if too long
        addr = _site_address_for_footer[:60] + ("..." if len(_site_address_for_footer) > 60 else "")
        header_text = f"DDR — {addr}"
    canvas.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 12 * mm, header_text)

    # Footer line
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_L, MARGIN_B - 6 * mm, PAGE_W - MARGIN_R, MARGIN_B - 6 * mm)

    # Footer text
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawString(MARGIN_L, MARGIN_B - 12 * mm,
                      f"AI DDR Generator  |  {datetime.now().strftime('%d %B %Y')}")
    canvas.drawRightString(PAGE_W - MARGIN_R, MARGIN_B - 12 * mm,
                           f"Page {canvas.getPageNumber() - 1}")

    canvas.restoreState()


# ──────────────────── Helpers ────────────────────
def _section(elements, num, title, styles):
    """Add a stylized section header with a thin underline and page protection."""
    elements.append(CondPageBreak(20 * mm))  # Protect header from being at the bottom
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph(f"SECTION {num}", styles["SectionNum"]))
    elements.append(Paragraph(title, styles["SectionTitle"]))


def _get_image_parts(img_path, caption=None, styles=None,
                     max_w=80 * mm, max_h=65 * mm):
    """Create image flowables for a grid cell. Returns list [Image, Caption]."""
    if not img_path or img_path == "Image Not Available":
        return []

    abs_path = os.path.join(os.getcwd(), img_path) if not os.path.isabs(img_path) else img_path
    if not os.path.exists(abs_path):
        return []

    try:
        img = RLImage(abs_path)
        iw, ih = img.imageWidth, img.imageHeight
        if iw <= 0 or ih <= 0:
            return []

        ratio = min(max_w / iw, max_h / ih, 1.0)
        img.drawWidth = iw * ratio
        img.drawHeight = ih * ratio
        
        parts = [img]
        if caption and styles:
            parts.append(Paragraph(f"<i>{caption}</i>", styles["Caption"]))
        return parts
    except Exception as e:
        logger.warning(f"Image flowable creation failed for {abs_path}: {e}")
        return []


def _make_image_row(img_list, styles):
    """
    Creates a 1 or 2 column table for images and captions.
    img_list: list of dicts {'path': str, 'caption': str}
    """
    if not img_list:
        return None

    row_data = []
    col_widths = []
    
    # Calculate widths for 1 or 2 columns
    num_cols = min(len(img_list), 2)
    width_per_col = (CONTENT_W - (num_cols - 1) * 4 * mm) / num_cols
    
    row_content = []
    for item in img_list[:2]:
        parts = _get_image_parts(item['path'], item['caption'], styles, 
                                max_w=width_per_col, max_h=65 * mm)
        if parts:
            row_content.append(parts)
        col_widths.append(width_per_col)
    
    if not row_content:
        return None

    t = Table([row_content], colWidths=col_widths)
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


def _severity_badge(severity, styles):
    """Create a small colored severity badge."""
    sev_key = (severity or "low").lower()
    color = SEVERITY_COLORS.get(sev_key, TEXT_MUTED)

    badge_data = [[Paragraph(f"<font color='white'>{severity.upper()}</font>", styles["SevBadge"])]]
    t = Table(badge_data, colWidths=[22 * mm], rowHeights=[5.5 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), color),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 0),
        ('TOPPADDING', (0, 0), (0, 0), 1),
        ('BOTTOMPADDING', (0, 0), (0, 0), 1),
    ]))
    return t


def _make_info_table(rows, styles):
    """Create a professional key-value info table."""
    table_data = []
    for label, value in rows:
        table_data.append([
            Paragraph(f"<b>{label}</b>", styles["TableCell"]),
            Paragraph(str(value), styles["TableCell"]),
        ])

    t = Table(table_data, colWidths=[45 * mm, CONTENT_W - 47 * mm])
    style_cmds = [
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (0, -1), 8),
        ('LEFTPADDING', (1, 0), (1, -1), 10),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, BORDER),
        ('LINEBELOW', (0, -1), (-1, -1), 0.5, BORDER),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
    ]
    # Alternate row shading
    for i in range(len(table_data)):
        if i % 2 == 0:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), TABLE_ALT))
    t.setStyle(TableStyle(style_cmds))
    return t


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                    MAIN GENERATOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def generate_pdf(ddr_data):
    """Generate a clean, professional DDR PDF."""
    global _site_address_for_footer
    logger.info("📄 Generating professional PDF report...")

    buffer = BytesIO()

    # Extract site metadata for cover and header
    site = ddr_data.get("SiteMetadata", {})
    if isinstance(site, str):
        site = {}
    site_address = site.get("SiteAddress", "")
    _site_address_for_footer = site_address

    doc = BaseDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T, bottomMargin=MARGIN_B,
        title="Detailed Diagnostic Report",
        author="AI DDR Generator",
    )

    content_frame = Frame(MARGIN_L, MARGIN_B, CONTENT_W,
                          PAGE_H - MARGIN_T - MARGIN_B, id="content")

    doc.addPageTemplates([
        PageTemplate(id="cover", frames=content_frame, onPage=_cover_page),
        PageTemplate(id="content", frames=content_frame, onPage=_content_page),
    ])

    styles = _styles()
    els = []

    # ━━━━━━━━━━━━━━━  COVER PAGE  ━━━━━━━━━━━━━━━
    els.append(Spacer(1, 95 * mm))
    els.append(Paragraph("DETAILED", styles["CoverLabel"]))
    els.append(Paragraph("Diagnostic Report", styles["CoverTitle"]))
    els.append(Spacer(1, 6))

    # Cover metadata table
    now = datetime.now()
    meta_rows = []
    if site.get("PreparedFor"):
        meta_rows.append(("PREPARED FOR", site["PreparedFor"]))
    if site_address:
        meta_rows.append(("SITE ADDRESS", site_address))
    meta_rows.append(("DATE", site.get("DateOfInspection", now.strftime("%d %B %Y"))))
    if site.get("InspectedBy"):
        meta_rows.append(("INSPECTED BY", site["InspectedBy"]))
    meta_rows.append(("REPORT BY", "AI DDR Generator"))

    if meta_rows:
        cover_tbl_data = []
        for label, value in meta_rows:
            cover_tbl_data.append([
                Paragraph(label, styles["MetaLabel"]),
                Paragraph(str(value), styles["MetaValue"]),
            ])
        cover_tbl = Table(cover_tbl_data, colWidths=[35 * mm, 120 * mm])
        cover_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ]))
        els.append(cover_tbl)
        els.append(Spacer(1, 16))

    # Brief summary on cover
    summary = str(ddr_data.get("PropertyIssueSummary", ""))
    if summary:
        display_summary = summary if len(summary) <= 350 else summary[:350] + "…"
        els.append(Paragraph(display_summary, styles["Body"]))

    els.append(NextPageTemplate("content"))
    els.append(PageBreak())

    # ━━━━━━━━━━━━━━━  TABLE OF CONTENTS  ━━━━━━━━━━━━━━━
    _section(els, "00", "Table of Contents", styles)

    toc_entries = [
        ("01", "Site Information"),
        ("02", "Issue Overview & Severity Dashboard"),
        ("03", "Property Issue Summary"),
        ("04", "Area-wise Observations"),
        ("05", "Impact Summary — Source vs. Symptom"),
        ("06", "Probable Root Cause"),
        ("07", "Severity Assessment"),
        ("08", "Recommended Actions"),
        ("09", "Additional Notes"),
        ("10", "Missing or Unclear Information"),
        ("11", "Limitations & Disclaimer"),
    ]
    for num, title in toc_entries:
        els.append(Paragraph(
            f"<b>Section {num}</b>&nbsp;&nbsp;&nbsp;&nbsp;{title}",
            styles["TocEntry"]))
    els.append(Spacer(1, 12))

    # ━━━━━━━━━━━━━━━  SECTION 01: SITE INFO  ━━━━━━━━━━━━━━━
    _section(els, "01", "Site Information", styles)

    site_rows = [
        ("Client / Owner", site.get("ClientName", "Not Available")),
        ("Site Address", site.get("SiteAddress", "Not Available")),
        ("Prepared For", site.get("PreparedFor", "Not Available")),
        ("Type of Structure", site.get("TypeOfStructure", "Not Available")),
        ("No. of Floors", site.get("Floors", "Not Available")),
        ("Year of Construction", site.get("YearOfConstruction", "Not Available")),
        ("Age of Building", site.get("AgeOfBuilding", "Not Available")),
        ("Date of Inspection", site.get("DateOfInspection", "Not Available")),
        ("Inspected By", site.get("InspectedBy", "Not Available")),
    ]
    els.append(_make_info_table(site_rows, styles))
    els.append(Spacer(1, 12))

    # ━━━━━━━━━━━━━━━  SECTION 02: DASHBOARD  ━━━━━━━━━━━━━━━
    observations = ddr_data.get("AreaWiseObservations", [])
    if isinstance(observations, str):
        observations = []

    counts = {"low": 0, "moderate": 0, "high": 0, "critical": 0}
    for obs in observations:
        sev = (obs.get("severity", "") or "").lower()
        if sev in counts:
            counts[sev] += 1
    total_issues = sum(counts.values())

    _section(els, "02", "Issue Overview & Severity Dashboard", styles)
    els.append(Paragraph(
        f"<b>{total_issues}</b> issue{'s' if total_issues != 1 else ''} identified across "
        f"<b>{len(observations)}</b> area{'s' if len(observations) != 1 else ''}.",
        styles["Body"]))

    # Dashboard cards
    card_data = [
        [Paragraph(f"<font size='16'><b>{counts['critical']}</b></font>", styles["DashCount"]),
         Paragraph(f"<font size='16'><b>{counts['high']}</b></font>", styles["DashCount"]),
         Paragraph(f"<font size='16'><b>{counts['moderate']}</b></font>", styles["DashCount"]),
         Paragraph(f"<font size='16'><b>{counts['low']}</b></font>", styles["DashCount"])],
        [Paragraph("CRITICAL", styles["DashLabel"]),
         Paragraph("HIGH", styles["DashLabel"]),
         Paragraph("MODERATE", styles["DashLabel"]),
         Paragraph("LOW", styles["DashLabel"])],
    ]
    col_w = 38 * mm
    dash = Table(card_data, colWidths=[col_w] * 4, rowHeights=[14 * mm, 6 * mm])
    dash.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 1), SEV_CRITICAL),
        ('BACKGROUND', (1, 0), (1, 1), SEV_HIGH),
        ('BACKGROUND', (2, 0), (2, 1), SEV_MODERATE),
        ('BACKGROUND', (3, 0), (3, 1), SEV_LOW),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, 0), 4),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 0), (-1, 0), 0, white),
    ]))
    els.append(dash)
    els.append(Spacer(1, 16))

    # ━━━━━━━━━━━━━━━  SECTION 03: SUMMARY  ━━━━━━━━━━━━━━━
    _section(els, "03", "Property Issue Summary", styles)
    full_summary = str(ddr_data.get("PropertyIssueSummary", "Not Available"))
    els.append(Paragraph(full_summary, styles["Body"]))

    # ━━━━━━━━━━━━━━━  SECTION 04: OBSERVATIONS  ━━━━━━━━━━━━━━━
    _section(els, "04", "Area-wise Observations", styles)

    for idx, obs in enumerate(observations):
        area = obs.get("area", "Unknown Area")
        severity = obs.get("severity", "N/A")
        issue = obs.get("issue", "Not Available")
        reasoning = obs.get("reasoning", "")
        thermal = obs.get("thermal_finding", "")
        img_captions = obs.get("image_captions", [])
        if isinstance(img_captions, str):
            img_captions = [img_captions]

        # Header row: area name + severity badge
        badge = _severity_badge(severity, styles)
        header_data = [[
            Paragraph(f"<b>{idx + 1}. {area}</b>", styles["ObsTitle"]),
            badge
        ]]
        header_tbl = Table(header_data, colWidths=[CONTENT_W - 30 * mm, 28 * mm])
        header_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))

        # Build the entire observation block for page-break protection
        obs_elements = [header_tbl, Spacer(1, 4)]
        obs_elements.append(Paragraph(f"<b>Issue:</b>  {issue}", styles["ObsBody"]))

        if reasoning and reasoning != "Not Available":
            obs_elements.append(Paragraph(f"<b>Assessment:</b>  {reasoning}", styles["ObsBody"]))

        if thermal and thermal != "Not Available":
            obs_elements.append(Paragraph(f"<b>Thermal Finding:</b>  {thermal}", styles["ObsThermal"]))

        # Prepare structured image data for grid layout
        imgs = obs.get("images", [])
        valid_img_data = []
        if isinstance(imgs, list):
            for i, path in enumerate(imgs[:10]):
                if path and path != "Image Not Available":
                    caption = img_captions[i] if i < len(img_captions) else f"{area} — Observation {i + 1}"
                    valid_img_data.append({'path': path, 'caption': caption})

        if valid_img_data:
            # First row (up to 2 images) stays with the text block
            row1 = _make_image_row(valid_img_data[0:2], styles)
            if row1:
                obs_elements.append(Spacer(1, 4))
                obs_elements.append(row1)
            
            els.append(KeepTogether(obs_elements))

            # Subsequent images in rows of 2
            for i in range(2, len(valid_img_data), 2):
                row_tbl = _make_image_row(valid_img_data[i:i+2], styles)
                if row_tbl:
                    els.append(Spacer(1, 2))
                    els.append(KeepTogether([row_tbl]))
        else:
            # No images fallback
            obs_elements.append(Paragraph("<i>Image Not Available</i>", styles["ObsThermal"]))
            els.append(KeepTogether(obs_elements))

        # Separator
        sep = Table([[""]], colWidths=[CONTENT_W])
        sep.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (0, 0), 0.5, BORDER),
            ('TOPPADDING', (0, 0), (0, 0), 6),
            ('BOTTOMPADDING', (0, 0), (0, 0), 8),
        ]))
        els.append(sep)

    # ━━━━━━━━━━━━━━━  SECTION 05: IMPACT SUMMARY TABLE  ━━━━━━━━━━━━━━━
    _section(els, "05", "Impact Summary — Source vs. Symptom", styles)
    els.append(Paragraph(
        "The table below maps each observed damage (negative/impacted side) to its "
        "identified source (positive/exposed side), helping prioritize remediation efforts.",
        styles["Body"]))

    impact_table = ddr_data.get("ImpactSummaryTable", [])
    if isinstance(impact_table, str):
        impact_table = []

    if impact_table:
        tbl_data = [[
            Paragraph("<b>Impacted Area (Symptom)</b>", styles["TableHeader"]),
            Paragraph("<b>Source Area (Root)</b>", styles["TableHeader"]),
        ]]
        for row in impact_table:
            if isinstance(row, dict):
                tbl_data.append([
                    Paragraph(str(row.get("impacted_area", "—")), styles["TableCell"]),
                    Paragraph(str(row.get("source_area", "—")), styles["TableCell"]),
                ])

        if len(tbl_data) > 1:
            impact_tbl = Table(tbl_data, colWidths=[CONTENT_W * 0.5, CONTENT_W * 0.5])
            style_cmds = [
                ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEAD),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
                ('LINEBELOW', (0, 0), (-1, -2), 0.5, BORDER),
                ('LINEBEFORE', (1, 0), (1, -1), 0.5, BORDER),
            ]
            for i in range(1, len(tbl_data)):
                if i % 2 == 0:
                    style_cmds.append(('BACKGROUND', (0, i), (-1, i), TABLE_ALT))
            impact_tbl.setStyle(TableStyle(style_cmds))
            els.append(impact_tbl)
        else:
            els.append(Paragraph("Not Available", styles["Body"]))
    else:
        els.append(Paragraph("Not Available", styles["Body"]))
    els.append(Spacer(1, 10))

    # ━━━━━━━━━━━━━━━  SECTION 06: ROOT CAUSE  ━━━━━━━━━━━━━━━
    _section(els, "06", "Probable Root Cause", styles)
    root_cause = str(ddr_data.get("ProbableRootCause", "Not Available"))
    els.append(Paragraph(root_cause, styles["Body"]))

    # ━━━━━━━━━━━━━━━  SECTION 07: SEVERITY  ━━━━━━━━━━━━━━━
    _section(els, "07", "Severity Assessment", styles)
    sev_text = str(ddr_data.get("SeverityAssessment", "Not Available"))
    els.append(Paragraph(sev_text, styles["Body"]))

    # ━━━━━━━━━━━━━━━  SECTION 08: ACTIONS  ━━━━━━━━━━━━━━━
    _section(els, "08", "Recommended Actions", styles)
    actions = ddr_data.get("RecommendedActions", [])
    if isinstance(actions, str):
        actions = [actions] if actions else []
    if actions:
        for i, action in enumerate(actions):
            els.append(Paragraph(f"<b>{i + 1}.</b>  {action}", styles["BulletItem"]))
    else:
        els.append(Paragraph("Not Available", styles["Body"]))

    # ━━━━━━━━━━━━━━━  SECTION 09: NOTES  ━━━━━━━━━━━━━━━
    _section(els, "09", "Additional Notes", styles)
    notes = str(ddr_data.get("AdditionalNotes", "Not Available"))
    els.append(Paragraph(notes, styles["Body"]))

    # ━━━━━━━━━━━━━━━  SECTION 10: MISSING INFO  ━━━━━━━━━━━━━━━
    _section(els, "10", "Missing or Unclear Information", styles)
    missing = ddr_data.get("MissingOrUnclearInformation", [])
    if isinstance(missing, str):
        missing = [missing] if missing else []
    if missing:
        for item in missing:
            els.append(Paragraph(f"•  {item}", styles["BulletItem"]))
    else:
        els.append(Paragraph("Not Available", styles["Body"]))

    # ━━━━━━━━━━━━━━━  SECTION 11: DISCLAIMER  ━━━━━━━━━━━━━━━
    els.append(PageBreak())
    _section(els, "11", "Limitations & Disclaimer", styles)

    disclaimers = [
        ("DATA AND INFORMATION DISCLAIMER",
         "This property inspection is not an exhaustive inspection of the structure, systems, or "
         "components. The inspection may not reveal all deficiencies. A health checkup helps to "
         "reduce some of the risk involved in the property/structure & premises, but it cannot "
         "eliminate these risks, nor can the inspection anticipate future events or changes in "
         "performance due to changes in use or occupancy."),

        ("SCOPE LIMITATIONS",
         "The inspection addresses only those components and conditions that are present, visible, "
         "and accessible at the time of the inspection. The inspector is not required to move "
         "furnishings or stored items. This is NOT a code compliance inspection and does NOT verify "
         "compliance with manufacturer's installation instructions. The inspection does NOT imply "
         "insurability or warrantability of the structure or its components."),

        ("AI-ASSISTED ANALYSIS",
         "This Detailed Diagnostic Report was generated using AI-assisted analysis of the provided "
         "Inspection Report and Thermal Imaging Report. While the AI model has been configured to "
         "follow industry-standard diagnostic protocols, all findings, severity assessments, and "
         "recommendations should be verified through on-site professional inspection by a qualified "
         "structural engineer or building inspector before any remediation action is taken."),

        ("LIMITATION OF LIABILITY",
         "The inspection report is an opinion of the present condition of the property based on "
         "visual examination. Some conditions may not be observable during inspection. Intermittent "
         "problems may not be obvious as they only happen under certain weather conditions or when "
         "specific fixtures are in use. Any structural cracks noted in this report deserve immediate "
         "attention by a Registered Structural Engineer."),
    ]

    for title, text in disclaimers:
        els.append(Paragraph(title, styles["DisclaimerBold"]))
        els.append(Paragraph(text, styles["Disclaimer"]))
        els.append(Spacer(1, 4))

    # ━━━━━━━━━━━━━━━  END MARK  ━━━━━━━━━━━━━━━
    els.append(Spacer(1, 30))
    els.append(Paragraph(
        "— End of Report —",
        ParagraphStyle("EndMark", fontName="Helvetica-Bold", fontSize=9,
                       textColor=TEXT_MUTED, alignment=TA_CENTER, spaceBefore=20)))

    # Build
    doc.build(els)
    buffer.seek(0)
    size_kb = buffer.getbuffer().nbytes // 1024
    logger.info(f"✅ PDF generated: {size_kb}KB, {len(observations)} observations")
    return buffer
