"""VeriQuay | Vendor Assurance — auditable, explainable procurement intake."""
import json
import time
from datetime import date, timedelta
from pathlib import Path
import streamlit as st
from engine import history, vendors, events, followup, communication_plan, connect
from workflow import execute, demo
from scenarios import definitions

st.set_page_config(page_title='VeriQuay | Vendor Assurance', page_icon='◈', layout='wide', initial_sidebar_state='expanded')
DB = Path(__file__).with_name('vendorflow.db')
st.markdown('''<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
html,body,[class*="css"],.stApp{font-family:'DM Sans',sans-serif}
.block-container{max-width:1400px;padding-top:1.3rem;padding-bottom:3rem}
h1,h2,h3{font-family:'Manrope',sans-serif;letter-spacing:-.035em}
h1{font-weight:800!important}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#101c33,#162a47 62%,#172c48)}
[data-testid="stSidebar"] *{color:#f1f5fa!important}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:8px;border-radius:9px}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:#253e5d}
[data-testid="stMetric"]{background:var(--secondary-background-color);border:1px solid rgba(126,145,170,.25);border-radius:16px;padding:17px}
[data-testid="stMetricValue"]{font-weight:800;letter-spacing:-.04em}
div[data-testid="stVerticalBlockBorderWrapper"]{border-radius:16px}
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{background:#0c877f;border:0;border-radius:10px;font-weight:700}
.stButton>button[kind="primary"]:hover{background:#0b6f69}
.hero{border-radius:20px;padding:24px 28px;background:linear-gradient(110deg,#122a46,#115a61);color:#fff;margin-bottom:20px}
.hero h1{font-size:2.2rem;margin:0;color:#fff!important}.hero p{margin:.45rem 0 0;color:#d0edf0}
.eyebrow{letter-spacing:.16em;font-size:.72rem;text-transform:uppercase;font-weight:800;color:#89e5da}
.small-note{font-size:.8rem;opacity:.72}
</style>''', unsafe_allow_html=True)

with st.sidebar:
    st.markdown('### ◈ VeriQuay')
    st.caption('VENDOR ASSURANCE WORKSPACE')
    page = st.radio('Workspace', ['Command center', 'Live workflow', 'Vendor intake', 'Decision explorer', 'Demo data management', 'Policy & scope'], label_visibility='collapsed')
    st.divider()
    st.caption('● Deterministic decisions  ·  ● Document evidence')
    st.caption('Synthetic demo only. Never upload real financial or identity documents.')

st.markdown('''<div class="hero"><div class="eyebrow">Procurement intelligence / operations</div><h1>VeriQuay <span style="color:#8fe8dc">◈</span></h1><p>Vendor assurance, from submission to defensible decision.</p></div>''', unsafe_allow_html=True)

def status_ui(status, reason):
    fn = st.success if status == 'Approved' else st.error if status == 'Rejected' else st.warning
    fn(f'**{status.upper()}**  ·  {reason}')

def stage_callback():
    """Actual callback invoked at each execution stage, not replayed afterward."""
    region = st.container(border=True)
    with region:
        st.markdown('#### ● Live execution stream')
        progress = st.progress(0, text='Receiving submission…')
        latest = st.empty()
        trail = st.empty()
    steps = []
    def on_stage(step):
        steps.append(step)
        icon = '✓' if step['passed'] else '⚠'
        latest.markdown(f'**{icon} {step["stage"]}**  ·  {step["detail"]}')
        recent = steps[-7:]
        trail.markdown('\n\n'.join(f'{"🟢" if s["passed"] else "🟠"} **{s["stage"]}** — {s["detail"]}' for s in recent))
        progress.progress(min(0.97, len(steps) / 15), text=f'{len(steps)} stages completed')
        time.sleep(.10)  # Small UI pacing; actual validations run before each callback.
    def done():
        progress.progress(1., text=f'Execution complete · {len(steps)} recorded stages')
    return on_stage, done

