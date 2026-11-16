import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from io import BytesIO
from document_intelligence import extract_pdf
from engine import communication_plan, followup
from workflow import demo

class EnhancementsTests(unittest.TestCase):
    def test_live_callbacks_emit_before_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            events=[]
            result,_=demo('01 Happy path',Path(folder)/'case.db',on_stage=events.append)
            self.assertEqual(result['status'],'Approved')
            self.assertEqual(events[0]['stage'],'Intake received')
            self.assertEqual(events[-1]['stage'],'Audit record committed')
            self.assertTrue(any(s['stage']=='PDF document review' for s in events))
            self.assertGreaterEqual(len(events),10)

    def test_duplicate_is_internal_only(self):
        with tempfile.TemporaryDirectory() as folder:
            result,_=demo('03 Duplicate identity',Path(folder)/'case.db')
            plan=communication_plan(result,'Orion')
            self.assertFalse(plan['vendor_actions'])
            self.assertTrue(plan['internal_actions'])
            self.assertIn('No action is required',followup(result,'Orion'))

    def test_mismatch_requests_corrected_document(self):
        with tempfile.TemporaryDirectory() as folder:
            result,_=demo('06 PDF tax mismatch',Path(folder)/'case.db')
            plan=communication_plan(result,'Cedar')
            self.assertIn('tax id',plan['vendor_actions'][0])

    def test_rejected_email_is_not_pending(self):
        with tempfile.TemporaryDirectory() as folder:
            result,_=demo('07 Confirmed disqualification',Path(folder)/'case.db')
            message=followup(result,'Blocked')
            self.assertNotIn('currently Pending',message)
            self.assertIn('cannot be approved',message)

    def test_alternate_labels_and_dates(self):
        b=BytesIO();c=canvas.Canvas(b,pagesize=A4)
        for i,line in enumerate(['Registered Business Name: Maple Fabricators Pvt Ltd',
                                 'GST Registration Number: 27ABCDE1234F1Z5',
                                 'Beneficiary Name: Maple Fabricators Pvt Ltd',
                                 'Valid Through: 31 Dec 2027']):
            c.drawString(40,780-i*40,line)
        c.save()
        doc=extract_pdf(b.getvalue(),enable_ocr=False)
        self.assertEqual(doc['fields']['certificate_expiry'],'2027-12-31')
        self.assertEqual(doc['coverage'],1.)

if __name__=='__main__':unittest.main()
