import xml.etree.ElementTree as ET
from decimal import Decimal
from typing import Dict, Any
import re
import logging

logger = logging.getLogger(__name__)

class ISO20022Parser:
    """
    A specialized parser for ISO 20022 Financial Messages.
    Focuses on 'pacs.008' (Customer Credit Transfer) for the Swiss Market.
    """
    
    def _extract_namespace(self, xml_content: str) -> str:
        """Dynamically extracts the namespace to support various ISO versions (DACH/SEPA)."""
        # Regex to find xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.xxx.xx"
        match = re.search(r'xmlns="([^"]+)"', xml_content)
        if match:
            return match.group(1)
        return 'urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08' # Fallback to Swiss v8

    def parse_credit_transfer(self, xml_content: str) -> Dict[str, Any]:
        """
        Parses a raw XML string and extracts transaction details.
        Returns a dictionary ready for the LedgerEngine.
        """
        try:
            namespace = self._extract_namespace(xml_content)
            namespaces = {'doc': namespace}
            
            root = ET.fromstring(xml_content)
            
            # Helper to find elements with namespace
            def find_text(path, element=root):
                el = element.find(path, namespaces)
                return el.text if el is not None else None
            
            def find_elem(path, element=root):
                return element.find(path, namespaces)

            # 1. Extract Transaction ID (EndToEndId)
            # Path: Document -> FIToFICstmrCdtTrf -> CdtTrfTxInf -> PmtId -> EndToEndId
            tx_info = find_elem(".//doc:CdtTrfTxInf")
            if tx_info is None:
                raise ValueError("Invalid ISO 20022: No Credit Transfer Info found")

            end_to_end_id = find_text("doc:PmtId/doc:EndToEndId", tx_info)

            # 2. Extract Amount & Currency
            # Path: ... -> Amt -> InstdAmt
            amt_elem = find_elem("doc:Amt/doc:InstdAmt", tx_info)
            amount = Decimal(amt_elem.text)
            currency = amt_elem.get("Ccy")

            # 3. Extract Remittance Information (Description)
            # Path: ... -> RmtInf -> Ustrd (Unstructured)
            description = find_text("doc:RmtInf/doc:Ustrd", tx_info)

            # 4. Extract Debtor & Creditor (Simplification for Demo)
            # In real world, we would map IBANs to internal Account IDs.
            # Here we extract the IBAN string.
            debtor_iban = find_text("doc:DbtrAcct/doc:Id/doc:IBAN", tx_info)
            creditor_iban = find_text("doc:CdtrAcct/doc:Id/doc:IBAN", tx_info)

            logger.info(f"Successfully parsed ISO 20022 msg: {end_to_end_id}")

            return {
                "transaction_ref": end_to_end_id,
                "amount": amount,
                "currency": currency,
                "description": description,
                "debtor_iban": debtor_iban,
                "creditor_iban": creditor_iban,
                # REAL WORLD IMPLEMENTATION NOTE:
                # The caller of this parser should now perform:
                # debit_account = session.exec(select(Account).where(Account.iban == debtor_iban)).first()
                # credit_account = session.exec(select(Account).where(Account.iban == creditor_iban)).first()
                # if not debit_account: raise ValueError("Unknown Debtor IBAN")
            }

        except ET.ParseError as e:
            logger.error(f"XML Parsing Failed: {str(e)}")
            raise ValueError("Malformed XML Data")
        except AttributeError as e:
            logger.error(f"Missing required ISO 20022 fields: {str(e)}")
            raise ValueError("XML missing required fields (Amt, Ccy, or Ids)")