def result_view(result, name, pdf=None):
    st.divider()
    st.subheader('Decision dossier')
    status_ui(result['status'], result['reason'])
    tabs = st.tabs(['Validation trace', 'Document evidence', 'Resolution plan', 'Export'])
    with tabs[0]:
        for i, step in enumerate(result['steps'], 1):
            with st.expander(f'{"✅" if step["passed"] else "⚠️"}  {i:02d} · {step["stage"]}', expanded=not step['passed']):
                st.write(step['detail'])
    with tabs[1]:
        doc = result.get('document')
        if doc:
            a,b,c = st.columns(3)
            a.metric('Extracted fields', len(doc['fields']))
            b.metric('Field coverage', f'{doc["coverage"]:.0%}')
            c.metric('Extraction', 'OCR' if doc['ocr_used'] else 'Text' if doc['text_available'] else 'Unavailable')
            st.caption('Coverage is for four expected evidence fields; it does not prove authenticity.')
            if doc.get('ocr_error'): st.info(doc['ocr_error'])
            comparisons = result.get('document_checks') or []
            if comparisons:
                st.dataframe([{'Field': c['field'].replace('_',' ').title(), 'Document': c['document_value'], 'Form': c['form_value'], 'Result': 'Match' if c['matches'] else 'Mismatch'} for c in comparisons], use_container_width=True, hide_index=True)
            if doc['missing_fields']: st.warning('Not extracted: '+', '.join(doc['missing_fields']))
            with st.expander('Extraction provenance'):
                st.json(doc.get('evidence', {}))
        else: st.info(result.get('document_error') or 'No PDF attached.')
    with tabs[2]:
        plan = communication_plan(result, name)
        a,b = st.columns(2)
        with a:
            st.markdown('#### Vendor actions')
            if plan['vendor_actions']:
                for item in plan['vendor_actions']: st.markdown('• '+item)
            else: st.success('No immediate action requested from the vendor.')
        with b:
            st.markdown('#### Internal review queue')
            if plan['internal_actions']:
                for item in plan['internal_actions']: st.markdown('• '+item)
            else: st.success('No additional internal exceptions.')
        st.markdown('#### Communication preview')
        msg = followup(result, name)
        st.text_area('Editable draft — not automatically sent', msg, height=240, key=f'draft_{result["vendor_id"]}_{result["status"]}')
        st.download_button('↓ Download email draft', msg, file_name='vendor_followup.txt', mime='text/plain', key=f'email_{result["vendor_id"]}')
    with tabs[3]:
        st.download_button('↓ Download decision + validation trace (JSON)', json.dumps(result, indent=2, default=str), file_name='veriquay_decision.json', mime='application/json', key=f'json_{result["vendor_id"]}')
        if pdf: st.download_button('↓ Download evidence PDF', pdf, file_name='veriquay_evidence.pdf', mime='application/pdf', key=f'pdf_{result["vendor_id"]}')

if page == 'Command center':
    st.subheader('Operations overview')
    rows, reg = history(DB), vendors(DB)
    a,b,c,d = st.columns(4)
    a.metric('Workflow runs',len(rows)); b.metric('Approved',sum(r['status']=='Approved' for r in rows)); c.metric('Pending',sum(r['status']=='Pending' for r in rows)); d.metric('Rejected',sum(r['status']=='Rejected' for r in rows))
    left,right=st.columns([1.6,1])
    with left:
        st.markdown('#### Recent decisions')
        if rows:
            filter_status=st.multiselect('Filter by decision',['Approved','Pending','Rejected'],default=['Approved','Pending','Rejected'])
            visible=[r for r in rows if r['status'] in filter_status]
            st.dataframe(visible,use_container_width=True,hide_index=True)
        else: st.info('No executions yet. Start a workflow to populate this dashboard.')
    with right:
        st.markdown('#### Decision distribution')
        counts={s:sum(r['status']==s for r in rows) for s in ['Approved','Pending','Rejected']}
        st.bar_chart(counts, horizontal=True)
        st.markdown('#### Quick start')
        st.write('Use **Live workflow** for repeatable demos or **Vendor intake** for your own form + PDF.')
    st.markdown('#### Vendor registry')
    st.dataframe(reg,use_container_width=True,hide_index=True)

elif page == 'Live workflow':
    st.subheader('Live scenario laboratory')
    st.write('Run real Python validations against generated test evidence. Each stage appears as it completes, and the decision is saved to SQLite.')
    defs=definitions()
    choice=st.selectbox('Choose a scenario',list(defs))
    st.info(defs[choice]['description'])
    if st.button('▶ Execute scenario',type='primary',use_container_width=True):
        on_stage,done=stage_callback()
        try:
            r,pdf=demo(choice,DB,on_stage=on_stage)
            done();st.session_state['last_demo']=(r,choice,pdf)
        except Exception as exc: st.error(f'Workflow error: {exc}')
    if 'last_demo' in st.session_state:
        r,n,p=st.session_state['last_demo'];result_view(r,n,p)

