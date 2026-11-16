"""Document extraction with flexible layouts, optional OCR, and traceable comparisons.

OCR needs pytesseract + Pillow and the Tesseract executable installed separately.
No authentication of official certificates or external registry lookup is performed.
"""
import re
from datetime import datetime
import os
import pytesseract

TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

if os.path.isfile(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
else:
    print("Tesseract executable not found:", TESSERACT_PATH)

LABELS = {
    'legal_name': r'(?:legal\s*(?:company|business|entity)?\s*name|registered\s*(?:company|business)?\s*name|company\s*name|business\s*name|entity\s*name)',
    'tax_id': r'(?:tax\s*(?:registration\s*)?(?:id|number|no\.?|identifier)|gstin|gst\s*(?:registration\s*)?(?:number|no\.?))',
    'bank_holder': r'(?:bank\s*(?:account\s*)?holder(?:\s*name)?|account\s*holder(?:\s*name)?|beneficiary\s*name)',
    'certificate_expiry': r'(?:certificate\s*(?:expiry|expiration|validity)|expir(?:y|ation)\s*date|valid\s*(?:until|through|to)|expires\s*on)',
}
DATE_PATTERNS = ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d %b %Y', '%d %B %Y', '%b %d, %Y', '%B %d, %Y', '%Y/%m/%d')

def _date_value(s):
    s = re.sub(r'\s+', ' ', s).strip().rstrip(' .')
    for fmt in DATE_PATTERNS:
        try: return datetime.strptime(s, fmt).date().isoformat()
        except ValueError: pass
    return None

def _read_fields(text):
    fields, evidence = {}, {}
    lines = [re.sub(r'\s+', ' ', x).strip() for x in text.splitlines() if x.strip()]
    for idx, line in enumerate(lines):
        for key, label in LABELS.items():
            if key in fields: continue
            m = re.search(r'^\s*(?:' + label + r')\s*(?:[:=\-–]|\s{2,})\s*(.*)$', line, re.I)
            if not m:
                # Support stacked key/value labels in common exported forms.
                if re.fullmatch(r'(?:' + label + r')\s*:?\s*', line, re.I) and idx + 1 < len(lines):
                    value = lines[idx + 1]
                else: continue
            else: value = m.group(1).strip()
            if not value: continue
            if key == 'certificate_expiry':
                parsed = _date_value(value)
                if not parsed: continue
                value = parsed
            elif key == 'tax_id':
                value = re.sub(r'[^A-Za-z0-9]', '', value).upper()
            fields[key] = value
            evidence[key] = {'source_line': idx + 1, 'snippet': line[:160]}
    return fields, evidence

def extract_pdf(data: bytes, enable_ocr=True):
    if not data or len(data) > 5_000_000: raise ValueError('PDF must be between 1 byte and 5 MB.')
    if not data.startswith(b'%PDF'): raise ValueError('Uploaded file is not a valid PDF.')
    try:
        import fitz
        doc = fitz.open(stream=data, filetype='pdf')
        if doc.is_encrypted: raise ValueError('Password-protected PDFs are not supported.')
        if doc.page_count > 15: raise ValueError('PDF exceeds the 15-page limit.')
        pages = [page.get_text(sort=True) for page in doc]
        raw_text = '\n'.join(pages)
        fields, evidence = _read_fields(raw_text)
        ocr_used, ocr_available, ocr_error = False, None, None
        # OCR only pages where embedded text did not yield useful fields; do not
        # invent fields from visual appearance or silently claim OCR succeeded.
        if enable_ocr and len(fields) < len(LABELS):
            try:
                import pytesseract
                from PIL import Image
                pytesseract.get_tesseract_version()
                ocr_available = True
                for i, page in enumerate(doc):
                    if len(fields) == len(LABELS): break
                    if len(pages[i].strip()) > 100 and fields: continue
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), alpha=False)
                    im = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
                    scanned = pytesseract.image_to_string(im, config='--psm 6')
                    if scanned.strip():
                        ocr_used = True
                        ocr_fields, ocr_evidence = _read_fields(scanned)
                        for key, value in ocr_fields.items():
                            if key not in fields:
                                fields[key] = value
                                evidence[key] = {**ocr_evidence[key], 'page': i + 1, 'method': 'OCR'}
            except (ImportError, OSError, RuntimeError, Exception) as exc:
                ocr_available = False
                ocr_error = f'OCR unavailable: {type(exc).__name__}. Install Tesseract OCR and optional Python packages.'
        doc.close()
    except ValueError: raise
    except Exception as exc: raise ValueError('Could not read this PDF. Please upload a valid PDF.') from exc
    return {
        'fields': fields, 'evidence': evidence, 'pages_text_length': len(raw_text),
        'text_available': bool(raw_text.strip()), 'scanned_or_unreadable': not bool(raw_text.strip()),
        'ocr_used': ocr_used, 'ocr_available': ocr_available, 'ocr_error': ocr_error,
        'coverage': len(fields) / len(LABELS), 'missing_fields': [k for k in LABELS if k not in fields],
        'extraction_method': 'OCR + embedded text' if ocr_used else 'embedded text' if raw_text.strip() else 'no readable text',
    }

def _norm(value): return re.sub(r'[^a-z0-9]', '', str(value or '').lower())

def compare_document(extracted, form):
    return [
        {'field': key, 'document_value': value, 'form_value': str(form.get(key, '')).strip(),
         'matches': _norm(value) == _norm(form.get(key, ''))}
        for key, value in extracted.items()
    ]
