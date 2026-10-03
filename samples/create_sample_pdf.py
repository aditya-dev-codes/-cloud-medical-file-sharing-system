# Helper script to create a clean, valid sample PDF medical report for testing
from pathlib import Path

def create_sample_pdf(filepath):
    """Generates a standard valid PDF 1.4 file containing sample patient laboratory data."""
    text_content = (
        "BT\n"
        "/F1 16 Tf\n"
        "50 720 Td\n"
        "(METROPOLITAN HOSPITAL - CLINICAL REPORT) Tj\n"
        "/F1 11 Tf\n"
        "0 -30 Td\n"
        "(Patient Name: Alex Morgan       DOB: 14-May-1998) Tj\n"
        "0 -20 Td\n"
        "(Attending Physician: Dr. Robert Vance, M.D.) Tj\n"
        "0 -25 Td\n"
        "(ALLERGIES: Penicillin - Severe Anaphylaxis, Peanuts) Tj\n"
        "0 -20 Td\n"
        "(MEDICATIONS: Metformin 500mg BID, Lisinopril 10mg QD, Atorvastatin 20mg) Tj\n"
        "0 -20 Td\n"
        "(DIAGNOSIS: Type 2 Diabetes Mellitus, Mild Hypertension) Tj\n"
        "0 -20 Td\n"
        "(PREVIOUS SURGERIES: Open Appendectomy 2020) Tj\n"
        "0 -25 Td\n"
        "(TEST RESULTS:) Tj\n"
        "0 -18 Td\n"
        "(- Fasting Blood Glucose: 138 mg/dL [HIGH]) Tj\n"
        "0 -18 Td\n"
        "(- HbA1c: 7.2 % [ELEVATED]) Tj\n"
        "0 -18 Td\n"
        "(- Blood Pressure: 132/84 mmHg) Tj\n"
        "0 -30 Td\n"
        "(CLINICAL NOTE: Continue current anti-hyperglycemic regimen. Absolute allergy to Penicillin.) Tj\n"
        "ET"
    )
    
    stream_bytes = text_content.encode('latin1')
    stream_len = len(stream_bytes)

    objects = []
    # obj 1: Catalog
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    # obj 2: Pages
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    # obj 3: Page
    objects.append(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n")
    # obj 4: Content Stream
    stream_header = f"4 0 obj\n<< /Length {stream_len} >>\nstream\n".encode('latin1')
    stream_footer = b"\nendstream\nendobj\n"
    objects.append(stream_header + stream_bytes + stream_footer)
    # obj 5: Font
    objects.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = [0]
    current_pos = len(header)

    body = b""
    for obj in objects:
        offsets.append(current_pos)
        body += obj
        current_pos += len(obj)

    xref_pos = current_pos
    xref = f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode('latin1')
    for offset in offsets[1:]:
        xref += f"{offset:010d} 00000 n \n".encode('latin1')

    trailer = f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode('latin1')

    with open(filepath, 'wb') as f:
        f.write(header + body + xref + trailer)

if __name__ == '__main__':
    out_file = Path(__file__).parent / 'sample_lab_report.pdf'
    create_sample_pdf(out_file)
    print(f"Generated clean sample PDF at: {out_file}")
