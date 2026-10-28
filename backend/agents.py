"""
AKG Assessment Agent Pipeline
-----------------------------------
5-agent sequential pipeline that traverses the 4 KGs and produces
a structured L1/L2/L3 regulatory impact assessment.

Agents:
  1. RegulationAgent — reads Entity KG: obligations, gaps, compliance score
  2. ProcessAgent    — traverses Process KG: impacted steps by technology
  3. SystemsAgent    — traverses Systems KG: impacted applications and owners
  4. DataAgent       — traverses Data KG: impacted tables and remediation actions
  5. SynthesisAgent  — synthesizes all findings into L1/L2/L3 report

Each agent receives pre-structured business context from the semantic layer
rather than raw Cypher results, so prompts focus on interpretation.
"""
import anthropic
import semantic_layer as sem


def _stream_agent(claude: anthropic.Anthropic, system: str, messages: list):
    """Yield text chunks as Claude generates them (token streaming)."""
    with claude.messages.stream(
        model      = "claude-sonnet-4-6",
        max_tokens = 4096,
        system     = system,
        messages   = messages,
    ) as stream:
        for chunk in stream.text_stream:
            yield chunk


def run_assessment(regulation_name: str, country: str = "BE"):
    """
    Run the 5-agent impact assessment pipeline.
    Yields (agent_name, content) tuples as each agent produces output.
    """
    claude = anthropic.Anthropic()

    # ── Pre-fetch shared context (used across multiple agents) ────────────────
    compliance  = sem.get_compliance_summary(country)
    comp_header = sem.format_compliance_summary(compliance)

    # ── Agent 1: Regulation Agent ──────────────────────────────────────────────
    yield "regulation", "Querying Entity KG for obligations and compliance gaps..."

    obligations     = sem.get_all_obligations(country)
    blockers        = sem.get_critical_blockers(country)
    obligations_txt = sem.format_obligations(obligations)
    blockers_txt    = sem.format_critical_blockers(blockers)

    for chunk in _stream_agent(claude,
        "You are an expert in EU e-invoicing regulations and Peppol BIS 3.0. "
        "You receive pre-analyzed compliance data and translate it into clear business language.",
        [{"role": "user", "content":
            f"Summarize the e-invoicing regulatory obligations and compliance status "
            f"in 4-6 sentences for a business audience. Lead with what is most urgent.\n\n"
            f"COMPLIANCE STATUS:\n{comp_header}\n\n"
            f"CRITICAL BLOCKERS (HIGH impact, unresolved):\n{blockers_txt}\n\n"
            f"ALL OBLIGATIONS:\n{obligations_txt}"}]
    ):
        yield "regulation", chunk

    # ── Agent 2: Process Agent ─────────────────────────────────────────────────
    yield "process", "Traversing Process KG for impacted business process steps..."

    steps     = sem.get_impacted_process_steps()
    steps_txt = sem.format_process_steps(steps)

    for chunk in _stream_agent(claude,
        "You are an integration architect specializing in O2C process compliance. "
        "You receive a structured list of impacted code modules and translate them into "
        "clear, prioritized change actions for a development team.",
        [{"role": "user", "content":
            f"List the TOP 5 most critical process-level changes required for compliance. "
            f"For each: name the module, state what Peppol field it must handle, "
            f"describe the specific code change, and explain the risk if skipped.\n\n"
            f"COMPLIANCE STATUS:\n{comp_header}\n\n"
            f"IMPACTED PROCESS STEPS:\n{steps_txt}\n\n"
            f"FORMAT: numbered bullet list. One step per bullet. "
            f"Lead with ABAP changes, then Java. Be specific."}]
    ):
        yield "process", chunk

    # ── Agent 3: Systems Agent ─────────────────────────────────────────────────
    yield "systems", "Traversing Systems KG for impacted applications..."

    systems     = sem.get_impacted_systems()
    systems_txt = sem.format_systems(systems)

    for chunk in _stream_agent(claude,
        "You are an enterprise IT architect specializing in CMDB-based change impact analysis. "
        "You receive a structured list of impacted systems and translate it into a delivery plan.",
        [{"role": "user", "content":
            f"For each impacted system, state: the change type "
            f"(Code Change / Config Change / MDG Workflow / Registration), "
            f"effort estimate (S=days, M=1-2 weeks, L=3+ weeks), owner, and risk.\n\n"
            f"Change type definitions:\n"
            + "\n".join(f"  {k}: {v}" for k, v in sem.CHANGE_TYPE_DEFINITIONS.items()) + "\n\n"
            f"COMPLIANCE STATUS:\n{comp_header}\n\n"
            f"IMPACTED SYSTEMS:\n{systems_txt}\n\n"
            f"FORMAT: table — System | Change Type | Effort | Owner | Risk"}]
    ):
        yield "systems", chunk

    # ── Agent 4: Data Agent ────────────────────────────────────────────────────
    yield "data", "Traversing Data KG for impacted data fields and remediation actions..."

    fields     = sem.get_data_gaps(country)
    fields_txt = sem.format_data_gaps(fields)

    for chunk in _stream_agent(claude,
        "You are a data architect specializing in data quality for regulatory compliance. "
        "You receive a structured list of impacted data fields and translate them into "
        "concrete data remediation actions for a data stewardship team.",
        [{"role": "user", "content":
            f"List the DATA QUALITY actions needed for compliance. "
            f"For each impacted field: state the table.field, the Peppol BT code, "
            f"what business data it represents, and the specific remediation action.\n\n"
            f"COMPLIANCE STATUS:\n{comp_header}\n\n"
            f"IMPACTED DATA FIELDS:\n{fields_txt}\n\n"
            f"FORMAT: numbered list. Prioritize fields with 'Action required' first. "
            f"Include the MDG governance change for master data fields as a standalone item."}]
    ):
        yield "data", chunk

    # ── Agent 5: Synthesis Agent ───────────────────────────────────────────────
    yield "synthesis", "Synthesizing full L1/L2/L3 impact assessment..."

    for chunk in _stream_agent(claude,
        "You are a regulatory compliance program manager preparing an executive assessment. "
        "You receive structured impact data across regulation, process, systems, and data layers "
        "and synthesize it into a clear, actionable report for executives and developers.",
        [{"role": "user", "content":
            f"Produce a complete regulatory change impact assessment.\n\n"
            f"COMPLIANCE STATUS:\n{comp_header}\n\n"
            f"CRITICAL BLOCKERS:\n{blockers_txt}\n\n"
            f"IMPACTED PROCESS STEPS:\n{steps_txt[:2000]}\n\n"
            f"IMPACTED SYSTEMS:\n{systems_txt[:1000]}\n\n"
            f"IMPACTED DATA FIELDS:\n{fields_txt[:1500]}\n\n"
            f"FORMAT — write clearly for both an executive and a developer:\n\n"
            f"## Executive Summary\n"
            f"2-3 plain-English sentences. What is broken, the deadline, "
            f"the consequence of missing it. State the readiness score.\n\n"
            f"## Priority Change Actions\n"
            f"Numbered list ordered by priority:\n"
            f"  P1 (Blockers): changes that prevent invoice transmission\n"
            f"  P2 (Required): changes needed for full compliance\n"
            f"  P3 (Confirm): items to verify/confirm as complete\n"
            f"Each item: ACTION | SYSTEM | WHAT TO CHANGE | PEPPOL FIELD | EFFORT\n\n"
            f"## Delivery Timeline\n"
            f"Month-by-month milestones to reach go-live readiness.\n\n"
            f"## Top Risk\n"
            f"One paragraph on the single highest-risk dependency.\n\n"
            f"Be specific: name tables, class names, Peppol BT codes."}]
    ):
        yield "synthesis", chunk
