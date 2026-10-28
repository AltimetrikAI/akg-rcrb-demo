package com.hpe.finance.invoice.validation;

import com.hpe.finance.invoice.exception.VatValidationException;
import org.springframework.stereotype.Component;

/**
 * HPE Finance Platform - Belgian VAT Validator
 *
 * Validates Belgian VAT registration numbers per Royal Decree 9 March 2022
 * and EU Directive 2014/55/EU (Peppol BIS Billing 3.0).
 *
 * Belgium VAT format: BExxxxxxxxxx
 *   - Prefix: "BE"
 *   - Total length: 12 characters
 *   - Digits: 10 after prefix
 *   - First digit of number must not be 0
 *   - Mod-97 check digit validation (same as IBAN)
 *
 * Peppol fields:
 *   Seller VAT (KNA1.STCEG, VBRK.STCEG) -> BT-031 Seller VAT Identifier
 *   Buyer  VAT (KNA1.STCEG)              -> BT-048 Buyer VAT Identifier
 *
 * ABAP equivalent: Z_HPE_VATCHECK function module performs same validation.
 * Critical gap identified: InvoiceDeliveryService skips this validator
 * on the PDF_EMAIL fast path — CHANGE REQUIRED before 2026-01-01 mandate.
 */
@Component
public class BelgianVatValidator {

    private static final String BE_PREFIX   = "BE";
    private static final int    FULL_LENGTH = 12;   // BE + 10 digits
    private static final int    MODULUS     = 97;

    /**
     * Validate a Belgian VAT number.
     * Throws VatValidationException with Peppol field reference on failure.
     *
     * @param vatNumber raw VAT number string (e.g. "BE0471938028")
     * @throws VatValidationException if format or check-digit is invalid
     */
    public void validate(String vatNumber) {
        if (vatNumber == null || vatNumber.isBlank()) {
            throw new VatValidationException(
                "BT-048/BT-031: Belgian VAT number is null or blank. " +
                "Required field: KNA1.STCEG (buyer) or VBRK.STCEG (seller).");
        }

        String vat = vatNumber.trim().toUpperCase();

        // Must start with BE
        if (!vat.startsWith(BE_PREFIX)) {
            throw new VatValidationException(
                "BT-048/BT-031: Belgian VAT number must start with 'BE'. " +
                "Received: '" + vat + "'. Check KNA1.STCEG.");
        }

        // Must be exactly 12 characters (BE + 10 digits)
        if (vat.length() != FULL_LENGTH) {
            throw new VatValidationException(
                "BT-048/BT-031: Belgian VAT number must be 12 chars (BE + 10 digits). " +
                "Got length " + vat.length() + " for '" + vat + "'.");
        }

        String digits = vat.substring(2);  // strip "BE"

        // All remaining chars must be digits
        if (!digits.matches("\\d{10}")) {
            throw new VatValidationException(
                "BT-048/BT-031: Belgian VAT number must have 10 digits after 'BE'. " +
                "Non-digit chars in '" + digits + "'.");
        }

        // First digit (enterprise number first digit) must not be 0
        if (digits.charAt(0) == '0') {
            throw new VatValidationException(
                "BT-048/BT-031: Belgian VAT number enterprise number cannot start with 0. " +
                "Got '" + vat + "'. Verify KNA1.STCEG data quality in SAP MDG.");
        }

        // Mod-97 check: 97 - (first 8 digits mod 97) = last 2 digits (check digits)
        long baseNumber  = Long.parseLong(digits.substring(0, 8));
        int  checkDigits = Integer.parseInt(digits.substring(8, 10));
        int  expected    = MODULUS - (int)(baseNumber % MODULUS);

        if (expected != checkDigits) {
            throw new VatValidationException(
                "BT-048/BT-031: Belgian VAT number '" + vat + "' failed mod-97 check. " +
                "Expected check digits " + String.format("%02d", expected) +
                " but got " + String.format("%02d", checkDigits) + ". " +
                "Data quality issue in KNA1.STCEG. Refer MDG change RCRB-BE-2024-001.");
        }
    }

    /**
     * Non-throwing validation — returns true/false for use in conditional logic.
     * Use validate() in mandatory paths; this for soft checks only.
     */
    public boolean isValid(String vatNumber) {
        try {
            validate(vatNumber);
            return true;
        } catch (VatValidationException e) {
            return false;
        }
    }
}