elif page == 'Vendor intake':
    st.subheader('New submission / vendor update')
    st.caption('Submit your own fictional form and PDF. A blank PDF or unreadable scan is held for manual review, never auto-approved.')
    records=vendors(DB)
    id_choice=st.selectbox('Submission type',[0]+[r['id'] for r in records],format_func=lambda x:'Register new vendor' if x==0 else f'Update existing vendor #{x}')
    with st.form('intake',clear_on_submit=False):
        st.markdown('#### 01 / Company and tax')
        a,b=st.columns(2)
        with a:
            name=st.text_input('Legal company name','Aster Technologies Pvt Ltd')
            country=st.selectbox('Country',['IN','US','GB','Other'])
        with b:
            tax=st.text_input('Tax ID (fictional)','27ABCDE1234F1Z5')
            email=st.text_input('Contact email','accounts@aster.example')
        st.markdown('#### 02 / Banking and compliance')
        a,b=st.columns(2)
        with a:
            holder=st.text_input('Bank account holder','Aster Technologies Pvt Ltd')
            account=st.text_input('Bank account number (fictional)','1111222233334444')
        with b:
            expiry=st.date_input('Certificate expiry',date.today()+timedelta(days=180))
            relation=st.checkbox('Corporate relationship evidence declared (human review required)')
        st.markdown('#### 03 / Document evidence')
        uploaded=st.file_uploader('Supporting PDF (maximum 5 MB)',type=['pdf'])
        st.caption('Text PDFs work out of the box. Scanned PDFs need optional Tesseract OCR installation. Upload fictional data only.')
        submitted=st.form_submit_button('▶ Validate submission',type='primary',use_container_width=True)
    if submitted:
        p=dict(legal_name=name,country=country,tax_id=tax,email=email,bank_holder=holder,bank_account=account,certificate_expiry=expiry.isoformat(),relationship_document='yes' if relation else 'no')
        pdf=uploaded.getvalue() if uploaded else None
        on_stage,done=stage_callback()
        try:
            r=execute(p,DB,vendor_id=id_choice or None,pdf=pdf,on_stage=on_stage)
            done();st.session_state['last_intake']=(r,name,pdf)
        except Exception as exc:st.error(f'Workflow error: {exc}')
    if 'last_intake' in st.session_state:
        r,n,p=st.session_state['last_intake'];result_view(r,n,p)

elif page == 'Decision explorer':
    st.subheader('Audit and decision explorer')
    runs=history(DB)
    if not runs: st.info('No recorded runs yet.')
    else:
        ids=[r['id'] for r in runs]
        chosen=st.selectbox('Select an execution ID',ids)
        conn=connect(DB)
        try: row=dict(conn.execute('SELECT * FROM runs WHERE id=?',(chosen,)).fetchone())
        finally:conn.close()
        status_ui(row['status'],row['reason'])
        a,b=st.columns(2)
        a.metric('Execution ID',row['id']);b.metric('Vendor ID',row['vendor_id'])
        st.markdown('#### Recorded validation checks')
        for step in json.loads(row['steps']):
            st.markdown(f'{"🟢" if step["passed"] else "🟠"} **{step["stage"]}** — {step["detail"]}')
        st.download_button('↓ Export audit record',json.dumps(row,indent=2),file_name=f'veriquay_run_{chosen}.json',mime='application/json')
    st.markdown('#### Sensitive bank change alerts')
    st.dataframe(events(DB),use_container_width=True,hide_index=True)


