import xml.etree.ElementTree as ET
from datetime import datetime
import random

def generate_pacs_008(filename="transaction.xml", amount="100.00", currency="CHF", 
                      debtor_iban="CH9300700111111111111", creditor_iban="CH9300700333333333333"):
    """
    Generates a valid ISO 20022 (pacs.008) XML file for testing.
    """
    
    # Namespace ISO 20022 pacs.008.001.08 (Swiss Standard)
    ns = "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"
    ET.register_namespace("", ns)
    
    root = ET.Element(f"{{{ns}}}Document")
    
    # Structure Hierarchy
    msg = ET.SubElement(root, f"{{{ns}}}FIToFICstmrCdtTrf")
    tx_info = ET.SubElement(msg, f"{{{ns}}}CdtTrfTxInf")
    
    # 1. Transaction ID (Unique based on timestamp)
    pmt_id = ET.SubElement(tx_info, f"{{{ns}}}PmtId")
    end_to_end_id = ET.SubElement(pmt_id, f"{{{ns}}}EndToEndId")
    end_to_end_id.text = f"TX-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(100,999)}"
    
    # 2. Amount
    amt = ET.SubElement(tx_info, f"{{{ns}}}Amt")
    instd_amt = ET.SubElement(amt, f"{{{ns}}}InstdAmt", Ccy=currency)
    instd_amt.text = str(amount)
    
    # 3. Description
    rmt_inf = ET.SubElement(tx_info, f"{{{ns}}}RmtInf")
    ustrd = ET.SubElement(rmt_inf, f"{{{ns}}}Ustrd")
    ustrd.text = f"Automated Payment {end_to_end_id.text}"
    
    # 4. Debtor (Sender)
    dbtr = ET.SubElement(tx_info, f"{{{ns}}}DbtrAcct")
    dbtr_id = ET.SubElement(dbtr, f"{{{ns}}}Id")
    dbtr_iban_el = ET.SubElement(dbtr_id, f"{{{ns}}}IBAN")
    dbtr_iban_el.text = debtor_iban
    
    # 5. Creditor (Receiver)
    cdtr = ET.SubElement(tx_info, f"{{{ns}}}CdtrAcct")
    cdtr_id = ET.SubElement(cdtr, f"{{{ns}}}Id")
    cdtr_iban_el = ET.SubElement(cdtr_id, f"{{{ns}}}IBAN")
    cdtr_iban_el.text = creditor_iban
    
    tree = ET.ElementTree(root)
    tree.write(filename, encoding="utf-8", xml_declaration=True)
    print(f"✅ Generated file: {filename} (Amount: {amount} {currency})")

if __name__ == "__main__":
    generate_pacs_008()