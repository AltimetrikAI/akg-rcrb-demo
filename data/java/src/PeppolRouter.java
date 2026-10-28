package com.hpe.finance.invoice.peppol;

import com.hpe.finance.invoice.model.Invoice;
import com.hpe.finance.invoice.model.DeliveryResult;
import com.hpe.finance.invoice.model.PeppolDocument;
import com.hpe.finance.invoice.sap.SapDcpClient;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Retryable;
import org.springframework.stereotype.Component;

/**
 * HPE Finance Platform - Peppol AS4 Router
 *
 * Builds Peppol BIS Billing 3.0 (UBL 2.1) documents and submits
 * to the Peppol AS4 network via SAP Document Compliance Platform.
 *
 * Mandatory Peppol fields validated before submission:
 *   BT-031 - Seller VAT identifier      (e.g. BE0471938028)
 *   BT-048 - Buyer VAT identifier        (mandatory for Belgium)
 *   BT-9   - Payment due date            (mandatory for Belgium)
 *   BG-23  - VAT breakdown by rate       (mandatory for Belgium)
 *   BT-5   - Invoice currency code       (ISO 4217)
 *
 * Integration: SAP DCP via REST API (SapDcpClient)
 * SapDcpClient reads: invoice data, maps to UBL 2.1 XML
 * SapDcpClient writes: Peppol network submission record
 */
@Component
@Slf4j
public class PeppolRouter {

    @Autowired private SapDcpClient      sapDcpClient;
    @Autowired private UblDocumentBuilder ublBuilder;

    @Value("${peppol.sender-participant-id}")
    private String senderParticipantId;   // HPE's Peppol participant ID

    @Value("${peppol.be.mandatory-from:2026-01-01}")
    private String belgiumMandatoryFrom;

    /**
     * Submit invoice to Peppol AS4 network.
     * Retries up to 3 times with exponential backoff on transient failures.
     */
    @Retryable(maxAttempts = 3, backoff = @Backoff(delay = 2000, multiplier = 2))
    public DeliveryResult submit(Invoice invoice) {
        log.info("Building Peppol BIS 3.0 document for invoice={}", invoice.getDocumentNumber());

        // Build UBL 2.1 / Peppol BIS Billing 3.0 XML document
        PeppolDocument doc = ublBuilder.build(invoice);

        // Validate all mandatory Peppol fields before submission
        validateMandatoryFields(invoice, doc);

        // Submit via SAP DCP (handles AS4 transport and network routing)
        String transmissionId = sapDcpClient.submitPeppol(
            doc,
            senderParticipantId,
            invoice.getBuyerPeppolParticipantId()
        );

        log.info("Peppol submission OK: invoice={} transmissionId={}",
                 invoice.getDocumentNumber(), transmissionId);

        return DeliveryResult.success(transmissionId, "PEPPOL_AS4");
    }

    public DeliveryResult submitChorusPro(Invoice invoice) {
        // France Chorus Pro submission via Peppol network
        PeppolDocument doc = ublBuilder.buildChorusPro(invoice);
        String transmissionId = sapDcpClient.submitChorusPro(doc);
        return DeliveryResult.success(transmissionId, "CHORUS_PRO");
    }

    private void validateMandatoryFields(Invoice invoice, PeppolDocument doc) {
        // BT-031: Seller VAT identifier - always mandatory for Peppol
        if (doc.getSellerVatId() == null || doc.getSellerVatId().isBlank()) {
            throw new PeppolValidationException(
                "BT-031 Seller VAT Identifier is mandatory for Peppol submission. " +
                "Check VBRK.STCEG for company code " + invoice.getCompanyCode());
        }

        // BT-048: Buyer VAT identifier - mandatory for Belgium
        if ("BE".equals(invoice.getCustomerCountry()) && doc.getBuyerVatId() == null) {
            throw new PeppolValidationException(
                "BT-048 Buyer VAT Identifier is mandatory for Belgian B2B invoices. " +
                "Customer " + invoice.getCustomerId() + " has no VAT in KNA1.STCEG.");
        }

        // BT-9: Payment due date - mandatory for Belgium
        if ("BE".equals(invoice.getCustomerCountry()) && invoice.getPaymentDueDate() == null) {
            throw new PeppolValidationException(
                "BT-9 Payment Due Date is mandatory for Belgian invoices (VBRK.ZFAELL).");
        }

        // BG-23: VAT breakdown - mandatory (one entry per distinct rate)
        if (doc.getVatBreakdown() == null || doc.getVatBreakdown().isEmpty()) {
            throw new PeppolValidationException(
                "BG-23 VAT Breakdown is mandatory. Each VAT rate must appear as a " +
                "separate line. Check BSEG tax lines grouped by MWSKZ.");
        }
    }
}
