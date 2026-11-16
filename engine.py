"""VeriQuay: auditable, deterministic vendor onboarding rules."""
import hashlib
import json
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

DB_DEFAULT = Path(__file__).with_name('vendorflow.db')
REQUIRED = ('legal_name', 'country', 'tax_id', 'bank_holder', 'bank_account', 'email', 'certificate_expiry')

def normalize_name(value):
    value = re.sub(r'[^a-z0-9 ]', ' ', (value or '').lower())
    return ' '.join(w for w in value.split() if w not in {'pvt','private','ltd','limited','inc','llc','the'})

def fingerprint(value):
    return hashlib.sha256(str(value).strip().upper().encode()).hexdigest()

def connect(db=DB_DEFAULT):
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.executescript('''
      CREATE TABLE IF NOT EXISTS vendors (
        id INTEGER PRIMARY KEY AUTOINCREMENT, legal_name TEXT NOT NULL,
        country TEXT, tax_hash TEXT, bank_hash TEXT, bank_holder TEXT,
        bank_last4 TEXT, status TEXT, updated_at TEXT);
      CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, vendor_id INTEGER,
        created_at TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL,
        flags TEXT NOT NULL, steps TEXT NOT NULL, input_snapshot TEXT NOT NULL,
        FOREIGN KEY(vendor_id) REFERENCES vendors(id));
      CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, vendor_id INTEGER NOT NULL,
        created_at TEXT NOT NULL, event_type TEXT NOT NULL, details TEXT NOT NULL,
        FOREIGN KEY(vendor_id) REFERENCES vendors(id));
    ''')
    conn.commit()
    return conn

def evaluate(payload, conn, vendor_id=None, today=None, document_checks=None, document_error=None, confirmed_block=False, on_stage=None):
    """Return a traceable decision. No real-world identity verification is claimed."""
    today = today or date.today()
    p = {k: str(v or '').strip() for k, v in payload.items()}
    class TracedSteps(list):
        def append(self, step):
            super().append(step)
            if on_stage: on_stage(step)
    steps, flags = TracedSteps(), []
    missing = [k for k in REQUIRED if not p.get(k)]
    steps.append({'stage':'Completeness', 'passed':not missing,
                  'detail':'All required fields present' if not missing else 'Missing: '+', '.join(missing)})
    if missing: flags.append('Missing required fields: '+', '.join(missing))

    email_valid = bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', p.get('email','')))
    steps.append({'stage':'Contact format', 'passed':email_valid, 'detail':'Email format valid' if email_valid else 'Invalid email format'})
    if not email_valid: flags.append('Invalid email format')

    # Tax rules are illustrative and do not establish government registration.
    country = p.get('country','').upper()
    tax = p.get('tax_id','').upper().replace(' ','')
    tax_ok = bool(tax)
    if country == 'IN':
        tax_ok = bool(re.fullmatch(r'\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]',tax))
    steps.append({'stage':'Tax ID format', 'passed':tax_ok, 'detail':'Format passes configured checks' if tax_ok else 'Tax ID format invalid or missing'})
    if not tax_ok: flags.append('Invalid tax ID format')

    try:
        expiry = date.fromisoformat(p.get('certificate_expiry',''))
        cert_ok = expiry >= today
    except ValueError:
        cert_ok = False
    steps.append({'stage':'Certificate expiry', 'passed':cert_ok,
                  'detail':f'Certificate expiry: {p.get("certificate_expiry") or "missing"}; evaluated {today.isoformat()}'})
    if not cert_ok: flags.append('Mandatory certificate missing, invalid, or expired')

    name_match = normalize_name(p.get('legal_name')) == normalize_name(p.get('bank_holder'))
    subsidiary = p.get('relationship_document','').lower() in ('yes','true','provided')
    steps.append({'stage':'Bank holder consistency', 'passed':name_match,
                  'detail':'Legal and bank names match' if name_match else ('Names differ; relationship evidence supplied, requires human verification' if subsidiary else 'Names differ; relationship evidence needed')})
    if not name_match: flags.append('Bank holder mismatch — human verification required'+(' (relationship evidence supplied)' if subsidiary else ''))

    tax_hash = fingerprint(tax) if tax else None
    bank_hash = fingerprint(p.get('bank_account')) if p.get('bank_account') else None
    duplicate_rows = conn.execute('SELECT id,legal_name,tax_hash,bank_hash FROM vendors WHERE id != ?',(vendor_id or -1,)).fetchall()
    duplicates = [r for r in duplicate_rows if (tax_hash and r['tax_hash']==tax_hash) or (bank_hash and r['bank_hash']==bank_hash)]
    steps.append({'stage':'Duplicate detection', 'passed':not duplicates,
                  'detail':'No matching vendor fingerprints' if not duplicates else 'Potential duplicate record IDs: '+', '.join(str(r['id']) for r in duplicates)})
    if duplicates: flags.append('Possible duplicate vendor — review before approval')

    changed = False
    if vendor_id is not None:
        existing = conn.execute('SELECT bank_hash FROM vendors WHERE id=?',(vendor_id,)).fetchone()
        if existing is None: raise ValueError('Unknown vendor ID')
        changed = bool(bank_hash and existing['bank_hash'] and existing['bank_hash'] != bank_hash)
    steps.append({'stage':'Bank change control', 'passed':not changed,
                  'detail':'Bank account changed since prior submission — independent verification required' if changed else 'No previously recorded bank account change'})
    if changed: flags.append('Bank account changed — automatic approval blocked')

    if document_error:
        steps.append({'stage':'PDF document review','passed':False,'detail':document_error})
        flags.append('Document could not be validated — human review required')
    elif document_checks is not None:
        mismatches=[c for c in document_checks if not c['matches']]
        if not document_checks:
            steps.append({'stage':'PDF document review','passed':False,'detail':'No supported labeled fields found in PDF; manual document review required'})
            flags.append('PDF lacks extractable verification fields — manual review required')
        else:
            steps.append({'stage':'PDF document review','passed':not mismatches,'detail':f'{len(document_checks)} fields compared; {len(mismatches)} mismatches: '+(', '.join(c['field'] for c in mismatches) if mismatches else 'none')})
            if mismatches: flags.append('PDF/form mismatch: '+', '.join(c['field'] for c in mismatches))

    # Missing or remediable issues are Pending. Rejection is reserved for policy-defined confirmed disqualification.
    if confirmed_block:
        steps.append({'stage':'Confirmed internal policy block','passed':False,'detail':'Synthetic internal blocklist entry was explicitly supplied; reject under demo policy.'})
        flags.append('Confirmed internal policy disqualification (synthetic test data)')
    status = 'Rejected' if confirmed_block else ('Pending' if flags else 'Approved')
    reason = '; '.join(flags) if flags else 'All configured checks passed; approved under demo policy (not external verification).'
    steps.append({'stage':'Decision', 'passed':status=='Approved', 'detail':f'{status}: {reason}'})
    return {'status':status, 'reason':reason, 'flags':flags, 'steps':steps, 'bank_changed':changed}

