FUNCTION Z_HPE_VATCHECK.
*"----------------------------------------------------------------------
*"*"Local Interface:
*"  IMPORTING
*"     VALUE(IV_KUNNR) TYPE  KUNNR
*"     VALUE(IV_STCEG) TYPE  STCEG
*"     VALUE(IV_LAND1) TYPE  LAND1
*"  EXPORTING
*"     VALUE(EV_VALID) TYPE  BOOLE_D
*"  EXCEPTIONS
*"     INVALID_VAT_NUMBER
*"----------------------------------------------------------------------
* HPE EMEA - VAT Registration Number Validation
* Validates customer VAT registration number against country-specific
* format rules. Called before billing document creation.
*
* Peppol field mappings:
*   KNA1-STCEG (seller context) -> BT-031 Seller VAT Identifier
*   KNA1-STCEG (buyer context)  -> BT-048 Buyer VAT Identifier
*
* Belgium (Royal Decree 9 March 2022):
*   Format: BE + 10 digits (e.g. BE0471938028)
*   Mandatory for all B2B invoices from 2026-01-01
*----------------------------------------------------------------------

  DATA: lv_stceg  TYPE stceg,
        lv_land1  TYPE land1,
        lv_len    TYPE i,
        lv_digits TYPE string.

  " Use passed values or re-read from KNA1
  lv_stceg = iv_stceg.
  lv_land1 = iv_land1.

  IF lv_stceg IS INITIAL OR lv_land1 IS INITIAL.
    SELECT SINGLE stceg land1
      INTO (lv_stceg, lv_land1)
      FROM kna1
     WHERE kunnr = iv_kunnr.

    IF sy-subrc <> 0.
      ev_valid = abap_false.
      RAISE invalid_vat_number.
    ENDIF.
  ENDIF.

  " Country-specific VAT format validation
  CASE lv_land1.

    WHEN 'BE'.
      " Belgian VAT: BE followed by exactly 10 digits
      " Maps to Peppol BT-031 (seller) and BT-048 (buyer)
      " Mandatory enforcement from 2026-01-01 per Belgian Royal Decree
      IF lv_stceg IS INITIAL.
        " CHANGE REQUIRED: currently returns true if blank for non-mandated customers
        " After 2026-01-01: must raise INVALID_VAT_NUMBER for all BE customers
        ev_valid = abap_false.
        RAISE invalid_vat_number.
      ENDIF.

      lv_len = strlen( lv_stceg ).
      IF lv_len <> 12.
        ev_valid = abap_false.
        RAISE invalid_vat_number.
      ENDIF.

      IF lv_stceg(2) <> 'BE'.
        ev_valid = abap_false.
        RAISE invalid_vat_number.
      ENDIF.

      " Verify remaining 10 characters are digits
      lv_digits = lv_stceg+2.
      IF lv_digits CN '0123456789'.
        ev_valid = abap_false.
        RAISE invalid_vat_number.
      ENDIF.

    WHEN 'DE'.
      " German VAT: DE followed by 9 digits
      IF lv_stceg(2) <> 'DE' OR strlen( lv_stceg ) <> 11.
        ev_valid = abap_false.
        RAISE invalid_vat_number.
      ENDIF.

    WHEN 'FR'.
      " French VAT: FR + 2 alphanumeric + 9 digits = 13 chars
      IF lv_stceg(2) <> 'FR' OR strlen( lv_stceg ) <> 13.
        ev_valid = abap_false.
        RAISE invalid_vat_number.
      ENDIF.

    WHEN 'NL'.
      " Dutch VAT: NL + 9 digits + B + 2 digits = 14 chars
      IF lv_stceg(2) <> 'NL' OR strlen( lv_stceg ) <> 14.
        ev_valid = abap_false.
        RAISE invalid_vat_number.
      ENDIF.

    WHEN OTHERS.
      " Non-mandated countries: presence check only
      IF lv_stceg IS INITIAL.
        ev_valid = abap_false.
      ELSE.
        ev_valid = abap_true.
      ENDIF.
      RETURN.

  ENDCASE.

  ev_valid = abap_true.

ENDFUNCTION.
