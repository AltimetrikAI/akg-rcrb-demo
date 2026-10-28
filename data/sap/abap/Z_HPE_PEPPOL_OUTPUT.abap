FUNCTION Z_HPE_PEPPOL_OUTPUT.
*"----------------------------------------------------------------------
*"*"Local Interface:
*"  IMPORTING
*"     VALUE(IS_VBRK)    TYPE  VBRK
*"     VALUE(IV_COUNTRY) TYPE  LAND1
*"  EXCEPTIONS
*"     OUTPUT_FAILED
*"     CHANNEL_NOT_CONFIGURED
*"----------------------------------------------------------------------
* HPE EMEA - e-Invoice Output Processing
* Determines delivery channel and submits invoice to SAP DCP.
* Routes to Peppol AS4, SDI (Italy), Chorus Pro (France), or PDF.
*
* SAP DCP integration:
*   RFC destination: HPE_DCP_PRD
*   Format: Peppol BIS Billing 3.0 (UBL 2.1)
*
* Belgium mandate (Royal Decree 2022):
*   Channel: PEPPOL_AS4 mandatory from 2026-01-01
*   Format:  UBL 2.1 or UN/CEFACT CII
*   BT-031 (seller VAT) must be present in XML output
*----------------------------------------------------------------------

  DATA: lv_channel    TYPE char20,
        lv_format     TYPE char20,
        ls_dcp        TYPE zdcp_submit_hpe,
        lv_doc_id     TYPE char40,
        lv_mandatory  TYPE abap_bool.

  " ----------------------------------------------------------------
  " Determine mandatory e-invoice channel by country
  " ----------------------------------------------------------------
  CASE iv_country.
    WHEN 'BE'.
      lv_channel   = 'PEPPOL_AS4'.
      lv_format    = 'UBL_21'.
      lv_mandatory = abap_true.     " Mandatory from 2026-01-01

    WHEN 'IT'.
      lv_channel   = 'SDI_IT'.      " Sistema di Interscambio
      lv_format    = 'FATTURAPA'.
      lv_mandatory = abap_true.

    WHEN 'FR'.
      lv_channel   = 'CHORUS_PRO'.  " French public sector mandate
      lv_format    = 'FACTURX'.
      lv_mandatory = abap_false.    " B2G only currently

    WHEN 'NL'.
      lv_channel   = 'PEPPOL_AS4'.
      lv_format    = 'UBL_21'.
      lv_mandatory = abap_true.

    WHEN OTHERS.
      lv_channel   = 'PDF_EMAIL'.   " Default: PDF via email
      lv_format    = 'PDF'.
      lv_mandatory = abap_false.
  ENDCASE.

  " ----------------------------------------------------------------
  " Build DCP submission structure
  " Peppol BT-031 (Seller VAT) must appear in outbound XML
  " ----------------------------------------------------------------
  ls_dcp-vbeln      = is_vbrk-vbeln.
  ls_dcp-channel    = lv_channel.
  ls_dcp-format     = lv_format.
  ls_dcp-seller_vat = is_vbrk-stceg.   " BT-031: HPE entity VAT
  ls_dcp-currency   = is_vbrk-waerk.   " BT-5:   Invoice currency
  ls_dcp-due_date   = is_vbrk-zfaell.  " BT-9:   Payment due date
  ls_dcp-mandatory  = lv_mandatory.

  " ----------------------------------------------------------------
  " Submit to SAP Document Compliance Platform via RFC
  " DCP handles Peppol AS4 network routing and XML generation
  " ----------------------------------------------------------------
  CALL FUNCTION 'DCP_DOCUMENT_SUBMIT'
    DESTINATION 'HPE_DCP_PRD'
    EXPORTING
      is_params  = ls_dcp
    IMPORTING
      ev_doc_id  = lv_doc_id
    EXCEPTIONS
      not_configured = 1
      submit_failed  = 2.

  CASE sy-subrc.
    WHEN 1.
      RAISE channel_not_configured.
    WHEN 2.
      IF lv_mandatory = abap_true.
        RAISE output_failed.
      ENDIF.
      " Non-mandatory: log warning but continue
      MESSAGE 'Peppol submission failed for non-mandatory country' TYPE 'W'.
  ENDCASE.

  " ----------------------------------------------------------------
  " Log e-invoice submission to compliance audit table
  " ----------------------------------------------------------------
  INSERT zhpe_einvoice_audit FROM @( VALUE #(
    guid      = cl_system_uuid=>create_uuid_c32_static( )
    vbeln     = is_vbrk-vbeln
    channel   = lv_channel
    doc_id    = lv_doc_id
    country   = iv_country
    erdat     = sy-datum
    erzet     = sy-uzeit
    uname     = sy-uname ) ).

ENDFUNCTION.