def submit(payload, db=DB_DEFAULT, vendor_id=None, today=None, document_checks=None, document_error=None, confirmed_block=False, on_stage=None):
    conn = connect(db)
    try:
        conn.execute('BEGIN IMMEDIATE')
        result = evaluate(payload,conn,vendor_id,today,document_checks,document_error,confirmed_block,on_stage)
        now = datetime.now(timezone.utc).isoformat()
        tax = str(payload.get('tax_id') or '').upper().replace(' ','')
        bank = str(payload.get('bank_account') or '').strip()
        fields = (str(payload.get('legal_name') or ''),str(payload.get('country') or ''),fingerprint(tax) if tax else None,
                  fingerprint(bank) if bank else None,str(payload.get('bank_holder') or ''),bank[-4:],result['status'],now)
        if vendor_id is None:
            cur = conn.execute('INSERT INTO vendors(legal_name,country,tax_hash,bank_hash,bank_holder,bank_last4,status,updated_at) VALUES(?,?,?,?,?,?,?,?)',fields)
            vendor_id = cur.lastrowid
        else:
            conn.execute('UPDATE vendors SET legal_name=?,country=?,tax_hash=?,bank_hash=?,bank_holder=?,bank_last4=?,status=?,updated_at=? WHERE id=?',(*fields,vendor_id))
        # Store only redacted input; never persist raw bank account or tax ID.
        snapshot = {k:v for k,v in payload.items() if k not in ('bank_account','tax_id')}
        snapshot['bank_last4'] = bank[-4:]
        snapshot['tax_id_masked'] = ('*' * max(0,len(tax)-4)) + tax[-4:]
        conn.execute('INSERT INTO runs(vendor_id,created_at,status,reason,flags,steps,input_snapshot) VALUES(?,?,?,?,?,?,?)',
                     (vendor_id,now,result['status'],result['reason'],json.dumps(result['flags']),json.dumps(result['steps']),json.dumps(snapshot)))
        if result['bank_changed']:
            conn.execute('INSERT INTO events(vendor_id,created_at,event_type,details) VALUES(?,?,?,?)',
                         (vendor_id,now,'BANK_ACCOUNT_CHANGED','Account fingerprint changed; independent verification required'))
        conn.commit()
        return {**result,'vendor_id':vendor_id}
    except Exception:
        conn.rollback()
        raise
    finally: conn.close()

