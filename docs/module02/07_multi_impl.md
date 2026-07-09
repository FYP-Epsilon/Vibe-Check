# Phase 3: Multi-Implementation Generation

> **Historical document** (written during Module 02's original 6-phase planning, predating the implementation sessions): describes the design/plan as of that point — a `src/adapters/` layer and a `POST /verify-batch` endpoint. Superseded by what was actually built: a real multi-implementation corpus generated from 3 independent LLM model families, implemented as an evaluation harness (`eval/nim_client.py`, `eval/gen_variants.py`, `eval/admit_variants.py`), not this production adapter/endpoint shape. See `eval/results/multi_impl_report.md`, `eval/results/session_b_report.md`, and `docs/module02/11_multi_impl_corpus_contract.md` (current) for what exists today. Kept as the project's finding trail.

> **Phase**: 3 of 6  
> **Scope**: Self-consistency sampling adapter, multi-implementation orchestrator, batch verification endpoint  
> **Prerequisite**: Phase 1 (hardened core) and Phase 2 (AI refinement) complete  
> **Estimated Effort**: 2–3 days  
> **Status**: Pending

---

## 1. Problem Statement

Module 02's current `POST /verify` endpoint accepts **one** Python implementation and produces **one** WIR. However, the research design (RQ2) and Module 03 both require **multiple WIRs** derived from the same specification for:

1. **Equivalence clustering** — grouping implementations by functional behavior
2. **Divergence isolation** — identifying the exact decision point where variants differ
3. **Model selection** — choosing the consensus implementation via majority voting
4. **Feedback for synthesis corrections** — repairing the LLM prompt when variants disagree

The question is: **where do the multiple implementations come from?**

### Answer: Self-Consistency Sampling (Before Module 02)

Multiple implementations are generated **upstream** of Module 02 using the same LLM with **higher temperature** (Option A from research discussion). Module 02 is called N times independently — once per implementation. The multi-implementation orchestration is a **thin coordination layer**, not a change to the core validator.

```
┌──────────────┐     ┌─────────────────────────────┐     ┌──────────────┐
│  Spec (NL or │────▶│  GenerationAdapter          │────▶│  Module 02   │
│   BPMN)      │     │  - SelfConsistencyAdapter   │     │  (× N times) │
└──────────────┘     │  - Module01Adapter          │     └──────┬───────┘
                     └─────────────────────────────┘            │
                                                                ▼
                                                     ┌─────────────────────┐
                                                     │  N (WIR, cert)      │
                                                     │  pairs              │
                                                     └──────────┬──────────┘
                                                                │
                                                                ▼
                                                     ┌─────────────────────┐
                                                     │  Module 03          │
                                                     │  - Cluster WIRs     │
                                                     │  - Select consensus │
                                                     └─────────────────────┘
```

---

## 2. Theoretical Foundation

### 2.1 Self-Consistency Sampling

Wang et al. (2023) introduced **self-consistency** for chain-of-thought reasoning: sample N reasoning paths from the same LLM, then select the answer supported by the majority [^38^]. Applied to code generation:

> "Instead of greedily decoding a single low-temperature solution, we sample a diverse set of candidate solutions at higher temperature, then marginalize over them to find the most consistent answer." — Wang et al.

For workflow code, "consistency" is measured by **functional equivalence** (bisimulation), not token overlap. Two implementations are consistent if they produce the same output traces for all inputs — which is exactly what Module 03 verifies.

### 2.2 Why Higher Temperature for Generation?

| Parameter | Single-Shot Code Gen | Self-Consistency Sampling |
|-----------|---------------------|---------------------------|
| Temperature | 0.0–0.2 | **0.7–0.9** |
| Top-p | 0.1–0.3 | **0.95** |
| Top-k | 1–10 | **40–50** |
| N (samples) | 1 | **5–10** |

Low temperature produces the "safest" (most probable) implementation. High temperature produces **diverse but still syntactically valid** implementations. The diversity is essential — if all N variants are identical, the clustering in Module 03 is trivial and provides no additional confidence.

### 2.3 Budget Adaptation

More variants → less budget per variant to stay within wall-clock limits:

```
total_budget = 300 seconds (5 min target)
N = 5 variants → per_variant_timeout = 60s
N = 10 variants → per_variant_timeout = 30s
```

Solver queries and test runs scale inversely with N:

| N | Z3 Queries/Variant | Test Runs/Variant | Per-Variant Timeout | Total Wall Clock |
|---|-------------------|-------------------|--------------------|--------------------|
| 1 | 200 | 50 | 300s | 300s |
| 3 | 100 | 35 | 100s | ~180s (parallel) |
| 5 | 80 | 25 | 60s | ~180s (parallel) |
| 10 | 50 | 15 | 30s | ~180s (parallel) |

---

## 3. Architecture: Adapter Pattern

The generation layer uses the **Adapter pattern** — a clean interface with multiple implementations. This keeps Module 02's core validator model-agnostic.

### 3.1 Interface (`adapters/base.py`)

```python
"""
GenerationAdapter — Abstract interface for workflow implementation sources.

This interface allows Module 02 to receive implementations from:
1. Self-consistency LLM sampling (standalone evaluation)
2. External Module 01 (team integration)
3. File-based test datasets (regression testing)

All implementations must produce syntactically valid Python code that follows
the FLOW-BENCH constrained Python IR subset.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class ImplementationVariant:
    """
    A single candidate implementation with generation metadata.
    
    Attributes:
        source_code: The Python workflow code string
        variant_id: Numeric identifier (0 to N-1)
        generation_params: Parameters used to generate this variant
                           (temperature, seed, model name, etc.)
        provenance: Where this implementation came from
    """
    source_code: str
    variant_id: int
    generation_params: Dict[str, Any] = field(default_factory=dict)
    provenance: str = "unknown"


class GenerationAdapter(ABC):
    """
    Pluggable source of Python workflow implementations.
    
    Implementations must guarantee that returned source_code strings:
    1. Are syntactically valid Python 3.10+
    2. Contain a top-level function definition
    3. Follow the constrained IR subset (assignments, if/else, for, while)
    4. Have type hints on the function signature
    5. Return a status string
    
    The adapter does NOT guarantee semantic correctness — that is Module 02's job.
    """

    @abstractmethod
    async def generate_variants(self, specification: str, n: int = 5) -> List[ImplementationVariant]:
        """
        Generate N Python implementation variants from a specification.
        
        Args:
            specification: Natural language description or BPMN XML of the workflow
            n: Number of variants to generate (default 5)
            
        Returns:
            List of ImplementationVariant, one per generated implementation.
            The list may contain fewer than n items if generation fails.
            
        Raises:
            GenerationError: If the specification cannot be processed
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify the adapter is operational (API key valid, endpoint reachable)."""
        pass


class GenerationError(Exception):
    """Raised when implementation generation fails."""
    pass
```

### 3.2 Self-Consistency Adapter (`adapters/llm_adapter.py`)

```python
"""
SelfConsistencyAdapter — Generates N variants via LLM temperature sampling.

Uses OpenAI GPT-4o-mini with progressive temperature:
- Variant 0: temperature 0.3 (conservative baseline, highest quality)
- Variants 1..N-1: temperature 0.8 (diverse explorations)

This ensures at least one high-quality variant while maximizing diversity
across the ensemble. Literature shows diminishing returns beyond N=10.

References:
- Wang et al. (2023). Self-Consistency Improves Chain of Thought Reasoning. ICLR.
- Rajani et al. (2019). Explain Yourself! Leveraging Language Models for
  Commonsense Reasoning. EMNLP.
"""
import asyncio
from typing import List
from adapters.base import GenerationAdapter, ImplementationVariant, GenerationError


# System prompt constrains the LLM to the FLOW-BENCH Python IR subset
WORKFLOW_SYSTEM_PROMPT = (
    "You generate Python workflow code for business process automation. "
    "Use ONLY: variable assignments, if/elif/else, for-loops, while-loops. "
    "Function calls follow: result = Service_Object__version__operation(). "
    "Include type hints. Return a str status. Use standard library only. "
    "Output ONLY the Python code, no markdown, no explanation."
)

# Progressive temperature schedule ensures quality baseline + diversity
TEMPERATURE_SCHEDULE = {
    0: 0.3,   # Conservative baseline
    "default": 0.8  # Diverse exploration
}


class SelfConsistencyAdapter(GenerationAdapter):
    """
    Generates implementation variants using self-consistency temperature sampling.
    
    Uses GPT-4o-mini for cost efficiency. The $5 OpenAI budget covers
    approximately 3,000 variant generations at current pricing.
    
    Args:
        api_key: OpenAI API key (reads from OPENAI_API_KEY env if not provided)
        model: Model identifier (default: gpt-4o-mini-2024-07-18)
        base_temperature: Temperature for non-baseline variants (default: 0.8)
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = "gpt-4o-mini-2024-07-18",
        base_temperature: float = 0.8
    ):
        from openai import AsyncOpenAI
        import os
        
        self.client = AsyncOpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model
        self.base_temperature = base_temperature

    async def generate_variants(self, specification: str, n: int = 5) -> List[ImplementationVariant]:
        """
        Generate N variants using progressive temperature sampling.
        
        Implementation strategy:
        1. Generate all N variants concurrently (parallel API calls)
        2. Each variant gets a different random seed for diversity
        3. Variant 0 uses conservative temperature (0.3) as quality baseline
        4. Variants 1..N-1 use higher temperature (0.8) for diversity
        5. All variants share the same system prompt for consistency
        
        Returns variants with metadata for reproducibility.
        """
        if n < 1:
            raise GenerationError("n must be >= 1")
        if n > 20:
            raise GenerationError("n > 20 not recommended (diminishing returns)")

        # Build the user prompt from the specification
        user_prompt = self._build_prompt(specification)

        # Generate all variants concurrently
        tasks = [
            self._generate_single(user_prompt, variant_id=i, total=n)
            for i in range(n)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter successful generations
        variants = []
        for i, result in enumerate(results):
            if isinstance(result, ImplementationVariant):
                variants.append(result)
            elif isinstance(result, Exception):
                # Log failure but continue with successful variants
                print(f"[SelfConsistencyAdapter] Variant {i} failed: {result}")

        if not variants:
            raise GenerationError(f"All {n} variant generations failed")

        return variants

    async def _generate_single(self, prompt: str, variant_id: int, total: int) -> ImplementationVariant:
        """Generate a single variant with the appropriate temperature."""
        temp = TEMPERATURE_SCHEDULE.get(variant_id, TEMPERATURE_SCHEDULE["default"])
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": WORKFLOW_SYSTEM_PROMULE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=temp,
            top_p=0.95,
            seed=variant_id,  # Deterministic per variant for reproducibility
            max_tokens=2048
        )

        code = response.choices[0].message.content.strip()
        
        # Clean markdown code blocks if present
        code = self._strip_markdown(code)
        
        # Basic validation: must contain 'def ' and be parseable
        if "def " not in code:
            raise GenerationError(f"Variant {variant_id}: No function definition found")
        
        try:
            import ast
            ast.parse(code)
        except SyntaxError as e:
            raise GenerationError(f"Variant {variant_id}: Syntax error: {e}")

        return ImplementationVariant(
            source_code=code,
            variant_id=variant_id,
            generation_params={
                "temperature": temp,
                "seed": variant_id,
                "model": self.model,
                "top_p": 0.95
            },
            provenance="self_consistency_llm"
        )

    def _build_prompt(self, specification: str) -> str:
        """Construct the generation prompt from a specification."""
        return (
            f"Generate a Python function implementing this business process:\n\n"
            f"{specification}\n\n"
            f"Requirements:\n"
            f"- Use if/else for decisions, for/while for loops\n"
            f"- Include type hints on the function signature\n"
            f"- Return a status string indicating the outcome\n"
            f"- Do not use external libraries beyond standard library\n"
            f"- Follow the pattern: result = Service_Object__version__operation()"
        )

    @staticmethod
    def _strip_markdown(code: str) -> str:
        """Remove markdown code fences if the LLM wraps output in ```python...```"""
        if code.startswith("```python"):
            code = code[9:]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        return code.strip()

    async def health_check(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False
```

### 3.3 Module 01 Adapter (`adapters/m01_adapter.py`)

```python
"""
Module01Adapter — Delegates generation to an external Module 01 service.

Used when Module 01 is implemented by another team member. Simply forwards
the specification to the M01 endpoint and wraps the response.
"""
import httpx
from typing import List
from adapters.base import GenerationAdapter, ImplementationVariant, GenerationError


class Module01Adapter(GenerationAdapter):
    """
    Adapter that delegates to an external Module 01 generation service.
    
    Expected M01 API:
        POST /generate
        Body: {"specification": str, "n_variants": int}
        Response: {"implementations": [str], "model": str}
    """

    def __init__(self, endpoint: str = "http://localhost:8001", timeout: float = 60.0):
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout

    async def generate_variants(self, specification: str, n: int = 5) -> List[ImplementationVariant]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(
                    f"{self.endpoint}/generate",
                    json={"specification": specification, "n_variants": n}
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as e:
                raise GenerationError(f"Module 01 request failed: {e}")

        implementations = data.get("implementations", [])
        if not implementations:
            raise GenerationError("Module 01 returned no implementations")

        return [
            ImplementationVariant(
                source_code=code,
                variant_id=i,
                generation_params={"source": "module_01", "model": data.get("model", "unknown")},
                provenance="module_01"
            )
            for i, code in enumerate(implementations)
        ]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.endpoint}/health")
                return resp.status_code == 200
        except Exception:
            return False
```

---

## 4. Orchestrator

The `MultiImplementationValidator` coordinates generation → validation for N variants with **adaptive budget allocation** and **parallel execution**.

```python
"""
MultiImplementationValidator — Orchestrates spec → N variants → N validated WIRs.

This is a thin coordination layer. It does NOT modify the core validation engine.
Instead, it:
1. Calls the GenerationAdapter to produce N variants
2. Calls Module 02's core validator for each variant (in parallel)
3. Applies adaptive budget scaling based on N
4. Returns all results to Module 03 for equivalence clustering
"""
import asyncio
import math
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from adapters.base import GenerationAdapter, ImplementationVariant


@dataclass
class BudgetConfig:
    """Per-variant resource budget."""
    z3_queries: int
    test_runs: int
    timeout: float  # seconds


class MultiImplementationValidator:
    """
    End-to-end orchestrator: specification → N variants → N validated WIRs.
    
    Budget Adaptation Strategy:
    - As N increases, per-variant budget decreases to maintain constant total wall time
    - Uses semaphore to limit concurrent validation (prevents resource exhaustion)
    - Timeout per variant is strictly enforced
    """

    # Budget lookup table: N → per-variant budget
    BUDGET_TABLE = {
        (0, 2): BudgetConfig(200, 50, 120),
        (2, 4): BudgetConfig(150, 40, 90),
        (4, 8): BudgetConfig(100, 25, 60),
        (8, 15): BudgetConfig(60, 15, 35),
        (15, float('inf')): BudgetConfig(40, 10, 20),
    }

    def __init__(
        self,
        generator: GenerationAdapter,
        validator: Any,  # WIRValidator from core engine
        max_parallel: int = 3,
        total_wall_time: float = 300.0  # 5 minutes
    ):
        self.generator = generator
        self.validator = validator
        self.max_parallel = max_parallel
        self.total_wall_time = total_wall_time
        self._semaphore = asyncio.Semaphore(max_parallel)

    async def verify_specification(
        self,
        specification: str,
        n_variants: int = 5
    ) -> "BatchValidationResult":
        """
        Full pipeline: spec → N variants → N validated WIRs.
        
        Steps:
        1. Generate N variants from specification
        2. Determine per-variant budget from N
        3. Validate each variant (parallel, with concurrency limit)
        4. Collect results and produce summary
        
        Returns BatchValidationResult containing all variants and cluster summary.
        """
        # Step 1: Generate variants
        variants = await self.generator.generate_variants(specification, n=n_variants)
        
        # Step 2: Adaptive budget
        budget = self._adaptive_budget(len(variants))
        
        # Step 3: Validate each variant (parallel with semaphore)
        results = await asyncio.gather(*[
            self._validate_one(variant, budget)
            for variant in variants
        ])
        
        # Step 4: Build result
        return BatchValidationResult(
            variant_results=results,
            n_requested=n_variants,
            n_generated=len(variants),
            budget_applied=budget
        )

    async def _validate_one(
        self,
        variant: ImplementationVariant,
        budget: BudgetConfig
    ) -> "VariantResult":
        """
        Validate a single variant with resource-constrained execution.
        
        The semaphore ensures at most max_parallel validations run concurrently.
        Timeout is strictly enforced per variant.
        """
        async with self._semaphore:
            try:
                wir, cert = await asyncio.wait_for(
                    self.validator.verify(
                        variant.source_code,
                        query_budget=budget.z3_queries,
                        test_runs=budget.test_runs
                    ),
                    timeout=budget.timeout
                )
                
                return VariantResult(
                    variant_id=variant.variant_id,
                    source_code=variant.source_code,
                    wir=wir,
                    certificate=cert,
                    generation_params=variant.generation_params,
                    timed_out=False,
                    error=None
                )
            except asyncio.TimeoutError:
                return VariantResult(
                    variant_id=variant.variant_id,
                    source_code=variant.source_code,
                    wir=None,
                    certificate=None,
                    generation_params=variant.generation_params,
                    timed_out=True,
                    error="Validation timeout"
                )
            except Exception as e:
                return VariantResult(
                    variant_id=variant.variant_id,
                    source_code=variant.source_code,
                    wir=None,
                    certificate=None,
                    generation_params=variant.generation_params,
                    timed_out=False,
                    error=str(e)
                )

    def _adaptive_budget(self, n: int) -> BudgetConfig:
        """Look up per-variant budget from N."""
        for (lo, hi), budget in self.BUDGET_TABLE.items():
            if lo <= n < hi:
                return budget
        return self.BUDGET_TABLE[(0, 2)]  # Fallback


@dataclass
class VariantResult:
    """Result of validating a single implementation variant."""
    variant_id: int
    source_code: str
    wir: Optional[Dict[str, Any]]
    certificate: Optional[Dict[str, Any]]
    generation_params: Dict[str, Any]
    timed_out: bool
    error: Optional[str]

    @property
    def passed(self) -> bool:
        if self.certificate is None:
            return False
        return self.certificate.get("combined", 0) >= 0.95


@dataclass
class BatchValidationResult:
    """Aggregated result of multi-implementation validation."""
    variant_results: List[VariantResult]
    n_requested: int
    n_generated: int
    budget_applied: BudgetConfig

    @property
    def n_passed(self) -> int:
        return sum(1 for r in self.variant_results if r.passed)

    @property
    def pass_rate(self) -> float:
        if not self.variant_results:
            return 0.0
        return self.n_passed / len(self.variant_results)

    @property
    def consensus_wir(self) -> Optional[Dict[str, Any]]:
        """Return the WIR of the variant with highest combined score."""
        best = max(
            (r for r in self.variant_results if r.passed),
            key=lambda r: r.certificate.get("combined", 0),
            default=None
        )
        return best.wir if best else None
```

---

## 5. API Endpoints

### New: `POST /verify-batch`

```python
@app.post("/verify-batch", response_model=BatchValidationResponse)
async def verify_batch(req: BatchVerifyRequest) -> BatchValidationResponse:
    """
    End-to-end multi-implementation validation.
    
    Accepts a specification, generates N variants via self-consistency sampling,
    validates each, and returns all WIRs with certificates for Module 03 clustering.
    
    Request:
        {
            "specification": "Retrieve all Jira issues. If priority is urgent, create Asana task.",
            "n_variants": 5,
            "adapter": "self_consistency"  # or "module_01"
        }
    
    Response:
        {
            "implementations": [
                {
                    "variant_id": 0,
                    "source_code": "def workflow() -> str: ...",
                    "wir": {...},
                    "certificate": {"combined": 0.9997, ...},
                    "passed": true
                },
                ...
            ],
            "summary": {
                "n_requested": 5,
                "n_generated": 5,
                "n_passed": 4,
                "pass_rate": 0.80,
                "consensus_variant_id": 0,
                "wall_time_seconds": 45.2
            }
        }
    """
    # Select adapter based on request
    if req.adapter == "module_01" and m01_adapter.health_check():
        adapter = m01_adapter
    else:
        adapter = self_consistency_adapter  # Default fallback

    # Run multi-implementation validation
    result = await multi_validator.verify_specification(
        specification=req.specification,
        n_variants=req.n_variants
    )

    return BatchValidationResponse(
        implementations=[
            {
                "variant_id": r.variant_id,
                "source_code": r.source_code,
                "wir": r.wir,
                "certificate": r.certificate,
                "passed": r.passed
            }
            for r in result.variant_results
        ],
        summary={
            "n_requested": result.n_requested,
            "n_generated": result.n_generated,
            "n_passed": result.n_passed,
            "pass_rate": result.pass_rate,
            "consensus_variant_id": result.consensus_wir and 0,
            "wall_time_seconds": result.wall_time
        }
    )
```

### Existing: `POST /verify` (Unchanged)

The single-implementation endpoint remains exactly as implemented — it is the core validation primitive that `/verify-batch` calls internally.

---

## 6. Configuration

```yaml
# config/multi_impl.yaml
multi_implementation:
  enabled: true
  default_n_variants: 5
  max_n_variants: 10
  max_parallel: 3
  total_wall_time: 300  # seconds
  
  adapters:
    self_consistency:
      model: "gpt-4o-mini-2024-07-18"
      baseline_temperature: 0.3
      exploration_temperature: 0.8
      top_p: 0.95
      max_tokens: 2048
      
    module_01:
      endpoint: "http://localhost:8001"
      timeout: 60.0
      fallback_to_self_consistency: true
```

---

## 7. References

1. Wang et al. (2023). *Self-Consistency Improves Chain of Thought Reasoning in Language Models*. ICLR.
2. Rajani et al. (2019). *Explain Yourself! Leveraging Language Models for Commonsense Reasoning*. EMNLP.
3. Mahmud et al. (2025). *Enhancing LLM Code Generation with Ensembles: A Similarity-Based Selection Approach*. arXiv:2503.15838.
4. Chen et al. (2023). *CodeT: Code Generation with Generated Tests*. ICLR.
5. Isahagian et al. (2025). *Towards Conversational Generation of Enterprise Workflows*. arXiv:2505.11646.

---

*Next: Phase 4 — Evaluation Data Generation (`08_eval_data.md`)*
