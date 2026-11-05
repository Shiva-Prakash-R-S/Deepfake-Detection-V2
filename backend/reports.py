import io
import os
from datetime import datetime, timezone
from PIL import Image as PILImage

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    KeepTogether,
    HRFlowable
)

from backend.storage import resolve_stored_image_path


def generate_pdf_report(prediction_record, user) -> io.BytesIO:
    """
    Generate a professional forensic authenticity PDF report for a prediction record.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=36,
        bottomMargin=36
    )

    story = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a")
    )
    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b")
    )
    section_title = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155")
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748b")
    )

    # 1. Header & Branding
    story.append(Paragraph("🛡️ DeepFake Detection V2", title_style))
    story.append(Paragraph("AI-Powered Image Authenticity Forensic Report", subtitle_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3b82f6"), spaceAfter=15))

    # 2. Executive Summary / Verdict Banner
    is_fake = prediction_record.predicted_label.upper() == "FAKE"
    banner_bg = colors.HexColor("#fee2e2") if is_fake else colors.HexColor("#dcfce7")
    banner_border = colors.HexColor("#ef4444") if is_fake else colors.HexColor("#10b981")
    verdict_text_color = colors.HexColor("#b91c1c") if is_fake else colors.HexColor("#15803d")
    verdict_title = "SUSPECTED DEEPFAKE (AI GENERATED)" if is_fake else "AUTHENTIC (REAL IMAGE)"

    verdict_style = ParagraphStyle(
        "VerdictText",
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=verdict_text_color,
        alignment=1
    )
    verdict_sub = ParagraphStyle(
        "VerdictSub",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=verdict_text_color,
        alignment=1
    )

    verdict_data = [
        [Paragraph(f"FINAL VERDICT: {verdict_title}", verdict_style)],
        [Paragraph(f"Confidence Score: {prediction_record.confidence:.2f}% (Threshold: {prediction_record.threshold_used:.2f})", verdict_sub)]
    ]
    verdict_table = Table(verdict_data, colWidths=[532])
    verdict_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), banner_bg),
        ("BOX", (0, 0), (-1, -1), 1.5, banner_border),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(verdict_table)
    story.append(Spacer(1, 15))

    # 3. Two-Column Layout: Embedded Image & Case Metadata
    story.append(Paragraph("Inspection Subject & Details", section_title))

    # Prepare Image flowable
    img_flowable = None
    try:
        abs_img_path = resolve_stored_image_path(prediction_record.stored_image_path)
        with PILImage.open(abs_img_path) as pil_im:
            w_orig, h_orig = pil_im.size

        # Fit within 220 x 200 box
        max_w, max_h = 220, 190
        scale = min(max_w / w_orig, max_h / h_orig, 1.0)
        img_flowable = RLImage(abs_img_path, width=w_orig * scale, height=h_orig * scale)
    except Exception:
        img_flowable = Paragraph("<em>[Image file unavailable]</em>", body_style)

    created_str = prediction_record.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")

    meta_rows = [
        [Paragraph("<b>Report ID:</b>", body_style), Paragraph(f"#{prediction_record.id}", body_style)],
        [Paragraph("<b>Timestamp:</b>", body_style), Paragraph(created_str, body_style)],
        [Paragraph("<b>Analyst:</b>", body_style), Paragraph(f"{user.full_name} ({user.email})", body_style)],
        [Paragraph("<b>Original File:</b>", body_style), Paragraph(prediction_record.original_filename, body_style)],
        [Paragraph("<b>Resolution:</b>", body_style), Paragraph(f"{prediction_record.image_width} × {prediction_record.image_height} px", body_style)],
        [Paragraph("<b>Format:</b>", body_style), Paragraph(prediction_record.image_format, body_style)],
        [Paragraph("<b>Face Detected:</b>", body_style), Paragraph("Yes (Cropped & Aligned)" if prediction_record.face_detected else "No (Full image analyzed)", body_style)],
        [Paragraph("<b>Latency:</b>", body_style), Paragraph(f"{prediction_record.inference_time_ms:.1f} ms", body_style)],
    ]
    meta_table = Table(meta_rows, colWidths=[90, 200])
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))

    two_col_table = Table([[img_flowable, meta_table]], colWidths=[232, 300])
    two_col_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("RIGHTPADDING", (0, 0), (0, 0), 10),
    ]))
    story.append(two_col_table)
    story.append(Spacer(1, 15))

    # 4. Statistical Metrics Table
    story.append(Paragraph("Forensic Probability Distribution", section_title))
    prob_data = [
        [
            Paragraph("<b>Classification</b>", body_style),
            Paragraph("<b>Score / Probability</b>", body_style),
            Paragraph("<b>Decision State</b>", body_style)
        ],
        [
            Paragraph("Deepfake Probability", body_style),
            Paragraph(f"{prediction_record.probability_fake:.2f}%", body_style),
            Paragraph("FLAGGED" if is_fake else "Negative", body_style)
        ],
        [
            Paragraph("Authentic Probability", body_style),
            Paragraph(f"{prediction_record.probability_real:.2f}%", body_style),
            Paragraph("Negative" if is_fake else "VERIFIED", body_style)
        ],
        [
            Paragraph("Model Architecture", body_style),
            Paragraph(f"{prediction_record.model_name} {prediction_record.model_version}", body_style),
            Paragraph("Spatial + 2D FFT Fusion", body_style)
        ],
    ]
    prob_table = Table(prob_data, colWidths=[180, 160, 192])
    prob_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(prob_table)
    story.append(Spacer(1, 12))

    # 5. Integrity & Verification
    story.append(Paragraph("Cryptographic Fingerprint", section_title))
    hash_p = Paragraph(f"<b>SHA-256 Digest:</b> <font face='Courier' size='8'>{prediction_record.image_sha256}</font>", body_style)
    story.append(hash_p)
    story.append(Spacer(1, 15))

    # 6. Disclaimer
    disclaimer_text = (
        "<b>Notice & Methodological Limitation:</b> This report was generated automatically by "
        "DeepFake Detection V2 using a hybrid dual-branch deep learning pipeline comprising an "
        "EfficientNet-B0 spatial backbone and a 2D Fast Fourier Transform (FFT) frequency spectrum CNN. "
        "Probabilistic scores indicate mathematical consistency with known synthetic generation patterns. "
        "Outputs should be utilized as investigative screening assistance rather than absolute judicial evidence."
    )
    story.append(KeepTogether([
        HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#cbd5e1"), spaceAfter=6),
        Paragraph(disclaimer_text, disclaimer_style)
    ]))

    doc.build(story)
    buffer.seek(0)
    return buffer
