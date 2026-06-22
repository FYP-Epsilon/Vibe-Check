# Phase 2: AI Refinement Integration

> **Phase**: 2 of 6  
> **Scope**: Integrate OpenAI GPT-4o-mini for diagnostic refinement — NOT for verification logic  
> **Prerequisite**: Phase 1 complete (core engine hardened, all tests passing)  
> **Estimated Effort**: 1–2 days  
> **Status**: Pending

---

## 1. Design Principle: LLM as Diagnostic Aid, Not Verification Authority

The fundamental rule of this phase: **LLMs improve the *explainability* of verification failures, not the *correctness* of verification itself.**

Module 02's three-layer validation (V1/V2/V3) provides mathematically independent correctness evidence. The AI refinement layer adds a **fourth, non-independent** mode that operates only on the *outputs* of V1/V2/V3 — never on the inputs. This preserves the architectural integrity of the research while significantly improving the developer experience when verification fails.

### Why This Matters for the Thesis

Using an LLM to "fix" or "refine" the WIR would create a circular dependency: the verification system would depend on the same class of tools (LLMs) that generate the untrusted code being verified. This would **invalidate the research contribution** of formal-methods-based validation.

Instead, the LLM is used in three **strictly post-hoc** roles:

| Role | Input | Output | Independence |
|------|-------|--------|--------------|
| Counterexample Explanation | V1 α-trace divergence point | Human-readable root cause | Post-hoc on V1 failure |
| Certificate Narrative | V1/V2/V3 numeric scores | Human-readable report | Post-hoc on all modes |
| Guard Simplification | Z3 counterexample + complex guard | Simplified equivalent guard | Suggestion only; V2 re-verifies |

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Module 02 Core Engine                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   V3 (AST)   │  │  V2 (Z3)     │  │  V1 (Trace)  │          │
│  │   Extractor  │  │  Symbolic    │  │  Differential│          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                  │
│         └──────────────────┼──────────────────┘                  │
│                            ▼                                     │
│              ┌─────────────────────────────┐                     │
│              │  MultiModalCertificate       │                     │
│              │  Composer (v1/v2/v3 → cert)  │                     │
│              └──────────────┬────────────────┘                     │
│                             │                                    │
└─────────────────────────────┼────────────────────────────────────┘
                              │
                              ▼  ←—— LLM Refinement Boundary
┌─────────────────────────────────────────────────────────────────┐
│                    AI Refinement Layer (NEW)                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  OpenAI GPT-4o-mini Client (gpt-4o-mini-2024-07-18)       │ │
│  │  Temperature: 0.3 (factual, low creativity)                │ │
│  │  Max tokens: 300 (concise explanations)                    │ │
│  └────────────────────────────────────────────────────────────┘ │
│         │               │                │                      │
│         ▼               ▼                ▼                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │Counterexample│ │ Certificate  │ │   Guard      │            │
│  │ Explanation  │ │  Narrative   │ │ Simplification│            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

### Temperature Selection Rationale

All three tasks use **temperature = 0.3**:
- **Code generation** typically uses 0.0–0.2 for correctness [^2^]
- **Factual Q&A** uses 0.0–0.3 to minimize hallucination [^2^]
- Our tasks are *closer to factual Q&A than code generation* — we want the LLM to interpret pre-computed divergence data, not generate creative solutions
- 0.3 provides slight variation for handling diverse divergence patterns without introducing fabrication

---

## 3. Implementation: `ai_refinement/` Package

### 3.1 Client Wrapper (`ai_refinement/client.py`)

