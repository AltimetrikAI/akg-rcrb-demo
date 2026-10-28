package com.hpe.finance.invoice.service;

import com.hpe.finance.invoice.model.Invoice;
import com.hpe.finance.invoice.model.CustomerProfile;
import com.hpe.finance.invoice.repository.CustomerRepository;
import com.hpe.finance.invoice.sap.SapMdgClient;
import com.hpe.finance.invoice.validation.BelgianVatValidator;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;

/**
 * HPE Finance Platform - Customer VAT Service
 *
 * Manages customer VAT registration data for e-invoice compliance.
 * Integrates with SAP MDG (Master Data Governance) as the system
 * of record for customer master data (KNA1 table in SAP).
 *
 * Data flow:
 *   CustomerRepository (local H2 cache)
 *     <- SAP MDG via RFC (SapMdgClient reads KNA1.STCEG, KNA1.LAND1)
 *
 * Belgium e-invoicing impact (HIGH):
 *   KNA1.STCEG (VAT Reg. No.) currently OPTIONAL in MDG workflow.
 *   Must become MANDATORY for all customers with LAND1 = 'BE'.
 *   MDG change request: RCRB-BE-2024-001
 *
 * Peppol field mapping:
 *   CustomerProfile.vatRegistrationNumber -> BT-048 (Buyer VAT ID)
 */
@Service
@Slf4j
public class CustomerVatService {

    @Autowired private CustomerRepository  customerRepo;
    @Autowired private SapMdgClient        sapMdgClient;   // reads SAP KNA1 via RFC
    @Autowired private BelgianVatValidator belgianVatValidator;

    /**
     * Fetch customer profile, reading from SAP MDG (KNA1) if not cached.
     * Cached for 1 hour to reduce RFC calls to SAP.
     */
    @Cacheable(value = "customer-vat", key = "#customerId")
    public CustomerProfile getCustomerProfile(String customerId) {
        return customerRepo.findById(customerId)
            .orElseGet(() -> {
                log.debug("Cache miss for customer={}, fetching from SAP MDG (KNA1)", customerId);
                return sapMdgClient.fetchCustomerMaster(customerId); // reads KNA1
            });
    }

    /**
     * Validate and enrich invoice with customer VAT data.
     * Called before Peppol submission by InvoiceDeliveryService.
     *
     * BT-048 (Buyer VAT Identifier) populated here from KNA1.STCEG.
     */
    public void validateAndEnrich(Invoice invoice) {
        CustomerProfile profile = getCustomerProfile(invoice.getCustomerId());

        if ("BE".equals(profile.getCountry())) {
            // Belgium: VAT Registration Number is MANDATORY (BT-048)
            // CHANGE REQUIRED: currently only WARNING logged, not enforced
            if (profile.getVatRegistrationNumber() == null ||
                profile.getVatRegistrationNumber().isBlank()) {

                // TODO: After 2026-01-01 this must throw, not warn
                log.warn("Belgian customer {} has no VAT registration number (KNA1.STCEG). " +
                         "Required for BT-048. Invoice {} may fail Peppol validation.",
                         invoice.getCustomerId(), invoice.getDocumentNumber());

                // CHANGE REQUIRED: uncomment after MDG mandatory field enforced
                // throw new MissingVatException("BT-048 mandatory for BE customers");
            } else {
                // Validate format: BExxxxxxxxxx (BE + 10 digits)
                belgianVatValidator.validate(profile.getVatRegistrationNumber());
            }
        }

        // Enrich invoice with VAT data for Peppol document builder
        invoice.setBuyerVatId(profile.getVatRegistrationNumber());  // -> BT-048
        invoice.setBuyerName(profile.getCompanyName());
        invoice.setBuyerCountry(profile.getCountry());
        invoice.setBuyerAddress(profile.getStreetAddress());
        invoice.setBuyerCity(profile.getCity());
        invoice.setBuyerPostalCode(profile.getPostalCode());
    }
}
