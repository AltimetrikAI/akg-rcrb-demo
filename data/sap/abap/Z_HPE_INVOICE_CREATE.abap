FUNCTION Z_HPE_INVOICE_CREATE.
*"----------------------------------------------------------------------
*"*"Local Interface:
*"  IMPORTING
*"     VALUE(IV_VBELN)   TYPE  VBELN       " Sales order number
*"     VALUE(IV_FKART)   TYPE  FKART DEFAULT 'F2'
*"  EXPORTING
*"     VALUE(ES_RESULT)  TYPE  ZBILL_RESULT_HPE
*"  EXCEPTIONS
*"     CUSTOMER_NOT_FOUND
*"     INVALID_VAT_NUMBER
*"     BILLING_FAILED
*"----------------------------------------------------------------------
* HPE EMEA - Billing Document Creation
* Creates SD billing document from sales order.
* Enforces e-invoice compliance for mandated countries (BE, IT, FR).
*
* Change history:
*   2023-09 - Initial version
*   2024-03 - Added Peppol output routing
*   2024-11 - Belgium mandate preparation (BT-031 enforcement)
*----------------------------------------------------------------------

  DATA: ls_vbak   TYPE vbak,
        ls_vbrk   TYPE vbrk,
        ls_kna1   TYPE kna1,
        lt_vbrp   TYPE TABLE OF vbrp,
        lv_valid  TYPE boole_d,
        lv_datum  TYPE datum.

  " ----------------------------------------------------------------
  " Step 1: Read sales order header (VBAK)
  " ----------------------------------------------------------------
  SELECT SINGLE bukrs kunnr waerk auart vkorg
    INTO CORRESPONDING FIELDS OF ls_vbak
    FROM vbak
   WHERE vbeln = iv_vbeln.

  IF sy-subrc <> 0.
    RAISE customer_not_found.
  ENDIF.

  " ----------------------------------------------------------------
  " Step 2: Read customer master (KNA1) - VAT and address data
  "         KNA1.STCEG = VAT Registration No. (Peppol BT-048 buyer)
  " ----------------------------------------------------------------
  SELECT SINGLE kunnr name1 stceg land1 stras ort01 pstlz adrnr
    INTO CORRESPONDING FIELDS OF ls_kna1
    FROM kna1
   WHERE kunnr = ls_vbak-kunnr.

  " ----------------------------------------------------------------
  " Step 3: VAT validation for e-invoice mandated countries
  "         Belgium (BE): mandatory from 2026-01-01 per Royal Decree
  " ----------------------------------------------------------------
  IF ls_kna1-land1 = 'BE' OR
     ls_kna1-land1 = 'IT' OR
     ls_kna1-land1 = 'FR'.

    CALL FUNCTION 'Z_HPE_VATCHECK'
      EXPORTING
        iv_kunnr = ls_kna1-kunnr
        iv_stceg = ls_kna1-stceg
        iv_land1 = ls_kna1-land1
      IMPORTING
        ev_valid = lv_valid
      EXCEPTIONS
        invalid_vat_number = 1.

    IF sy-subrc <> 0 OR lv_valid = abap_false.
      RAISE invalid_vat_number.
    ENDIF.
  ENDIF.

  " ----------------------------------------------------------------
  " Step 4: Populate billing document header (VBRK)
  "         Key Peppol fields mapped here:
  "           VBRK-STCEG  -> BT-031 (Seller VAT Identifier)
  "           VBRK-WAERK  -> BT-5   (Invoice Currency Code)
  "           VBRK-ZFAELL -> BT-9   (Payment Due Date)
  " ----------------------------------------------------------------
  ls_vbrk-fkart  = iv_fkart.
  ls_vbrk-bukrs  = ls_vbak-bukrs.
  ls_vbrk-waerk  = ls_vbak-waerk.            " BT-5: Currency code
  ls_vbrk-kunnr  = ls_vbak-kunnr.
  ls_vbrk-stceg  = 'BE0471938028'.           " BT-031: HPE Belgium entity VAT
  ls_vbrk-zfaell = sy-datum + 30.            " BT-9:  Payment due date (30 days net)
  ls_vbrk-vkorg  = ls_vbak-vkorg.

  " ----------------------------------------------------------------
  " Step 5: Read billing items (VBRP) from sales order positions
  " ----------------------------------------------------------------
  SELECT vbeln posnr matnr arktx netwr mwsbp mwskz
    INTO TABLE lt_vbrp
    FROM vbrp
   WHERE vbeln = iv_vbeln.

  " ----------------------------------------------------------------
  " Step 6: Post accounting document (FI) with VAT breakdown
  "         Calls Z_HPE_FI_TAXPOST which builds BG-23 BSEG lines
  " ----------------------------------------------------------------
  CALL FUNCTION 'Z_HPE_FI_TAXPOST'
    EXPORTING
      is_vbrk     = ls_vbrk
    TABLES
      it_vbrp     = lt_vbrp
    IMPORTING
      ev_belnr    = es_result-belnr
    EXCEPTIONS
      posting_failed = 1.

  IF sy-subrc <> 0.
    RAISE billing_failed.
  ENDIF.

  " ----------------------------------------------------------------
  " Step 7: Trigger invoice output - routes to Peppol DCP or PDF
  " ----------------------------------------------------------------
  CALL FUNCTION 'Z_HPE_PEPPOL_OUTPUT'
    EXPORTING
      is_vbrk    = ls_vbrk
      iv_country = ls_kna1-land1
    EXCEPTIONS
      output_failed = 1.

  es_result-vbeln   = ls_vbrk-vbeln.
  es_result-fkart   = ls_vbrk-fkart.
  es_result-success = abap_true.

ENDFUNCTION.
