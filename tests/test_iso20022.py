import pytest
from decimal import Decimal
from app.services.iso_parser import ISO20022Parser

def test_parse_valid_pacs_008():
    # Sample ISO 20022 XML (Simplified real bank payload)
    xml_data = """
    <Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
        <FIToFICstmrCdtTrf>
            <CdtTrfTxInf>
                <PmtId>
                    <EndToEndId>TX-SWISS-2026-001</EndToEndId>
                </PmtId>
                <Amt>
                    <InstdAmt Ccy="CHF">15000.50</InstdAmt>
                </Amt>
                <RmtInf>
                    <Ustrd>Invoice #999 Payment</Ustrd>
                </RmtInf>
                <DbtrAcct>
                    <Id><IBAN>CH9300700123456789012</IBAN></Id>
                </DbtrAcct>
                <CdtrAcct>
                    <Id><IBAN>CH9300700987654321098</IBAN></Id>
                </CdtrAcct>
            </CdtTrfTxInf>
        </FIToFICstmrCdtTrf>
    </Document>
    """
    
    parser = ISO20022Parser()
    result = parser.parse_credit_transfer(xml_data)
    
    assert result["transaction_ref"] == "TX-SWISS-2026-001"
    assert result["amount"] == Decimal("15000.50")
    assert result["currency"] == "CHF"
    assert result["description"] == "Invoice #999 Payment"
    assert result["debtor_iban"] == "CH9300700123456789012"

def test_parse_invalid_xml():
    parser = ISO20022Parser()
    with pytest.raises(ValueError, match="Malformed XML"):
        parser.parse_credit_transfer("<Invalid>XML</Broken>")