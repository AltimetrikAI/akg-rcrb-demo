package com.hpe.finance.invoice.service;

import com.hpe.finance.invoice.model.LineItem;
import com.hpe.finance.invoice.model.TaxResult;
import com.hpe.finance.invoice.model.VatLine;
import com.hpe.finance.invoice.repository.TaxRateRepository;
import com.hpe.finance.invoice.sap.SapFiClient;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * HPE Finance Platform - Tax Determination Service
 *
 * Computes applicable VAT rates per line item and builds BG-23
 * VAT breakdown required by Peppol / Belgium e-invoicing mandate.
 *
 * Data sources:
 *   SapFiClient   -> reads SAP T007A (tax keys) and TTXD (tax rates) via RFC
 *   TaxRateRepository -> local cache of country/rate mappings
 *
 * Peppol BG-23 VAT Breakdown fields produced:
 *   VatLine.rate          -> BT-119 (VAT category rate)
 *   VatLine.taxableAmount -> BT-116 (VAT category taxable amount)
 *   VatLine.taxAmount     -> BT-117 (VAT category tax amount)
 *
 * Belgium impact (MEDIUM):
 *   Each distinct VAT rate MUST appear as a separate VatLine.
 *   Current implementation groups correctly but SAP BSEG posting
 *   (Z_HPE_FI_TAXPOST) must mirror this grouping for BG-23 compliance.
 */
@Service
@Slf4j
public class TaxDeterminationService {

    @Autowired private TaxRateRepository taxRateRepo;
    @Autowired private SapFiClient       sapFiClient;  // reads T007A, TTXD from SAP FI

    /**
     * Calculate tax and build BG-23 VAT breakdown for a set of invoice lines.
     *
     * @param countryCode ISO 3166-1 alpha-2 customer country
     * @param lineItems   invoice line items with net amounts and tax codes
     * @return TaxResult containing per-rate VatLines (BG-23) and total tax
     */
    public TaxResult calculateTax(String countryCode, List<LineItem> lineItems) {
        // Fetch current tax rates from SAP T007A/TTXD
        Map<String, BigDecimal> taxCodeRates = sapFiClient.getTaxRates(countryCode);

        // BG-23: group by tax code, one VatLine per distinct rate
        Map<String, List<LineItem>> byTaxCode = lineItems.stream()
            .collect(Collectors.groupingBy(LineItem::getTaxCode));

        List<VatLine> vatBreakdown = byTaxCode.entrySet().stream()
            .map(entry -> {
                String     taxCode      = entry.getKey();
                BigDecimal rate         = taxCodeRates.getOrDefault(taxCode, BigDecimal.ZERO);

                // BT-116: Sum net amounts for this tax code
                BigDecimal taxableAmount = entry.getValue().stream()
                    .map(LineItem::getNetAmount)
                    .reduce(BigDecimal.ZERO, BigDecimal::add);

                // BT-117: Tax amount = taxable * rate / 100
                BigDecimal taxAmount = taxableAmount
                    .multiply(rate)
                    .divide(BigDecimal.valueOf(100), 2, RoundingMode.HALF_UP);

                log.debug("VatLine: taxCode={} rate={}% taxable={} tax={}",
                          taxCode, rate, taxableAmount, taxAmount);

                return new VatLine(taxCode, rate, taxableAmount, taxAmount); // BG-23 line
            })
            .collect(Collectors.toList());

        BigDecimal totalTax = vatBreakdown.stream()
            .map(VatLine::getTaxAmount)
            .reduce(BigDecimal.ZERO, BigDecimal::add);

        log.info("Tax determination: country={} lines={} vatRates={} totalTax={}",
                 countryCode, lineItems.size(), vatBreakdown.size(), totalTax);

        return new TaxResult(vatBreakdown, totalTax);
    }
}
