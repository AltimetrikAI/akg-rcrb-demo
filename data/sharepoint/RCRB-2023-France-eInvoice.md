# HPE RCRB Assessment: France B2B e-Invoicing Mandate
## Document Reference: RCRB-FR-2023-042
**Status:** COMPLETED — Implementation closed 2023-11-30
**Author:** EMEA Compliance Engineering / Tax Technology Team
**Reviewed by:** M. Dupont (EMEA Finance), S. Patel (IT Architecture)
**Date:** 2023-08-14

---

## 1. Regulatory Context

France's mandatory B2B e-invoicing (Facture Electronique) rollout under Ordonnance 2021-1190 required all large enterprises to begin receiving structured e-invoices via the Chorus Pro platform and registered Peppol access points. This RCRB assessment covered HPE France's compliance obligations.

**Mandate dates applicable to HPE:**
- 2023-09-01: Large enterprise RECEIVE capability (Chorus Pro + Peppol)
- 2024-01-01: Large enterprise TRANSMIT — Chorus Pro for B2G, Peppol AS4 for B2B

**Format:** Factur-X (hybrid PDF/A-3 + XML ZUGFeRD 2.0) **or** UBL 2.1 / CII via Peppol BIS Billing 3.0

---

## 2. Scope of Assessment

| System | Assessment Type | Outcome |
|--------|----------------|---------|
| SAP S/4HANA EMEA PRD | Impact + Change | 4 code changes, 2 config changes |
| SAP DCP | Activation | France country activated |
| HPE Invoice Delivery Service | Code change | Chorus Pro routing added |
| SAP MDG Customer Governance | Policy change | SIRET number made mandatory for FR |
| Peppol AS4 Access Point | Configuration | FR participant ID registered |

---

## 3. Key Findings and Changes Made

### 3.1 SAP S/4HANA — Z_HPE_PEPPOL_OUTPUT (ABAP)
**Finding:** Output routing function module had no France-specific logic; all French invoices routed to PDF_EMAIL.
**Change:** Added `WHEN 'FR' -> channel = 'CHORUS_PRO'` to country routing CASE statement.
**Effort:** 2 days (developer + unit test).

### 3.2 SAP MDG — Customer Master Governance
**Finding:** French customers lacked SIRET number (equivalent to VAT ID for B2G invoices) in KNA1. Field optional in MDG workflow.
**Change:** MDG governance workflow updated — STCEG mandatory for LAND1=FR (B2G) and LAND1=FR enterprises.
**Lessons learned:** Making an optional SAP MDG field mandatory requires MDG workflow change + data remediation for existing customers. 847 customer records updated. Plan 3+ months lead time for similar changes.

### 3.3 HPE Invoice Delivery Service (Java)
**Finding:** `COUNTRY_CHANNEL` map had no FR entry; defaulted to `PDF_EMAIL`.
**Change:** Added `"FR", "CHORUS_PRO"` to map. Route through `PeppolRouter.submitChorusPro()`.
**Finding (CRITICAL):** During testing, discovered that `validateAndEnrich()` was not being called for the Chorus Pro path because channel determination and validation were in the wrong order.
**Change:** Moved `customerVatService.validateAndEnrich(invoice)` to execute BEFORE channel lookup (not inside the `if (!"PDF_EMAIL".equals(channel))` block).

> **NOTE FOR FUTURE ASSESSMENTS:** This validation ordering bug exists in the current codebase for any country that is NOT already in the COUNTRY_CHANNEL map. If a new mandate is added (e.g. Belgium) without also fixing the validation order, Belgian customers whose channel lookup fails will bypass VAT validation and receive a PDF instead of Peppol. **This must be fixed as part of the Belgium rollout.**

### 3.4 Peppol Access Point — FR Participant Registration
**Effort:** 4 weeks (Storecove registration, NANOG SMP entry, test exchange with DGFiP test endpoint).
**Lessons learned:** Peppol participant registration must be initiated at least 6 weeks before go-live.

---

## 4. Fields Changed vs. Belgium Outlook

| Peppol Field | France Change | Belgium Outlook |
|--------------|---------------|-----------------|
| BT-031 Seller VAT | No change (FR company already set) | No change expected |
| BT-048 Buyer VAT | SIRET made mandatory in MDG | **STCEG must be made mandatory in MDG for BE** |
| BT-9 Payment Due Date | No change (already set) | Must verify for all billing types |
| BG-23 VAT Breakdown | Validated via Chorus Pro schematron | Must verify BSEG grouping logic |
| Channel | CHORUS_PRO added | PEPPOL_AS4 must be added for BE |

---

## 5. Reusable Artifacts

The following can be **reused directly** for Belgium assessment:
- MDG governance workflow template (change LAND1 filter from FR to BE)
- Peppol AS4 access point test script (`scripts/peppol_test_exchange.py`)
- ABAP transport for Z_HPE_PEPPOL_OUTPUT country routing (basis for Belgium addition)
- Customer data remediation runbook (update for LAND1=BE scope)

---

## 6. Retrospective

**What worked:** Early engagement with SAP DCP team on country activation (8 weeks lead time sufficient).
**What didn't:** MDG field governance change was underestimated — 3 weeks longer than planned due to data remediation of existing records. For Belgium, start MDG change immediately.
**Critical lesson:** Fix the `validateAndEnrich` call order in `InvoiceDeliveryService` before Belgium go-live — this is a latent defect that will cause compliance failures.

---
*This document is stored in HPE SharePoint: Compliance/RCRB/Assessments/2023/*
*Related Jira epic: RCRB-FR-2023*
