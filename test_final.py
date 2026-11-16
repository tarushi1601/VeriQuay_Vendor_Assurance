import unittest,tempfile
from pathlib import Path
from scenarios import definitions,generate_documents
from workflow import demo
from engine import history,events
class IntegrationTests(unittest.TestCase):
 def test_all_scenarios(self):
  expected=['Approved','Pending','Pending','Pending','Pending','Pending','Rejected','Pending']
  for (name,_),status in zip(definitions().items(),expected):
   with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
    r,pdf=demo(name,Path(d)/'test.db')
    self.assertEqual(r['status'],status,r['reason'])
    self.assertGreater(len(pdf),100)
    self.assertGreaterEqual(len(r['steps']),8)
    self.assertGreaterEqual(len(history(Path(d)/'test.db')),1)
    if 'Bank switch' in name:self.assertEqual(len(events(Path(d)/'test.db')),1)
    if 'PDF tax mismatch' in name:self.assertIn('PDF/form mismatch',r['reason'])
 def test_pdf_pack(self):
  with tempfile.TemporaryDirectory() as d:
   generate_documents(d)
   self.assertEqual(len(list(Path(d).glob('*.pdf'))),8)
if __name__=='__main__':unittest.main()
