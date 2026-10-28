# HPE EMEA E-Invoicing Compliance Policy
## Document Reference: IT-POL-EINV-EMEA-001 v2.1
**Owner:** EMEA Finance Compliance / Tax Technology CoE
**Last Updated:** 2024-03-15
**Review Cycle:** Annual
**Classification:** Internal Use

---

## 1. Purpose and Scope

This policy governs HPE's obligations and technical approach for electronic invoice exchange across EMEA jurisdictions. It applies to all HPE legal entities operating in EMEA with B2B or B2G invoice transactions.

**In-scope systems:**
- SAP S/4HANA EMEA PRD (primary billing engine)
- SAP Document Compliance Platform (DCP) — format generation
- HPE Invoice Delivery Service — channel routing microservice
- HPE Customer VAT Service — customer master enrichment
- Peppol AS4 Access Point — network transport

---

## 2. Mandatory E-Invoicing by Country

| Country | Mandate Type | Format | Channel | HPE Effective Date | Status |
|---------|-------------|--------|---------|-------------------|--------|
| Italy | B2B + B2G mandatory | FatturaPA XML | SDI (Sistema di Interscambio) | 2019-01-01 | LIVE |
| France | B2G mandatory | Factur-X / UBL 2.1 | Chorus Pro | 2023-09-01 | LIVE |
| Netherlands | B2G mandatory | UBL 2.1 | Peppol AS4 | 2019-04-01 | LIVE |
| Belgium | **B2B mandatory** | **Peppol BIS 3.0 (UBL 2.1)** | **Peppol AS4** | **2026-01-01** | **IN ASSESSMENT** |
| Germany | B2B receive | ZUGFeRD / XRechnung | Peppol AS4 | 2025-01-01 | PLANNED |
| Spain | B2B mandatory | Factura-e / UBL | Peppol / FACeB2B | 2027 | FUTURE |

---

## 3. Technical Standards

### 3.1 Preferred Format
HPE standardizes on **Peppol BIS Billing 3.0 (UBL 2.1 XML)** where country regulation permits, to minimize the number of distinct invoice format implementations. Country-specific formats (FatturaPA, Factur-X) are used only where mandated by local law.

### 3.2 Network Transport
**Peppol AS4** is the preferred network. Country-specific government portals (SDI for Italy, Chorus Pro for France) are used where required.

### 3.3 Format Validation
All Peppol invoices are validated against EN 16931-1 schematron rules before submission. Country-specific schematron rules are applied for IT and FR. Belgium will use the standard PEPPOL-EN16931-UBL validation ruleset.

---

## 4. Mandatory Data Requirements

The following customer master fields are **mandatory** for e-invoice channels:

| Field | SAP Table | Peppol BT | Applies To | MDG Governance |
|-------|-----------|-----------|-----------|---------------|
| VAT Registration No. | KNA1.STCEG | BT-048 | All e-invoice mandates | **MANDATORY for IT, FR (B2G)**; must be extended to BE |
| Company Name | KNA1.NAME1 | BT-44 | All | Mandatory (existing) |
| Street Address | KNA1.STRAS | BT-50 | All | Mandatory (existing) |
| City | KNA1.ORT01 | BT-52 | All | Mandatory (existing) |
| Postal Code | KNA1.PSTLZ | BT-53 | All | Mandatory (existing) |
| Country | KNA1.LAND1 | BT-55 | All | Mandatory (existing) |
| Payment Due Date | VBRK.ZFAELL | BT-9 | BE, IT | Set by Z_HPE_INVOICE_CREATE |

> **POLICY DECISION (2024-03-15):** As part of Belgium readiness, the MDG governance workflow SHALL be updated to require KNA1.STCEG for all customers with LAND1=BE before 2025-06-30 to allow sufficient data remediation time before the 2026-01-01 mandate.

---

## 5. RCRB Process for New Mandates

When a new e-invoicing mandate is identified, a Regulatory Change and Risk Business (RCRB) assessment must be initiated:

**Step 1 — Detect:** Monitor EU Commission publications, national tax authority (FPS Finance BE, HMRC, BZSt) announcements. AI-assisted monitoring via AKG platform (planned).

**Step 2 — Assess:** RCRB assessment covering:
  - Impacted SAP billing objects (VBRK, VBRP, BSEG fields)
  - Impacted application landscape (CMDB-driven impact analysis)
  - Required data quality changes (MDG governance updates)
  - Effort estimation and risk scoring (L1/L2/L3 impact levels)

**Step 3 — Plan:** RCRB Board approval, Jira epic creation, sprint allocation.

**Step 4 — Implement:** SAP configuration, ABAP code changes, Java microservice changes, MDG workflow updates.

**Step 5 — Test:** Peppol conformance test (POLIFONIA), user acceptance testing.

**Step 6 — Go-Live:** Phased rollout by customer segment. Hypercare 30 days.

---

## 6. Audit and Archival

All e-invoices must be archived for **7 years** per EU VAT Directive and national implementations:
- Belgium: 7 years (Belgian VAT Code Article 60)
- Italy: 10 years (DPR 633/1972)
- France: 10 years (Code Général des Impôts)

Archive responsibility: Databricks Analytics Platform reads BKPF/BSEG from SAP and stores structured tax data. ZHPE_EINVOICE_AUDIT table provides per-invoice submission evidence.

---

## 7. Known Issues and Open Items

| Ref | Issue | Severity | Owner | Target |
|-----|-------|----------|-------|--------|
| RCRB-BE-2024-001 | KNA1.STCEG not mandatory in MDG for LAND1=BE | HIGH | Data Governance | 2025-06-30 |
| RCRB-BE-2024-002 | InvoiceDeliveryService: validateAndEnrich() bypass on PDF_EMAIL path | HIGH | Integration Team | 2025-Q3 |
| RCRB-BE-2024-003 | Peppol participant ID for Belgium: not yet registered | HIGH | Integration Team | 2025-09-01 |
| RCRB-BE-2024-004 | VBRK.ZFAELL (BT-9) not set for all billing types | MEDIUM | ABAP Team | 2025-Q4 |
| RCRB-BE-2024-005 | BSEG tax line grouping (BG-23) — verify Z_HPE_FI_TAXPOST logic | MEDIUM | ABAP Team | 2025-Q3 |

---

## 8. Contacts

| Role | Name | Email |
|------|------|-------|
| Policy Owner | EMEA Finance Compliance | emea-tax-compliance@hpe.com |
| Technical Lead | Integration & Middleware | integration-team@hpe.com |
| SAP Platform | ERP Platform Team | erp-platform@hpe.com |
| Data Governance | MDG CoE | data-governance@hpe.com |

---
*Stored in HPE SharePoint: Compliance/Policies/eInvoicing/*
*Previous version: v2.0 (2023-03-10) — added France LIVE status*