```python
"""
OpenAI GPT-4o-mini client for diagnostic refinement.
Single provider, single model — keeps the integration minimal.
"""
import os
from dataclasses import dataclass
from typing import Optional
import httpx
from openai import AsyncOpenAI


@dataclass(frozen=True)
class RefinementConfig:
    """Configuration for AI refinement tasks."""
    model: str = "gpt-4o-mini-2024-07-18"
    temperature: float = 0.3
    max_tokens: int = 300
    # Cost: ~$0.15/M input tokens, $0.60/M output tokens (as of 2026-05)
    # Typical call: ~1K input + ~150 output = ~$0.0002 per call


class RefinementClient:
    """
    Thin wrapper around OpenAI client for Module 02 diagnostic tasks.
    
    This client is deliberately minimal — it provides a single entry point
    with consistent parameters across all three refinement tasks. It does NOT
    implement caching, retry logic, or fallback to other providers; those
    concerns are handled at the orchestrator level in main.py.
    
    Usage:
        client = RefinementClient()
        explanation = await client.complete(prompt, task="counterexample")
    """

    def __init__(self, config: Optional[RefinementConfig] = None):
        self.config = config or RefinementConfig()
        self._client = AsyncOpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            http_client=httpx.AsyncClient(timeout=30.0)
        )

    async def complete(self, prompt: str, task: str) -> str:
        """
        Send a refinement prompt to GPT-4o-mini.
        
        Args:
            prompt: The formatted prompt for the specific task
            task: Task identifier for logging ("counterexample", "narrative", "guard")
            
        Returns:
            LLM-generated text (explanation, narrative, or suggestion)
            
        Raises:
            RefinementError: On API failure (timeout, rate limit, invalid key)
        """
        try:
            response = await self._client.chat.completions.create(
                model=self.config.model,
                messages=[{
                    "role": "system",
                    "content": (
                        "You are a verification diagnostic assistant. "
                        "You analyze formal verification outputs and produce "
                        "concise, factual explanations. Do not speculate beyond "
                        "the provided data. Be precise and technical."
                    )
                }, {
                    "role": "user",
                    "content": prompt
                }],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise RefinementError(f"{task} refinement failed: {e}") from e

    async def health_check(self) -> bool:
        """Verify API key and connectivity."""
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False


class RefinementError(Exception):
    """Raised when AI refinement fails (API error, timeout, etc.)."""
    pass
```

### 3.2 Counterexample Explanation (`ai_refinement/counterexample.py`)

**When**: Called when V1 differential testing detects an α-trace mismatch (code trace ≠ WIR trace).

**Input**: The divergence point data from `DifferentialComparator._emit_certificate()`.

**Output**: 1–2 sentence human-readable explanation of *why* the code and WIR diverged.

```python
"""
Counterexample Explanation Generator

Transforms raw trace divergence data into human-readable root-cause analysis.
This helps developers understand WHY a verification failed without requiring
them to manually compare execution traces.
"""
from typing import Dict, Any, Optional

# Prompt template — deliberately structured to prevent LLM hallucination
# All fields are filled from actual trace data; no room for speculation
COUNTEREXAMPLE_PROMPT = """Analyze the following verification failure:

PYTHON CODE EXECUTION TRACE (actual):
{code_trace}

WIR (extracted IR) EXECUTION TRACE (expected):
{wir_trace}

DIVERGENCE POINT:
- Step: {divergence_step}
- Code state: {code_state}
- WIR state: {wir_state}
- Type: {divergence_type}  # one of: branch_mismatch, missing_step, extra_step, state_mismatch

Provide a concise 1-2 sentence technical explanation of what caused this divergence.
Focus on the specific control-flow decision or state variable where they differ.
Do not suggest fixes — only explain the cause."""


class CounterexampleExplainer:
    """Generates human-readable explanations for V1 trace mismatches."""

    def __init__(self, client: "RefinementClient"):
        self.client = client

    async def explain(self, divergence: Dict[str, Any]) -> Optional[str]:
        """
        Generate explanation for a trace divergence.
        
        Returns None if LLM is unavailable (non-blocking — verification continues).
        The explanation is advisory only and does not affect the certificate score.
        """
        try:
            prompt = COUNTEREXAMPLE_PROMPT.format(
                code_trace="\n".join(divergence.get("code_trace", [])[-10:]),  # Last 10 steps
                wir_trace="\n".join(divergence.get("wir_trace", [])[-10:]),
                divergence_step=divergence["step"],
                code_state=divergence["code_state"],
                wir_state=divergence["wir_state"],
                divergence_type=divergence["type"]
            )
            return await self.client.complete(prompt, task="counterexample")
        except Exception:
            # Non-blocking: if LLM fails, return structured fallback
            return self._fallback_explanation(divergence)

    def _fallback_explanation(self, divergence: Dict[str, Any]) -> str:
        """Structured explanation without LLM — always available."""
        return (
            f"Divergence at step {divergence['step']}: "
            f"Code reached {divergence['code_state']} "
            f"but WIR expected {divergence['wir_state']}. "
            f"Type: {divergence['type']}."
        )
```

### 3.3 Certificate Narrative (`ai_refinement/narrative.py`)

**When**: Called after all three validation modes complete to generate a human-readable summary.

**Input**: The `MultiModalCertificate` (V1/V2/V3 scores + combined score).

**Output**: Paragraph-format report suitable for thesis documentation or UI display.

