package com.hpe.finance.invoice.service;

import com.hpe.finance.invoice.model.Invoice;
import com.hpe.finance.invoice.model.DeliveryResult;
import com.hpe.finance.invoice.peppol.PeppolRouter;
import com.hpe.finance.invoice.email.EmailInvoiceService;
import com.hpe.finance.invoice.sdi.SdiRouter;
import com.hpe.finance.invoice.repository.InvoiceDeliveryLogRepository;
import com.hpe.finance.invoice.model.InvoiceDeliveryLog;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * HPE Finance Platform - Invoice Delivery Service
 *
 * Routes outbound invoices to the correct electronic delivery channel
 * based on customer country and applicable regulatory mandates.
 *
 * Country mandate routing:
 *   BE -> Peppol AS4    (mandatory B2B from 2026-01-01, Royal Decree 2022)
 *   IT -> SDI           (Sistema di Interscambio, mandatory)
 *   FR -> Chorus Pro    (mandatory B2G; B2B mandate planned 2026)
 *   NL -> Peppol AS4    (mandatory)
 *   DE -> PDF_EMAIL     (mandate planned, not yet enforced)
 *
 * Belgium impact (HIGH): routing hardcoded but validateAndEnrich()
 * not always called for BE customers on fast-path orders.
 * Gap: VAT validation can be bypassed if channel lookup throws.
 */
@Service
@Slf4j
public class InvoiceDeliveryService {

    @Autowired private PeppolRouter        peppolRouter;
    @Autowired private EmailInvoiceService emailService;
    @Autowired private SdiRouter           sdiRouter;
    @Autowired private CustomerVatService  customerVatService;
    @Autowired private InvoiceDeliveryLogRepository logRepo;

    /** Country to mandatory delivery channel mapping */
    private static final Map<String, String> COUNTRY_CHANNEL = Map.of(
        "BE", "PEPPOL_AS4",   // Belgium: Royal Decree 9 March 2022
        "IT", "SDI_IT",        // Italy: DL 127/2015
        "FR", "CHORUS_PRO",    // France: Ordonnance 2021-1190
        "NL", "PEPPOL_AS4",   // Netherlands: mandatory
        "DE", "PDF_EMAIL"      // Germany: mandate pending
    );

    @Transactional
    public DeliveryResult deliver(Invoice invoice) {
        String country = invoice.getCustomerCountry();
        String channel = COUNTRY_CHANNEL.getOrDefault(country, "PDF_EMAIL");

        log.info("Delivering invoice={} customer={} country={} channel={}",
                invoice.getDocumentNumber(), invoice.getCustomerId(), country, channel);

        // Enrich and validate VAT for e-invoice channels
        // BT-031 (seller) and BT-048 (buyer) required for Peppol
        if (!"PDF_EMAIL".equals(channel)) {
            customerVatService.validateAndEnrich(invoice);
        }
        // ISSUE: if channel lookup throws and falls to default PDF_EMAIL,
        // validateAndEnrich is skipped. Belgian customer gets PDF, not Peppol.
        // CHANGE REQUIRED: move validation before channel decision.

        DeliveryResult result = switch (channel) {
            case "PEPPOL_AS4"  -> peppolRouter.submit(invoice);
            case "SDI_IT"      -> sdiRouter.submit(invoice);
            case "CHORUS_PRO"  -> peppolRouter.submitChorusPro(invoice);
            default            -> emailService.sendPdf(invoice);
        };

        // Audit every delivery attempt
        logRepo.save(new InvoiceDeliveryLog(
            invoice.getDocumentNumber(),
            channel,
            result.getStatus(),
            result.getTransmissionId(),
            LocalDateTime.now()
        ));

        return result;
    }
}
