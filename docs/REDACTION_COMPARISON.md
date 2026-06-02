# Redaction: homegrown layer vs. RedaktR (MCP) — evidence-based comparison

**Question asked:** is our homegrown redaction better, or are parts of RedaktR (a local PHI-redaction
MCP) better to use?

**Answer (short):** RedaktR has a **real, large recall advantage** on real data, but it **conflicts
with three of our hard constraints**, and — by its own measured benchmark — the advantage comes
almost entirely from **spaCy NER, not the MLX-LLM**. The right move is **neither replace nor ignore**:
keep our deterministic floor and add RedaktR **behind our existing `Redactor` port via an MCP seam**,
so the heavy non-portable pipeline runs as a separate gated service while our engine stays std-lib,
portable, and deterministic.

All numbers below are from RedaktR's **own** measured results file
(`OE_Samples/redaktR/workflow_comparison_results.json`, run on `ws_sample.csv`, 85,850 chars,
2025-09-06) and its README — not estimates.

## What the measured data actually shows

| Dimension | Homegrown `redaction/` | RedaktR | Source |
|---|---|---|---|
| Techniques | regex floor + optional 1 backend | 4: regex + spaCy NER + MLX-LLM + consensus | RedaktR README |
| Recall, same sample | regex-only ≈ 8 items | **4-technique: 42–49 items (+425–512%)** | results file (api 8→49, mcp 8→42) |
| Source of the recall | regex | **spaCy NER (avg 29 items, 0.93s)** | `technique_performance` |
| MLX-LLM yield | n/a | **0.7 items avg, 8.3s** (slowest, near-zero) | `technique_performance` |
| ast-grep yield (CSV) | n/a | **0 items** | results file |
| Speed | <1 ms, deterministic | 2.6–9.8 s | results file |
| Cross-platform | macOS/Linux/Windows, std-lib | **MLX = Apple-only; spaCy via Docker; Postgres/Redis/conda** | requirements.txt |
| Determinism / hash-pinnable | yes | no (LLM + consensus voting) | architecture |
| Hospital profiles, audit, chunking, file formats, MCP | none | yes, mature | RedaktR README |

### Three findings

1. **RedaktR's recall edge is real and large** — 8→42 PHI items on the identical sample. Our
   regex-only floor lands near RedaktR's "current" (≈8). For real clinical notes, that gap matters;
   our floor alone is not sufficient for real PHI.
2. **The edge is spaCy NER, not MLX.** spaCy = 29 items / 0.93 s; MLX-LLM = 0.7 items / 8.3 s;
   ast-grep = 0 on CSV. The expensive, Apple-only, non-deterministic MLX component contributes ~2%
   of detections for ~90% of the runtime. **Borrow spaCy; do not pay for the LLM** unless a domain
   eval later proves it adds recall on real notes.
3. **RedaktR conflicts with our constraints**: Apple-Silicon-bound (MLX) vs. our macOS/**Linux/
   Windows** requirement; Postgres/Redis/Docker/conda vs. our std-lib-by-default posture;
   non-deterministic vs. our hash-pinned trace. Wholesale replacement fails our own rules.

## Recommendation: MCP seam behind the `Redactor` port

Our `redaction/` package already defines a swappable `Redactor` ABC and a `LayeredRedactor` that
unions a deterministic floor with optional backends (fail-safe). That makes integration clean:

- **Keep the deterministic floor** — always-on, hash-pinnable, cross-platform, the fail-safe base
  (this is exactly RedaktR's own integration recommendation #7: "graceful degradation when
  techniques fail").
- **Add `McpRedactor`** (`redaction/mcp_backend.py`) — an optional backend that calls RedaktR's MCP
  `scan_healthcare_text` tool over the protocol and maps its spans into our `RedactionSpan`. The
  heavy, infra-bound, non-portable, non-deterministic pipeline runs as a **separate gated service**
  in the approved §8 environment; our engine stays std-lib and portable.
- **Prefer the scan with `techniques=["regex","spacy"]`** so we tap the high-yield/low-latency path
  and skip the near-zero-yield MLX (the McpRedactor sends this preference; the server may honor it).
- **WE apply the redaction** from the returned spans (not the server's redact tool), so placeholder
  formatting, span-merging, and determinism stay under our control.

### Why MCP rather than importing RedaktR's code

- Keeps `transformers`/`spacy`/`mlx`/Docker/Postgres **out of our process and dependency tree** —
  our portability + std-lib posture survives.
- The MCP server is the trust/compliance boundary: it lives in the §8-approved environment with its
  own audit trail; our engine never loads the model.
- Same gating + fail-safe discipline as the `OpenMedRedactor`: refuses to construct unless
  `ADMISSION_ENGINE_PHI_ENV_APPROVED=1`; any client error → floor still redacts (never fails open).

## What we deliberately do NOT adopt

- **MLX-LLM** as a redaction technique — its measured yield (0.7 items) does not justify the latency
  (8.3 s), Apple lock-in, or non-determinism. Re-evaluate only if a real-notes domain eval shows it
  adds recall the regex+spaCy layer misses.
- **Postgres/Redis/Docker/conda** infra — that belongs to RedaktR-as-a-service, not to our engine.
- **The server's `redact` tool** as the redaction applier — we apply from spans to keep formatting
  and determinism ours.

## Net

Homegrown floor: better on portability, determinism, speed, zero-dependency. RedaktR: better on
recall, profiles, audit, file formats. The MCP seam lets us keep our advantages **and** tap
RedaktR's recall where it counts (real PHI, approved environment) — without importing its
constraints. The `McpRedactor` backend implements this; it is gated to the approved environment and
fail-safe to the deterministic floor.