```python
"""
Certificate Narrative Generator

Converts numeric validation scores into human-readable prose.
Useful for thesis documentation, UI display, and supervisor reports.
"""
from typing import Dict, Any

NARRATIVE_PROMPT = """Generate a concise technical verification report from these scores:

STRUCTURAL VALIDATION (V3):
- Score: {v3_score:.2f}
- Nodes extracted: {v3_nodes}
- Edges extracted: {v3_edges}
- Guards flattened to CNF: {v3_guards}
- Branch coverage: {v3_branch_coverage:.0%}

SYMBOLIC VALIDATION (V2):
- Score: {v2_score:.2f}
- Paths explored: {v2_paths}
- Solver queries: {v2_queries}
- Solver time: {v2_time:.1f}s

DYNAMIC VALIDATION (V1):
- Score: {v1_score:.2f}
- Test inputs executed: {v1_tests}
- Mismatches found: {v1_mismatches}
- Input entropy (coverage): {v1_entropy:.2f}

COMBINED CERTIFICATE: {combined_score:.4f} (threshold: 0.95)
RESULT: {result}

Write a 3-4 sentence paragraph summarizing the verification outcome.
Mention which modes contributed most to confidence and any weaknesses detected.
Use technical language appropriate for a final-year research project."""


class CertificateNarrative:
    """Generates human-readable verification reports from certificate data."""

    def __init__(self, client: "RefinementClient"):
        self.client = client

    async def generate(self, certificate: Dict[str, Any]) -> str:
        """Generate narrative from certificate. Falls back to template if LLM unavailable."""
        try:
            prompt = NARRATIVE_PROMPT.format(
                v3_score=certificate["v3"]["score"],
                v3_nodes=certificate["v3"].get("nodes", 0),
                v3_edges=certificate["v3"].get("edges", 0),
                v3_guards=certificate["v3"].get("guards_cnf", 0),
                v3_branch_coverage=certificate["v3"].get("branch_coverage", 0),
                v2_score=certificate["v2"]["score"],
                v2_paths=certificate["v2"].get("paths_explored", 0),
                v2_queries=certificate["v2"].get("solver_queries", 0),
                v2_time=certificate["v2"].get("solver_time", 0),
                v1_score=certificate["v1"]["score"],
                v1_tests=certificate["v1"].get("tests_run", 0),
                v1_mismatches=certificate["v1"].get("mismatches", 0),
                v1_entropy=certificate["v1"].get("input_entropy", 0),
                combined_score=certificate["combined"],
                result="PASSED" if certificate["combined"] >= 0.95 else "FAILED"
            )
            return await self.client.complete(prompt, task="narrative")
        except Exception:
            return self._fallback_narrative(certificate)

    def _fallback_narrative(self, cert: Dict[str, Any]) -> str:
        """Template-based narrative without LLM."""
        parts = []
        parts.append(f"Combined certificate score: {cert['combined']:.4f}.")
        parts.append(f"V3 structural: {cert['v3']['score']:.2f}, "
                     f"V2 symbolic: {cert['v2']['score']:.2f}, "
                     f"V1 dynamic: {cert['v1']['score']:.2f}.")
        parts.append("PASSED" if cert["combined"] >= 0.95 else "FAILED")
        return " ".join(parts)
```

### 3.4 Guard Simplification (`ai_refinement/guard_simplify.py`)

**When**: Called when Z3 finds a counterexample input that violates a WIR guard — suggests a simplified, equivalent guard expression.

**Important**: The simplified guard is a **suggestion only**. V2 must re-verify it before adoption. The LLM does not change the WIR directly.

```python
"""
Guard Simplification Assistant

When V2 symbolic execution finds that a guard expression is unnecessarily
complex or potentially incorrect, this module suggests a simplified equivalent.
The suggestion is verified by V2 before any adoption — the LLM never modifies
the WIR directly.
"""
from typing import Dict, Any, Tuple, Optional

GUARD_SIMPLIFY_PROMPT = """Given the following control-flow guard from a workflow:

CURRENT GUARD (CNF): {current_guard}
COUNTEREXAMPLE INPUT: {counterexample}
GUARD EVALUATION ON COUNTEREXAMPLE:
- Expected: {expected_result}
- Actual: {actual_result}

Suggest a simplified, equivalent Python boolean expression that would correctly
evaluate for all explored paths. The expression should:
1. Be syntactically valid Python
2. Use only the control variables: {control_vars}
3. Not change the semantic meaning for any explored path
4. Be simpler (fewer operators) than the current guard

Output ONLY the Python expression, no explanation."""


class GuardSimplifier:
    """Suggests simplified guard expressions. All suggestions require V2 re-verification."""

    def __init__(self, client: "RefinementClient"):
        self.client = client

    async def simplify(
        self,
        current_guard: str,
        counterexample: Dict[str, Any],
        control_vars: list[str],
        expected_result: bool,
        actual_result: bool
    ) -> Optional[str]:
        """
        Request a simplified guard expression.
        
        Returns a Python boolean expression string, or None if simplification
        is not applicable. The caller (V2 engine) must re-verify the suggestion
        using symbolic execution before adopting it.
        """
        try:
            prompt = GUARD_SIMPLIFY_PROMPT.format(
                current_guard=current_guard,
                counterexample=counterexample,
                control_vars=", ".join(control_vars),
                expected_result=expected_result,
                actual_result=actual_result
            )
            suggestion = await self.client.complete(prompt, task="guard")
            
            # Safety: validate the suggestion is syntactically valid Python
            try:
                compile(suggestion, "<guard>", "eval")
                return suggestion
            except SyntaxError:
                return None  # Reject non-Python output
                
        except Exception:
            return None
```

