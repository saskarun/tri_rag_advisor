"""Generate fictional SAMPLE regulatory documents (not real notifications)."""
import json
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from docx import Document

OUT = Path(__file__).parent / "samples"
OUT.mkdir(exist_ok=True)

def pdf(name, title, paras):
    st = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(OUT / name), pagesize=A4)
    flow = [Paragraph(title, st["Title"]), Paragraph("SAMPLE DOCUMENT - fictional content for demo purposes only.", st["Italic"]), Spacer(1, 12)]
    for p in paras:
        flow += [Paragraph(p, st["BodyText"]), Spacer(1, 8)]
    doc.build(flow)

pdf("CBIC_Circular_ISD_EInvoicing_Sample.pdf", "CBIC Circular No. 999/12/2025-GST (Sample): ISD Rules and E-Invoicing", [
 "Section 1. Applicability. This circular, issued by the Central Board of Indirect Taxes and Customs (CBIC, also referred to as the Tax Authority for indirect tax), clarifies the distribution of input tax credit (ITC) by an Input Service Distributor (ISD) under Section 20 of the CGST Act, 2017 and Rule 39 of the CGST Rules, 2017.",
 "Section 2. ISD Registration. Every office of Meridian Industries Ltd. that receives common input services for distribution to its group entities must obtain a separate ISD registration. Meridian Industries Ltd. is the parent of Meridian Components Pvt. Ltd.",
 "Section 3. Distribution of Credit. Under Rule 39, ITC on common services shall be distributed in the ratio of turnover of the recipient units in the preceding financial year. Credit distributed by mistake to a wrong recipient shall be recovered with interest at 18 percent per annum under Section 21.",
 "Section 4. E-Invoicing Threshold. The 57th GST Council meeting recommended that e-invoicing under Rule 48(4) be mandatory for taxpayers with aggregate turnover exceeding INR 5 crore. This is a prospective amendment effective 1 April 2026 and does not apply to invoices issued before that date.",
 "Section 5. Retrospective Clarification. The clarification in Section 3 regarding ISD invoices raised on or after 1 April 2024 is clarificatory in nature and applies retrospectively from the date of introduction of the ISD mechanism.",
 "Section 6. Penalty. Failure to issue an ISD invoice as per Rule 54(1A) attracts a penalty under Section 122 of up to INR 25,000 per instance.",
])

pdf("RBI_KYC_PMLA_SOP_Sample.pdf", "Prism Bank Ltd. - KYC/AML Standard Operating Procedure (Sample)", [
 "Clause 1. Purpose. This SOP implements the RBI Master Direction on Know Your Customer (KYC), 2016 and obligations under the Prevention of Money Laundering Act, 2002 (PMLA) for Prism Bank Ltd. The Reserve Bank of India (RBI, the Regulator) supervises compliance.",
 "Clause 2. Customer Due Diligence. Prism Bank shall carry out CDD at account opening. For non-individual customers, beneficial owners holding more than 10 percent of shares must be identified, as per Section 3(b) of the PML Rules. Meridian Industries Ltd. is a corporate customer of Prism Bank and is classified as medium risk.",
 "Clause 3. Periodic KYC Update. Re-KYC is required every 2 years for high risk, every 8 years for medium risk, and every 10 years for low risk customers. Control C-07 (Re-KYC Tracker) maps to this obligation.",
 "Clause 4. Suspicious Transaction Reporting. The Principal Officer shall file a Suspicious Transaction Report (STR) with the Financial Intelligence Unit - India (FIU-IND) within 7 working days of arriving at a conclusion of suspicion. Control C-12 (STR Workflow) maps to this obligation.",
 "Clause 5. Penalties. Non-compliance with KYC obligations may attract a monetary penalty under Section 47A of the Banking Regulation Act, 1949 and a penalty under Section 13 of PMLA of INR 10,000 to INR 100,000 per failure. Repeated failure may lead to licence restriction.",
 "Clause 6. Risk Framework. Residual risk is assessed using ISO 31000 aligned methodology; risk owners must log exceptions in the GRC register within 5 working days.",
])

d = Document()
d.add_heading("Share Purchase Agreement (Sample Excerpt)", 0)
d.add_paragraph("SAMPLE DOCUMENT - fictional content for demo purposes only.")
for t in [
 "Clause 1. Parties. This Share Purchase Agreement is entered into between Aster Capital Partners (the Buyer) and Meridian Industries Ltd. (the Seller) for the sale of 100 percent of the equity shares of Meridian Components Pvt. Ltd. (the Target).",
 "Clause 2. Purchase Price. The aggregate purchase price is INR 850 crore, subject to a working-capital adjustment capped at INR 20 crore. Valuation shall be supported by a report from a registered valuer under the Companies Act 2013 and Rule 11UA of the Income Tax Rules.",
 "Clause 3. Indemnity. The Seller shall indemnify the Buyer against Losses arising from breach of warranties, including any tax liability of the Target for periods before Closing, including ISD credit reversals under Section 21 of the CGST Act. The Seller's aggregate liability is capped at 15 percent of the Purchase Price (INR 127.5 crore), with a basket threshold of INR 2 crore.",
 "Clause 4. Material Adverse Change. A Material Adverse Change means any event that reduces consolidated EBITDA of the Target by more than 20 percent or results in suspension of any licence. The Buyer may terminate before Closing upon a MAC, with a long-stop date of 31 March 2027.",
 "Clause 5. Foreign Investment. As the Buyer is a non-resident entity, the transaction shall comply with FEMA Non-Debt Instruments Rules, 2019 pricing guidelines, and Form FC-TRS shall be filed within 60 days of receipt of consideration.",
 "Clause 6. Regulatory Conditions. Closing is conditional on no adverse finding by the Income Tax Dept. or the CBIC against the Target and on clearance by the Competition Commission of India.",
]:
    d.add_paragraph(t)
d.save(OUT / "SPA_Aster_Meridian_Sample.docx")

table = {
 "title": "Tax thresholds and rates table (Sample)",
 "rows": [
  {"item": "E-invoicing mandatory turnover threshold", "value": "INR 5 crore", "reference": "Rule 48(4) CGST Rules", "authority": "CBIC"},
  {"item": "ISD credit recovery interest rate", "value": "18% per annum", "reference": "Section 21 CGST Act", "authority": "CBIC"},
  {"item": "Penalty for ISD invoice default", "value": "INR 25,000 per instance", "reference": "Section 122 / Rule 54(1A)", "authority": "CBIC"},
  {"item": "Tax on transfer of unlisted shares (long term)", "value": "12.5%", "reference": "Section 112 Income Tax Act", "authority": "CBDT"},
  {"item": "TDS on payment to non-resident for share sale", "value": "As per Section 195", "reference": "Section 195 Income Tax Act", "authority": "Income Tax Dept"},
  {"item": "Beneficial owner threshold for companies", "value": "10%", "reference": "PML Rules Section 3(b)", "authority": "RBI"},
 ],
}
(OUT / "Tax_Thresholds_Table_Sample.json").write_text(json.dumps(table, indent=2))
print("done", [p.name for p in OUT.iterdir()])