elif page == 'Demo data management':
    st.subheader('Demo data management')
    st.caption('Synthetic test data only. Deletions are permanent; back up vendorflow.db first.')
    st.warning('Deleting history does not validate or approve a vendor. For production, use an access-controlled archive and audit log instead.')
    mode = st.radio('Choose an operation', ['Delete one validation run', 'Delete a vendor and its history'], horizontal=True)

    if mode == 'Delete one validation run':
        all_runs = history(DB)
        if not all_runs:
            st.info('There are no validation runs to delete.')
        else:
            run_by_id = {r['id']: r for r in all_runs}
            run_id = st.selectbox('Validation run', list(run_by_id),
                format_func=lambda i: f"Run #{i} | Vendor #{run_by_id[i]['vendor_id']} | {run_by_id[i]['status']} | {run_by_id[i]['created_at']}")
            st.dataframe([run_by_id[run_id]], hide_index=True, use_container_width=True)
            confirmation = st.checkbox('I understand this run will be permanently deleted.', key='confirm_run')
            if st.button('Delete selected run', type='primary', disabled=not confirmation):
                conn = connect(DB)
                try:
                    with conn:
                        row = conn.execute('SELECT vendor_id FROM runs WHERE id=?', (run_id,)).fetchone()
                        if row is None:
                            st.error('This run no longer exists. Refresh the page.')
                        else:
                            vendor_id = row['vendor_id']
                            conn.execute('DELETE FROM runs WHERE id=?', (run_id,))
                            latest = conn.execute('SELECT status FROM runs WHERE vendor_id=? ORDER BY id DESC LIMIT 1', (vendor_id,)).fetchone()
                            conn.execute('UPDATE vendors SET status=? WHERE id=?',
                                         (latest['status'] if latest else 'No runs', vendor_id))
                            st.session_state.pop('last_intake', None)
                            st.session_state.pop('last_demo', None)
                            st.success(f'Run #{run_id} deleted. The vendor record was preserved.')
                finally:
                    conn.close()
                st.rerun()
    else:
        all_vendors = vendors(DB)
        if not all_vendors:
            st.info('There are no vendors to delete.')
        else:
            vendor_by_id = {v['id']: v for v in all_vendors}
            vendor_id = st.selectbox('Vendor', list(vendor_by_id),
                format_func=lambda i: f"Vendor #{i} | {vendor_by_id[i]['legal_name']} | {vendor_by_id[i]['status']}")
            selected = vendor_by_id[vendor_id]
            st.dataframe([selected], hide_index=True, use_container_width=True)
            st.error('This will permanently delete the vendor, all its validation runs, and its bank-change events.')
            confirmation = st.checkbox('I understand this vendor and all its history will be permanently deleted.', key='confirm_vendor')
            typed = st.text_input(f'Type DELETE {vendor_id} to confirm', key=f'delete_vendor_{vendor_id}')
            if st.button('Delete vendor and history', type='primary',
                         disabled=not (confirmation and typed.strip() == f'DELETE {vendor_id}')):
                conn = connect(DB)
                try:
                    with conn:
                        conn.execute('DELETE FROM events WHERE vendor_id=?', (vendor_id,))
                        conn.execute('DELETE FROM runs WHERE vendor_id=?', (vendor_id,))
                        deleted = conn.execute('DELETE FROM vendors WHERE id=?', (vendor_id,)).rowcount
                    if deleted:
                        st.session_state.pop('last_intake', None)
                        st.session_state.pop('last_demo', None)
                        st.success(f'Vendor #{vendor_id} and associated history deleted.')
                    else:
                        st.error('Vendor not found. Refresh the page.')
                finally:
                    conn.close()
                st.rerun()

else:
    st.subheader('Policy, trust and scope')
    st.markdown('''**Approved** — configured checks pass. This is a demonstration-policy approval, **not independent identity, tax, or bank verification**.

**Pending** — information is missing, inconsistent, duplicated, expired, changed, or cannot be extracted. A reviewer or vendor must resolve the issue.

**Rejected** — only the explicitly supplied **fictional confirmed policy block** in the demo; the app does not infer fraud from mismatched names.

**Document handling** — extracts labeled fields from text PDFs and supports several label/date formats. Optional OCR uses locally installed Tesseract for scanned PDFs. Neither method authenticates certificates. Unsupported layouts are held for review.

**Communication** — creates separate vendor-facing actions and internal review tasks; messages are editable drafts and **not sent automatically**.

**Privacy** — fictional data only. The database stores masked/fingerprinted tax and bank identifiers, but this is **not a production security implementation**. No login, role-based access, encryption-at-rest, or official registry integrations.

**Execution** — stages are displayed through callbacks while checks run, not a replay. A short display delay makes fast checks readable; all results come from actual rules. SQLite history is local and can be lost on ephemeral cloud hosting.''')
    st.markdown('#### System components')
    st.code('Streamlit UI → PDF text/OCR extraction → field comparison → validation engine → SQLite audit → decision + follow-up',language='text')
