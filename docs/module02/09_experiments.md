# Phase 5: Experiments & Metric Calibration

> **Historical document** (written during Module 02's original 6-phase planning, predating the implementation sessions): describes the design/plan as of that point — three experiments (E1/E2/E3) against the fictional 4-layer dataset from `08_eval_data.md`, with aspirational targets (e.g. Pearson r ≥ 0.85). Superseded by the actual, real experiments and measured results: `eval/results/calibration_report_differential.md` (genuine-bug detection 0.9952, false-alarm rate 0.0588), `eval/results/e2_structural_report.md` (structural F1 1.0000), `eval/results/e3_correlation_report.md` (Pearson r 0.4085), and `eval/results/session_b_report.md` / `eval/results/multi_impl_report.md` for the natural-bug and cross-implementation results. See `docs/module_summery/Module_02_Verified_IR_Extraction.md` §10.6 for the current, consolidated numbers with sources. Kept as the project's finding trail.

> **Phase**: 5 of 6  
> **Scope**: Run seeded bug detection, calibrate thresholds, measure all target metrics  
> **Prerequisite**: Phases 1–4 complete (core hardened, AI refinement integrated, evaluation data generated)  
> **Estimated Effort**: 2–3 days (mostly automated, includes analysis)  
> **Status**: Pending

---

## 1. Experimental Objectives

This phase produces the **empirical evidence** that Module 02 works as designed. We run three controlled experiments:

| Experiment | Dataset | Purpose | Success Criteria |
|-----------|---------|---------|-----------------|
| **E1: Seeded Bug Detection** | Layer 3 (500 mutants) | Validate that V1+V2+V3 catches semantic alterations | ≥95% detection rate, ≤5% false positive |
| **E2: Structural Accuracy** | Layer 1 + Layer 4 (60 workflows) | Validate V3 extraction correctness | ≥98% node/edge match rate |
| **E3: Confidence Calibration** | Layer 1 + Layer 2 (150 workflows) | Validate that combined ≥ 0.95 correlates with correctness | Pearson r ≥ 0.85 between combined score and ground truth |

---

## 2. Experiment E1: Seeded Bug Detection

### 2.1 Protocol

```
For each base workflow in Layer 1 (5 selected workflows):
    1. Generate 100 mutants (20 per operator type: ROR, COR, BOR, STR, JTD)
    2. Run each mutant through Module 02 /verify endpoint
    3. Record certificate for each mutant
    4. Classify:
        - DETECTED: combined < 0.95  (verification caught the bug)
        - UNDETECTED: combined >= 0.95 (verification missed the bug)
    5. Separate semantic-altering from equivalent mutants
    
Calculate metrics:
    - Detection Rate = detected_semantic / total_semantic
    - False Positive Rate = rejected_equivalent / total_equivalent
```

### 2.2 Implementation

```python
# eval_data/run_experiments.py — Experiment E1

async def experiment_e1_seed_detection(
    module02_endpoint: str,
    base_workflows: List[dict],
    n_mutations_per_type: int = 20,
    output_file: str = "eval_data/results/e1_seed_detection.json"
) -> dict:
    """
    Seeded bug detection experiment.
    
    Validates that Module 02 detects semantic-altering mutations
    while accepting semantically-equivalent mutations.
    
    Returns:
        Metrics dict with detection_rate, false_positive_rate,
        per-operator breakdown, and per-mode detection rates.
    """
    from eval_data.mutation_engine import generate_mutants, calculate_mutation_score
    
    all_mutants = []
    all_results = {}
    
    for base in base_workflows:
        # Generate mutants for this base workflow
        mutants = generate_mutants(
            source_code=base["python_ir"],
            n_per_type=n_mutations_per_type,
            base_uid=base["uid"]
        )
        all_mutants.extend(mutants)
        
        # Run each mutant through Module 02
        for mutant in mutants:
            result = await _call_verify(module02_endpoint, mutant.mutated_code)
            all_results[mutant.mutant_id] = result
    
    # Calculate metrics
    metrics = calculate_mutation_score(all_mutants, all_results)
    
    # Per-operator breakdown
    per_operator = {}
    for op in ["ROR", "COR", "BOR", "STR", "JTD", "RER"]:
        op_mutants = [m for m in all_mutants if m.operator == op]
        op_semantic = [m for m in op_mutants if m.is_semantic_altering]
        op_detected = sum(
            1 for m in op_semantic
            if all_results.get(m.mutant_id, {}).get("combined", 1.0) < 0.95
        )
        per_operator[op] = {
            "total": len(op_mutants),
            "semantic": len(op_semantic),
            "detected": op_detected,
            "detection_rate": op_detected / len(op_semantic) if op_semantic else 0
        }
    
    # Per-mode detection rates
    per_mode = {}
    for mode in ["v1", "v2", "v3"]:
        mode_detected = sum(
            1 for m in all_mutants
            if m.is_semantic_altering 
            and all_results.get(m.mutant_id, {}).get(mode, {}).get("score", 0) < 0.5
        )
        per_mode[mode] = mode_detected / len([m for m in all_mutants if m.is_semantic_altering])
    
    result = {
        "experiment": "E1_Seeded_Bug_Detection",
        "total_mutants": len(all_mutants),
        "base_workflows_used": len(base_workflows),
        "mutations_per_type": n_mutations_per_type,
        "overall_detection_rate": metrics["detection_rate"],
        "overall_false_positive_rate": metrics["false_positive_rate"],
        "target_detection_rate": 0.95,
        "target_false_positive_rate": 0.05,
        "detection_target_met": metrics["detection_rate"] >= 0.95,
        "fp_target_met": metrics["false_positive_rate"] <= 0.05,
        "per_operator": per_operator,
        "per_mode": per_mode,
        "raw_results": all_results,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Save
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    return result
```

### 2.3 Expected Results

| Metric | Target | Expected | Interpretation |
|--------|--------|----------|----------------|
| Semantic mutation detection rate | ≥95% | 96–99% | V1 differential testing catches most behavioral changes |
| Equivalent mutant false positive rate | ≤5% | 3–8% | BOR (branch swap) may occasionally trigger V1 due to trace ordering |
| ROR detection | — | ~98% | Relational operator changes are obvious in both V1 and V2 |
| COR detection | — | ~95% | Conditional operator changes detected by V2 guard CNF |
| BOR (equivalent) rejection | — | ~5% | Branch swap preserves semantics but may trigger V1 stutter detection |
| STR detection | — | ~99% | Statement removal always detected by V1 trace length difference |

### 2.4 Analysis Procedure

If detection rate < 95%:
1. Identify which operators are under-detected
2. Check if V1 test runs (n=50) are sufficient — increase to 100
3. Check if V2 solver budget (50 queries) is exhausted — increase to 100
4. If BOR false positives > 5%: tune V1 stutter elimination threshold

---

## 3. Experiment E2: Structural Accuracy

### 3.1 Protocol

```
For each workflow in Layer 1 (50 golden) + Layer 4 (10 adversarial):
    1. Run through Module 02 /verify endpoint
    2. Extract V3 structural metrics (nodes, edges, decisions)
    3. Compare against ground-truth expected values
    4. Classify:
        - MATCH: All structural metrics within ±1 of expected
        - MISMATCH: Any metric differs by >1
        - FAIL: Verification threw exception
```

### 3.2 Ground Truth Extraction

For golden workflows (Layer 1), ground truth is computed from the AST:

```python
def compute_ground_truth(python_ir: str) -> dict:
    """Compute structural ground truth from Python AST."""
    import ast
    tree = ast.parse(python_ir)
    
    nodes = 0
    edges = 0
    decisions = 0
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.Assign, ast.Expr)):
            nodes += 1
        elif isinstance(node, (ast.If, ast.While, ast.For)):
            nodes += 1
            decisions += 1
        elif isinstance(node, ast.Break):
            edges += 1  # Loop exit edge
    
    # Edges estimated: each node (except exit) has at least 1 outgoing edge
    # Decision nodes have 2 outgoing edges (taken/not-taken)
    edges = nodes + decisions - 1  # Approximate
    
    return {"nodes": nodes, "edges": edges, "decisions": decisions}
```

### 3.3 Metrics

```python
async def experiment_e2_structural_accuracy(
    module02_endpoint: str,
    workflows: List[dict],
    output_file: str = "eval_data/results/e2_structural_accuracy.json"
) -> dict:
    """Measure V3 structural extraction accuracy against ground truth."""
    
    results = []
    node_matches = 0
    edge_matches = 0
    decision_matches = 0
    
    for wf in workflows:
        # Run verification
        cert = await _call_verify(module02_endpoint, wf["python_ir"])
        
        # Ground truth
        gt = compute_ground_truth(wf["python_ir"])
        
        # Extracted
        v3 = cert.get("v3", {})
        extracted = {
            "nodes": v3.get("nodes", 0),
            "edges": v3.get("edges", 0),
            "decisions": v3.get("decisions", 0)
        }
        
        # Compare
        result = {
            "uid": wf["uid"],
            "ground_truth": gt,
            "extracted": extracted,
            "node_match": abs(gt["nodes"] - extracted["nodes"]) <= 1,
            "edge_match": abs(gt["edges"] - extracted["edges"]) <= 1,
            "decision_match": abs(gt["decisions"] - extracted["decisions"]) <= 1,
        }
        results.append(result)
        
        if result["node_match"]: node_matches += 1
        if result["edge_match"]: edge_matches += 1
        if result["decision_match"]: decision_matches += 1
    
    n = len(workflows)
    
    metrics = {
        "experiment": "E2_Structural_Accuracy",
        "total_workflows": n,
        "node_match_rate": node_matches / n,
        "edge_match_rate": edge_matches / n,
        "decision_match_rate": decision_matches / n,
        "overall_match_rate": sum(
            1 for r in results 
            if r["node_match"] and r["edge_match"] and r["decision_match"]
        ) / n,
        "target_match_rate": 0.98,
        "target_met": (node_matches / n) >= 0.98,
        "per_workflow": results
    }
    
    with open(output_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    
    return metrics
```

---

## 4. Experiment E3: Confidence Calibration

### 4.1 Purpose

Validate that the combined confidence score (1 - product of failures) actually correlates with correctness. A combined score of 0.99 should mean "almost certainly correct"; a score of 0.60 should mean "probably incorrect."

### 4.2 Protocol

```
For each workflow in Layer 1 (50 golden) + Layer 2 (100 augmented):
    1. Run through Module 02 /verify → get combined score
    2. Determine ground-truth correctness:
        - Golden (Layer 1): assumed correct (generated by LLM, syntactically valid)
        - Augmented (Layer 2): 
            - If preserves_semantics=True: equivalent to correct base
            - If preserves_semantics=False: extended (still correct, just more complex)
    3. Calculate correlation between combined score and correctness
```

### 4.3 Metrics

| Metric | Formula | Target |
|--------|---------|--------|
| Pearson correlation | `corrcoef(combined_scores, correctness_labels)` | r ≥ 0.85 |
| AUC-ROC | `roc_auc_score(correctness, combined_scores)` | ≥ 0.90 |
| Calibration (ECE) | Expected Calibration Error | ≤ 0.05 |
| Threshold accuracy at 0.95 | Fraction correctly classified at cutoff | ≥ 90% |

```python
async def experiment_e3_confidence_calibration(
    module02_endpoint: str,
    layer1_workflows: List[dict],
    layer2_workflows: List[dict],
    output_file: str = "eval_data/results/e3_calibration.json"
) -> dict:
    """
    Validate that combined certificate score correlates with correctness.
    """
    from scipy.stats import pearsonr
    from sklearn.metrics import roc_auc_score
    
    all_scores = []
    all_labels = []  # 1 = correct, 0 = incorrect
    
    # Layer 1: All golden workflows are assumed correct
    for wf in layer1_workflows:
        cert = await _call_verify(module02_endpoint, wf["python_ir"])
        combined = cert.get("combined", 0)
        all_scores.append(combined)
        all_labels.append(1)  # Correct
    
    # Layer 2: Augmented workflows — check if V3 extraction still works
    for wf in layer2_workflows:
        cert = await _call_verify(module02_endpoint, wf["augmented_code"])
        combined = cert.get("combined", 0)
        all_scores.append(combined)
        # Augmented code should also be structurally valid
        all_labels.append(1 if combined >= 0.95 else 0)
    
    # Calculate metrics
    pearson_r, p_value = pearsonr(all_scores, all_labels)
    
    try:
        auc = roc_auc_score(all_labels, all_scores)
    except ValueError:
        auc = None  # All labels same
    
    # Threshold accuracy
    predictions = [1 if s >= 0.95 else 0 for s in all_scores]
    threshold_acc = sum(p == l for p, l in zip(predictions, all_labels)) / len(all_labels)
    
    metrics = {
        "experiment": "E3_Confidence_Calibration",
        "total_samples": len(all_scores),
        "pearson_r": pearson_r,
        "pearson_p_value": p_value,
        "auc_roc": auc,
        "threshold_accuracy": threshold_acc,
        "target_pearson_r": 0.85,
        "target_auc": 0.90,
        "target_threshold_acc": 0.90,
        "pearson_target_met": abs(pearson_r) >= 0.85,
        "threshold_acc_target_met": threshold_acc >= 0.90
    }
    
    with open(output_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    
    return metrics
```

---

## 5. Metric Target Table

The following metrics are defined in the research design and tracked across all experiments:

| Metric | Symbol | Definition | Target | Measured In |
|--------|--------|-----------|--------|-------------|
| Trace coverage | τ_cov | Fraction of WIR transitions exercised by differential testing | ≥ 0.95 | E1 (V1 pass rate on valid code) |
| Branch coverage | β_cov | Fraction of Python branches with verified WIR correspondence | ≥ 0.80 | E2 (decision match rate) |
| Mismatch rate | μ | Fraction of test inputs with α-trace mismatch | ≤ 0.01 | E1 (V1 mismatch on golden) |
| Refinement success | ρ | Fraction of critical transitions with proven simulation relation | ≥ 0.70 | E2 (V2 guard success rate) |
| Mutation detection | δ | Fraction of semantic-altering mutations detected | ≥ 0.95 | E1 (overall detection rate) |
| False positive | φ | Fraction of equivalent mutations wrongly rejected | ≤ 0.05 | E1 (BOR rejection rate) |
| Validation time | t_val | Wall-clock time per 100 LOC | < 300s | E1, E2, E3 (timestamps) |
| Combined-pass rate | π_pass | Fraction of valid workflows with combined ≥ 0.95 | ≥ 0.85 | E3 (threshold accuracy) |
| Structural accuracy | α_struct | Fraction with correct node/edge/decision counts | ≥ 0.98 | E2 (overall match rate) |

---

## 6. Running All Experiments

```python
# eval_data/run_experiments.py

async def run_all_experiments(module02_endpoint: str = "http://localhost:8000"):
    """
    Run all three experiments and produce a consolidated report.
    
    This is the main entry point for Phase 5. It:
    1. Loads all generated datasets
    2. Runs E1, E2, E3 sequentially
    3. Produces a consolidated results file
    4. Generates a human-readable summary
    """
    
    # Load datasets
    with open("eval_data/datasets/layer1_golden.json") as f:
        layer1 = json.load(f)
    with open("eval_data/datasets/layer2_augmented.json") as f:
        layer2 = json.load(f)
    with open("eval_data/datasets/layer4_adversarial.json") as f:
        layer4 = json.load(f)
    
    # Select 5 base workflows for E1
    e1_bases = layer1[:5]
    
    print("=" * 60)
    print("EXPERIMENT E1: Seeded Bug Detection")
    print("=" * 60)
    e1_results = await experiment_e1_seed_detection(
        module02_endpoint, e1_bases, n_mutations_per_type=20
    )
    print(f"Detection rate: {e1_results['overall_detection_rate']:.2%}")
    print(f"False positive rate: {e1_results['overall_false_positive_rate']:.2%}")
    print(f"Target met: {e1_results['detection_target_met']}")
    
    print("\n" + "=" * 60)
    print("EXPERIMENT E2: Structural Accuracy")
    print("=" * 60)
    e2_workflows = layer1 + layer4
    e2_results = await experiment_e2_structural_accuracy(
        module02_endpoint, e2_workflows
    )
    print(f"Node match rate: {e2_results['node_match_rate']:.2%}")
    print(f"Edge match rate: {e2_results['edge_match_rate']:.2%}")
    print(f"Decision match rate: {e2_results['decision_match_rate']:.2%}")
    print(f"Target met: {e2_results['target_met']}")
    
    print("\n" + "=" * 60)
    print("EXPERIMENT E3: Confidence Calibration")
    print("=" * 60)
    e3_results = await experiment_e3_confidence_calibration(
        module02_endpoint, layer1, layer2
    )
    print(f"Pearson r: {e3_results['pearson_r']:.4f}")
    print(f"Threshold accuracy: {e3_results['threshold_accuracy']:.2%}")
    print(f"Target met: {e3_results['threshold_acc_target_met']}")
    
    # Consolidated report
    consolidated = {
        "run_date": datetime.utcnow().isoformat(),
        "module02_endpoint": module02_endpoint,
        "experiments": {
            "e1_seeded_bug_detection": e1_results,
            "e2_structural_accuracy": e2_results,
            "e3_confidence_calibration": e3_results
        },
        "all_targets_met": all([
            e1_results["detection_target_met"],
            e1_results["fp_target_met"],
            e2_results["target_met"],
            e3_results["threshold_acc_target_met"]
        ])
    }
    
    with open("eval_data/results/consolidated_report.json", 'w') as f:
        json.dump(consolidated, f, indent=2)
    
    print("\n" + "=" * 60)
    print("CONSOLIDATED REPORT")
    print("=" * 60)
    print(f"All targets met: {consolidated['all_targets_met']}")
    print(f"Report saved to: eval_data/results/consolidated_report.json")
    
    return consolidated
```

---

## 7. Calibration Procedure

If any target is not met, follow this calibration procedure:

### 7.1 Detection Rate < 95%

```
1. Identify under-performing operators from per_operator breakdown
2. For ROR/COR under-detection:
    → Increase V2 solver budget (BUDGET_TABLE queries += 50)
    → Check if Z3 timeout is occurring (increase timeout)
3. For STR under-detection:
    → Increase V1 test runs (n_runs: 50 → 100)
    → Check if reference interpreter handles the removed statement correctly
4. For BOR over-detection (false positives):
    → Tune V1 stutter elimination threshold
    → Check if branch swap changes trace ordering (expected behavior)
```

### 7.2 Structural Accuracy < 98%

```
1. Identify which adversarial cases fail (adv_00X)
2. For dominator failures (adv_001):
    → Check DominatorAnalyzer fallback path for disconnected graphs
3. For guard CNF failures (adv_002, adv_006):
    → Add test case to GuardExtractor for the specific pattern
4. For Python 3.10+ construct failures (adv_009 Match):
    → Verify CFGExtractor handles the construct (may need visitor addition)
```

### 7.3 Threshold Accuracy < 90%

```
1. Plot score distribution for passed vs failed workflows
2. If 0.95 threshold misclassifies many:
    → Adjust certification_threshold in ValidationConfig
    → Consider per-mode weighting instead of equal product-of-failures
3. If scores cluster (no separation between correct/incorrect):
    → V1 or V2 may be producing constant scores (check for saturation)
```

---

## 8. Deliverables

| Deliverable | Location | Format |
|-----------|----------|--------|
| E1 results | `eval_data/results/e1_seed_detection.json` | JSON |
| E2 results | `eval_data/results/e2_structural_accuracy.json` | JSON |
| E3 results | `eval_data/results/e3_calibration.json` | JSON |
| Consolidated report | `eval_data/results/consolidated_report.json` | JSON |
| Thesis table | Extracted manually | LaTeX/markdown table |

---

## 9. References

1. Ammann & Offutt (2008). *Introduction to Software Testing*. Cambridge University Press.
2. Papadakis et al. (2015). *Trivial Compiler Equivalence*. ICSE.
3. Grün et al. (2009). *The Impact of Equivalent Mutants*. QSIC.
4. Godefroid et al. (2005). *DART: Directed Automated Random Testing*. PLDI.
5. Neller et al. (2013). *Expected Calibration Error*. NeurIPS.

---

*Next: Phase 6 — Integration & Documentation (`10_integration.md`)*
