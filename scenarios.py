"""Synthetic, reproducible demonstrations with a fresh database per demo run."""
from datetime import date,timedelta
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO

TODAY=date.today()
def base():
 return dict(legal_name='Aster Technologies Pvt Ltd',country='IN',tax_id='27ABCDE1234F1Z5',bank_holder='Aster Technologies Pvt Ltd',bank_account='1111222233334444',email='accounts@aster.example',certificate_expiry=(date.today()+timedelta(days=180)).isoformat(),relationship_document='no')

def pdf_bytes(payload, title='Vendor verification evidence', overrides=None, scan=False):
 p={**payload,**(overrides or {})}; buf=BytesIO(); c=canvas.Canvas(buf,pagesize=A4)
 c.setTitle(title); c.setFont('Helvetica-Bold',18);c.drawString(55,775,title)
 c.setFont('Helvetica',10);c.drawString(55,750,'SYNTHETIC TEST DOCUMENT - NOT REAL VERIFICATION')
 for i,(label,key) in enumerate([('Legal Company Name','legal_name'),('Tax ID','tax_id'),('Bank Account Holder','bank_holder'),('Certificate Expiry','certificate_expiry')]):
  c.drawString(55,705-i*33,f'{label}: {p.get(key,"")}')
 c.setFont('Helvetica',9);c.drawString(55,540,'Prepared for VeriQuay demonstration. All entities are fictional.')
 c.save();return buf.getvalue()

def definitions():
 p=base(); expired={**p,'legal_name':'Expired Materials Pvt Ltd','tax_id':'29ABCDE1234F1Z5','bank_holder':'Expired Materials Pvt Ltd','bank_account':'2222333344445555','email':'ap@expired.example','certificate_expiry':(date.today()-timedelta(days=3)).isoformat()}
 subsidiary={**p,'legal_name':'Nova India Pvt Ltd','tax_id':'07ABCDE1234F1Z5','bank_holder':'Nova Global Holdings','bank_account':'3333444455556666','email':'finance@nova.example','relationship_document':'yes'}
 switch={**p,'legal_name':'Summit Logistics Pvt Ltd','tax_id':'06ABCDE1234F1Z5','bank_holder':'Summit Logistics Pvt Ltd','bank_account':'4444555566667777','email':'ap@summit.example'}
 dup={**p,'legal_name':'Orion Supplies Pvt Ltd','tax_id':'24ABCDE1234F1Z5','bank_holder':'Orion Supplies Pvt Ltd','bank_account':'5555666677778888','email':'billing@orion.example'}
 conflict={**p,'legal_name':'Cedar Industrial Pvt Ltd','tax_id':'33ABCDE1234F1Z5','bank_holder':'Cedar Industrial Pvt Ltd','bank_account':'6666777788889999','email':'finance@cedar.example'}
 blocked={**p,'legal_name':'Blocked Example Pvt Ltd','tax_id':'19ABCDE1234F1Z5','bank_holder':'Blocked Example Pvt Ltd','bank_account':'7777888899990000','email':'admin@blocked.example'}
 return {
 '01 Happy path':dict(description='All supplied information agrees. Expected Approved.',payload=p),
 '02 Bank switch':dict(description='First approve a vendor, then change its account; expected Pending and audit event.',payload=switch,prior=[switch],update=True,changes={'bank_account':'9999000011112222'}),
 '03 Duplicate identity':dict(description='A new vendor uses an existing vendor tax ID despite a different name; expected Pending.',payload={**dup,'legal_name':'Orion Trading Services','bank_holder':'Orion Trading Services','bank_account':'9999111122223333','email':'new@orion.example'},prior=[dup]),
 '04 Expired certificate':dict(description='A complete document is expired; expected Pending.',payload=expired),
 '05 Subsidiary mismatch':dict(description='Bank holder is a parent entity; evidence is declared, but human verification remains required.',payload=subsidiary),
 '06 PDF tax mismatch':dict(description='Uploaded PDF tax ID conflicts with form; expected Pending.',payload=conflict,pdf_overrides={'tax_id':'33ABCDE1234F1Z9'}),
 '07 Confirmed disqualification':dict(description='Synthetic confirmed internal blocklist decision; expected Rejected. No external registry check.',payload=blocked,blocked=True),
 '08 Unreadable PDF':dict(description='No usable verification fields in uploaded PDF; expected Pending for manual review.',payload={**p,'legal_name':'Unclear Documents Pvt Ltd','tax_id':'09ABCDE1234F1Z5','bank_holder':'Unclear Documents Pvt Ltd','bank_account':'8888999900001111','email':'docs@unclear.example'},unreadable=True),
 }

def generate_documents(directory):
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
 for name,s in definitions().items():
  if s.get('unreadable'):
   b=BytesIO();c=canvas.Canvas(b,pagesize=A4);c.drawString(50,700,'Unstructured supporting attachment: no verified fields');c.save(); data=b.getvalue()
  else:data=pdf_bytes(s['payload'],name,overrides=s.get('pdf_overrides'))
  (directory/(name.replace(' ','_').lower()+'.pdf')).write_bytes(data)