---

## 4. Integration Points

### 4.1 In `main.py` — Orchestration

```python
from ai_refinement.client import RefinementClient, RefinementError
from ai_refinement.counterexample import CounterexampleExplainer
from ai_refinement.narrative import CertificateNarrative
from ai_refinement.guard_simplify import GuardSimplifier

# Initialize at startup
refinement_client = RefinementClient()
counterexample_explainer = CounterexampleExplainer(refinement_client)
certificate_narrative = CertificateNarrative(refinement_client)
guard_simplifier = GuardSimplifier(refinement_client)

@app.post("/verify")
async def verify(req: VerifyRequest) -> ValidationResponse:
    # ... existing V3 → V2 → V1 pipeline ...
    
    # NEW (Phase 2): Add AI refinement to response
    explanation = None
    if cert["combined"] < 0.95 and cert["v1"]["mismatches"] > 0:
        # Only explain V1 failures (most actionable)
        explanation = await counterexample_explainer.explain(
            divergence_data
        )
    
    narrative = await certificate_narrative.generate(cert)
    
    return ValidationResponse(
        wir=wir,
        certificate=cert,
        ai_refinement={
            "counterexample_explanation": explanation,
            "narrative": narrative,
            "llm_used": True
        }
    )
```

### 4.2 Non-Blocking Error Handling

AI refinement failures must never block the verification pipeline:

```python
async def safe_refinement(refinement_call, fallback):
    """Wrapper that ensures AI refinement never blocks verification."""
    try:
        return await asyncio.wait_for(refinement_call, timeout=10.0)
    except (RefinementError, asyncio.TimeoutError):
        return fallback
```

---

## 5. Cost Analysis

| Task | Input Tokens | Output Tokens | Cost per Call | Trigger Frequency |
|------|-------------|---------------|---------------|-------------------|
| Counterexample Explanation | ~800 | ~100 | ~$0.0002 | Only on V1 failure (~20% of runs) |
| Certificate Narrative | ~600 | ~150 | ~$0.00015 | Every verification run |
| Guard Simplification | ~500 | ~80 | ~$0.0001 | Only on V2 counterexample (~10% of runs) |

**Per-workflow average cost**: ~$0.0002  
**For 100-workflow evaluation**: ~$0.02  
**Total project budget** ($5): Sufficient for ~25,000 refinement calls

---

## 6. Testing Strategy

| Test | Purpose | Validation |
|------|---------|------------|
| `test_refinement_client.py::test_health_check` | Verify API key works | Returns True with valid key |
| `test_refinement_client.py::test_timeout` | Ensure non-blocking | Returns fallback within 10s on timeout |
| `test_refinement_client.py::test_invalid_key` | Graceful degradation | Returns fallback, logs error |
| `test_counterexample.py::test_explanation_format` | Output structure | 1–2 sentences, references specific divergence |
| `test_counterexample.py::test_fallback` | LLM failure path | Returns structured fallback with divergence data |
| `test_narrative.py::test_narrative_contains_scores` | Score inclusion | Narrative mentions V1/V2/V3 scores |
| `test_guard.py::test_syntax_validation` | Safety check | Non-Python suggestions rejected |

---

## 7. References

1. Wang et al. (2023). *Self-Consistency Improves Chain of Thought Reasoning in Language Models*. ICLR. [^38^]
2. Li et al. (2025). *Learning to Disprove: Formal Counterexample Generation with Large Language Models*. arXiv:2603.19514. [^40^]
3. Buzzard (2024). *Thoughts on the Putnam exam performance of o1*. Blog post.
4. OpenAI API Documentation — Sampling parameters best practices. [^2^]
5. Papadakis et al. (2015). *Trivial Compiler Equivalence*. ICSE.

---

*Next: Phase 3 — Multi-Implementation Generation (`07_multi_impl.md`)*
