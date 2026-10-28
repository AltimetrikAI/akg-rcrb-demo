FUNCTION Z_HPE_FI_TAXPOST.
*"----------------------------------------------------------------------
*"*"Local Interface:
*"  IMPORTING
*"     VALUE(IS_VBRK)  TYPE  VBRK
*"  TABLES
*"     IT_VBRP         TYPE  VBRPTAB
*"  EXPORTING
*"     VALUE(EV_BELNR) TYPE  BELNR_D
*"  EXCEPTIONS
*"     POSTING_FAILED
*"     INVALID_TAX_CODE
*"----------------------------------------------------------------------
* HPE EMEA - FI Accounting Document Posting with Tax
* Posts accounting document (BKPF/BSEG) for billing document.
*
* BG-23 VAT Breakdown requirement (Belgium / Peppol):
*   Each distinct VAT rate must produce a SEPARATE BSEG line item.
*   Current implementation consolidates tax lines - CHANGE REQUIRED.
*
* BSEG fields mapped to Peppol:
*   BSEG-MWSKZ -> tax code -> BT-119 (VAT category code)
*   BSEG-HWBAS -> taxable amount -> BT-116 (VAT taxable amount)
*   BSEG-WMWST -> tax amount -> BT-117 (VAT category tax amount)
*----------------------------------------------------------------------

  DATA: ls_bkpf      TYPE bkpf,
        ls_bseg      TYPE bseg,
        lt_bseg      TYPE TABLE OF bseg,
        lt_tax_items TYPE TABLE OF vbrp,
        ls_vbrp      TYPE vbrp,
        lv_hwbas     TYPE wrbtr,
        lv_wmwst     TYPE wrbtr,
        lv_mwskz     TYPE mwskz.

  " ----------------------------------------------------------------
  " Step 1: Build accounting document header (BKPF)
  "   BKPF-WAERS -> BT-5 (Invoice Currency Code)
  " ----------------------------------------------------------------
  ls_bkpf-bukrs = is_vbrk-bukrs.
  ls_bkpf-blart = 'DR'.                   " Customer invoice
  ls_bkpf-bldat = sy-datum.
  ls_bkpf-budat = sy-datum.
  ls_bkpf-waers = is_vbrk-waerk.          " BT-5: currency
  ls_bkpf-xblnr = is_vbrk-vbeln.          " Reference: billing doc
  ls_bkpf-bktxt = 'HPE EMEA Invoice'.

  " ----------------------------------------------------------------
  " Step 2: Customer receivable line (debit)
  " ----------------------------------------------------------------
  CLEAR ls_bseg.
  ls_bseg-koart  = 'D'.
  ls_bseg-kunnr  = is_vbrk-kunnr.
  ls_bseg-wrbtr  = REDUCE wrbtr( INIT s = 0
                                 FOR  v IN it_vbrp
                                 NEXT s = s + v-netwr + v-mwsbp ).
  ls_bseg-shkzg  = 'S'.
  APPEND ls_bseg TO lt_bseg.

  " ----------------------------------------------------------------
  " Step 3: BG-23 - One tax BSEG line per distinct VAT rate
  "
  "   CURRENT ISSUE: loop consolidates all tax into one BSEG line.
  "   REQUIRED CHANGE: group by MWSKZ, one line per rate.
  "   This is the BG-23 compliance gap for Belgium e-invoicing.
  " ----------------------------------------------------------------
  SORT it_vbrp BY mwskz.

  LOOP AT it_vbrp INTO ls_vbrp.

    AT NEW mwskz.
      " Start of new VAT rate group - initialize accumulators
      CLEAR: lv_hwbas, lv_wmwst.
      lv_mwskz = ls_vbrp-mwskz.
    ENDAT.

    " Accumulate base and tax amounts for this rate
    lv_hwbas = lv_hwbas + ls_vbrp-netwr.   " BT-116: taxable amount
    lv_wmwst = lv_wmwst + ls_vbrp-mwsbp.   " BT-117: tax amount

    AT END OF mwskz.
      " Write one BSEG tax line per rate (BG-23 requirement)
      CLEAR ls_bseg.
      ls_bseg-koart  = 'S'.                 " Tax account line
      ls_bseg-mwskz  = lv_mwskz.            " BT-119: VAT category code
      ls_bseg-hwbas  = lv_hwbas.            " BT-116: VAT taxable amount
      ls_bseg-wmwst  = lv_wmwst.            " BT-117: VAT category tax amount
      ls_bseg-shkzg  = 'H'.
      APPEND ls_bseg TO lt_bseg.
    ENDAT.

  ENDLOOP.

  " ----------------------------------------------------------------
  " Step 4: Post document via FI BAPI
  " ----------------------------------------------------------------
  CALL FUNCTION 'POSTING_INTERFACE_DOCUMENT'
    EXPORTING
      is_bkpf              = ls_bkpf
    TABLES
      it_bseg              = lt_bseg
    IMPORTING
      ev_belnr             = ev_belnr
    EXCEPTIONS
      posting_not_possible = 1.

  IF sy-subrc <> 0.
    RAISE posting_failed.
  ENDIF.

ENDFUNCTION.
