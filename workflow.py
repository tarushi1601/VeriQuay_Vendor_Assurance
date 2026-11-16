"""Real staged execution: callback fires when each actual check completes."""
from engine import submit
from document_intelligence import extract_pdf, compare_document
from scenarios import definitions, pdf_bytes

def execute(payload, db, vendor_id=None, pdf=None, confirmed_block=False, on_stage=None):
    def emit(stage, passed, detail):
        if on_stage: on_stage({'stage': stage, 'passed': passed, 'detail': detail})
    emit('Intake received', True, 'Submission received for processing')
    checks, err, info = None, None, None
    if pdf is not None:
        emit('Document ingestion', True, f'PDF received ({len(pdf):,} bytes)')
        try:
            info = extract_pdf(pdf)
            if not info['text_available'] and not info['ocr_used']:
                err = 'No readable document text; OCR was unavailable or could not extract usable text.'
            else: checks = compare_document(info['fields'], payload)
            emit('Document extraction', bool(info['fields']),
                 f'{len(info["fields"])} fields extracted via {info["extraction_method"]}; coverage {info["coverage"]:.0%}')
        except ValueError as exc:
            err = str(exc)
            emit('Document extraction', False, err)
    else:
        emit('Document ingestion', False, 'No PDF attached; supporting evidence must be reviewed')
        err = 'Supporting verification PDF was not provided.'
    result = submit(payload, db=db, vendor_id=vendor_id, document_checks=checks,
                    document_error=err, confirmed_block=confirmed_block, on_stage=on_stage)
    emit('Audit record committed', True, f'Vendor record #{result["vendor_id"]} stored')
    return {**result, 'document': info, 'document_checks': checks or [], 'document_error': err}

def demo(name, db, on_stage=None):
    s = definitions()[name]
    p = dict(s['payload'])
    prior_ids = []
    for old in s.get('prior', []):
        prior_ids.append(execute(old, db, pdf=pdf_bytes(old))['vendor_id'])
    if s.get('update'): p.update(s['changes'])
    if s.get('unreadable'):
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from io import BytesIO
        b = BytesIO(); c = canvas.Canvas(b, pagesize=A4)
        c.drawString(50, 700, 'Unstructured attachment with no fields'); c.save(); pdf = b.getvalue()
    else: pdf = pdf_bytes(s['payload'], name, overrides=s.get('pdf_overrides'))
    return execute(p, db, vendor_id=prior_ids[0] if s.get('update') else None,
                   pdf=pdf, confirmed_block=s.get('blocked', False), on_stage=on_stage), pdf