def history(db=DB_DEFAULT):
    conn=connect(db)
    try: return [dict(r) for r in conn.execute('SELECT id,vendor_id,created_at,status,reason FROM runs ORDER BY id DESC').fetchall()]
    finally: conn.close()

def vendors(db=DB_DEFAULT):
    conn=connect(db)
    try: return [dict(r) for r in conn.execute('SELECT id,legal_name,country,bank_last4,status,updated_at FROM vendors ORDER BY id DESC').fetchall()]
    finally: conn.close()

def events(db=DB_DEFAULT):
    conn=connect(db)
    try: return [dict(r) for r in conn.execute('SELECT * FROM events ORDER BY id DESC').fetchall()]
    finally: conn.close()

def communication_plan(result, legal_name):
    """Separate actionable vendor requests from internal verification tasks."""
    flags = result.get('flags', [])
    vendor_actions, internal_actions = [], []
    for flag in flags:
        f = flag.lower()
        if 'duplicate' in f:
            internal_actions.append('Check the matching vendor record and confirm whether this is a duplicate or an authorized update.')
        elif 'bank account changed' in f:
            internal_actions.append('Independently verify the new bank details using a trusted contact channel before releasing payments.')
        elif 'bank holder mismatch' in f:
            vendor_actions.append('Provide evidence of the relationship between the legal entity and bank account holder, or correct the bank details.')
            internal_actions.append('Verify the legal relationship and account ownership before approval.')
        elif 'pdf/form mismatch' in f:
            fields = flag.split(':', 1)[-1].strip().replace('_', ' ')
            vendor_actions.append(f'Correct the conflicting {fields} information or upload a document that matches the submitted form.')
        elif 'certificate' in f:
            vendor_actions.append('Upload a current compliance certificate and confirm its expiry date.')
        elif 'tax id format' in f:
            vendor_actions.append('Correct the tax registration number to the expected format for the selected country.')
        elif 'email format' in f:
            vendor_actions.append('Provide a valid contact email address.')
        elif 'missing required fields' in f:
            vendor_actions.append('Complete all missing required fields listed in the validation results.')
        elif 'document' in f or 'pdf lacks' in f:
            vendor_actions.append('Upload a readable supporting PDF containing the company name, tax ID, bank holder, and certificate expiry.')
            internal_actions.append('Review the supporting document manually if automated extraction is unavailable.')
        elif 'disqualification' in f:
            internal_actions.append('Review the confirmed internal policy block and communicate the decision through the approved compliance channel.')
        else:
            internal_actions.append('Investigate: ' + flag)
    return {'vendor_actions': list(dict.fromkeys(vendor_actions)),
            'internal_actions': list(dict.fromkeys(internal_actions))}

def followup(result, legal_name):
    status = result['status']
    plan = communication_plan(result, legal_name)
    if status == 'Approved':
        return (f'Subject: Vendor onboarding — approved\n\nHello {legal_name},\n\n'
                'Your submission has passed our configured onboarding checks and is marked Approved. '
                'This is a workflow decision and does not represent external bank or government verification.\n\n'
                'Regards,\nVendor Operations')
    if status == 'Rejected':
        return (f'Subject: Vendor onboarding — application decision\n\nHello {legal_name},\n\n'
                'Your application cannot be approved under our current onboarding policy. '
                'Please contact Vendor Operations if you would like clarification or a formal review.\n\n'
                'Regards,\nVendor Operations')
    if not plan['vendor_actions']:
        return (f'Subject: Vendor onboarding — under review\n\nHello {legal_name},\n\n'
                'Thank you for your submission. Your application is Pending while our procurement team '
                'completes additional internal verification. No action is required from you at this time. '
                'We will contact you if more information is needed.\n\nRegards,\nVendor Operations')
    actions = '\n'.join(f'- {a}' for a in plan['vendor_actions'])
    return (f'Subject: Action requested — vendor onboarding\n\nHello {legal_name},\n\n'
            'Your application is currently Pending. To proceed, please address the following:\n'
            f'{actions}\n\nWe will review the updated submission once received.\n\nRegards,\nVendor Operations')
