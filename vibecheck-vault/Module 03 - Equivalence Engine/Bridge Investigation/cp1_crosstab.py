import sys, glob, re, json, os
sys.path.insert(0, "/Users/kavindu/Projects/Vibe-Check/module_01_spec/src")
sys.path.insert(0, "/Users/kavindu/Projects/Vibe-Check/module_02_extract/src")
sys.path.insert(0, "/Users/kavindu/Projects/Vibe-Check/module_03_equiv")
sys.path.insert(0, "/Users/kavindu/Projects/Vibe-Check/module_03_equiv/src")
from api import run_module_01_pipeline
from ast_extractor.cfg_extractor import CFGExtractor
from src.property_ingest import load_property_suite
from src.pipeline import process_wir_batch

CTX_DIR = "/Users/kavindu/Projects/Vibe-Check/flow-bench/data/context"
VAR_DIR = "/Users/kavindu/Projects/Vibe-Check/module_02_extract/eval/variants/normalized"
eligible_uids = [44,45,46,47,48,49,50,53,56,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,89,91,97,100]

TIER_SEMANTICS = {
    "P0_Critical_Sentinels": {"conformance_check": False},
    "P1_Structural_Control_Flow": {"conformance_check": True},
    "P2_Quality_Limits": {"conformance_check": True},
    "P3_Adversarial_Defenses": {"conformance_check": False},
    "synthesized_mutant_killers": {"conformance_check": False},
}

def normalize_name(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())

def spec_task_names(uid):
    xml = open(f"{CTX_DIR}/uid_{uid}_context.bpmn").read()
    res = run_module_01_pipeline(xml)
    sg = res["phase_1"]["semantic_graph"]
    names = []
    for s in sg["states"]:
        if s.get("node_type") in ("task", "userTask", "serviceTask"):
            for p in s.get("atomic_propositions", []):
                m = re.match(r'(?:start|done)\(([^)]+)\)', p)
                if m:
                    names.append(m.group(1)); break
    seen = set(); out = []
    for n in names:
        if n not in seen:
            seen.add(n); out.append(n)
    return out, res

def code_call_order(path):
    src = open(path).read()
    wir = CFGExtractor().extract(src)
    funcs = wir.get("functions", {})
    sibling_names = set(funcs.keys())
    best_fn, best_count, best_calls = None, -1, []
    call_re = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\(')
    for fn_name, cfg in funcs.items():
        calls = []
        for n in cfg["nodes"]:
            code = n.get("code")
            if not code:
                continue
            lines = code if isinstance(code, list) else [code]
            for line in lines:
                for m in call_re.finditer(line):
                    if m.group(1) in sibling_names and m.group(1) != fn_name:
                        calls.append(m.group(1))
        if len(calls) > best_count:
            best_count = len(calls)
            best_fn = fn_name
            best_calls = calls
    return best_calls

ATOM_RE = re.compile(r'(?:start|done)\(([^)]+)\)')

def atoms_in_formula(origin_formula):
    return list(dict.fromkeys(ATOM_RE.findall(origin_formula)))

records = []

for uid in eligible_uids:
    spec_names, res = spec_task_names(uid)
    suite_dict = {
        "ltlf_property_suite": res["phase_3"]["refined_ltlf_property_suite"],
        "tier_semantics": TIER_SEMANTICS,
    }
    try:
        suite = load_property_suite(suite_dict)
    except Exception as e:
        print(f"uid {uid}: ingestion failed: {e}")
        continue

    checkable = suite.conformance_properties()
    if not checkable:
        continue

    variants = sorted(glob.glob(f"{VAR_DIR}/{uid}__*.py"))
    for vpath in variants:
        vname = os.path.basename(vpath)
        src = open(vpath).read()
        wir = CFGExtractor().extract(src)
        calls = code_call_order(vpath)
        calls_norm = [normalize_name(c) for c in calls]

        try:
            result = process_wir_batch(
                [json.dumps(wir)],
                bpmn_tasks=spec_names,
                property_suite=suite,
            )
        except Exception as e:
            print(f"uid {uid} variant {vname}: process_wir_batch failed: {e}")
            continue
        cluster = list(result["clusters"].values())[0]

        for r in cluster["compliance_results"]:
            atoms = atoms_in_formula(r["origin_formula"])
            atom_norms = [normalize_name(a) for a in atoms]
            # was each atom name actually invoked at runtime (present in the orchestrator's call list)?
            atom_called = {}
            for a, an in zip(atoms, atom_norms):
                called = any(an == cn or an in cn or cn in an for cn in calls_norm)
                atom_called[a] = called
            all_called = all(atom_called.values()) if atoms else False
            any_never_called = any(not v for v in atom_called.values())
            records.append({
                "uid": uid,
                "variant": vname,
                "tier": r["tier"],
                "origin_formula": r["origin_formula"],
                "verdict": r["verdict"],
                "atoms": atoms,
                "atom_called": atom_called,
                "all_atoms_called_at_runtime": all_called,
                "any_atom_never_called": any_never_called,
                "unmatched_atoms": r["unmatched_atoms"],
            })

json.dump(records, open(os.path.join(os.path.dirname(__file__), "cp1_crosstab_raw.json"), "w"), indent=2)

# ---- cross-tab ----
violations = [r for r in records if r["verdict"] == "VIOLATION"]
compliants = [r for r in records if r["verdict"] == "COMPLIANT"]
inconclusive = [r for r in records if r["verdict"] == "INCONCLUSIVE"]

print(f"total checks: {len(records)}  VIOLATION={len(violations)} COMPLIANT={len(compliants)} INCONCLUSIVE={len(inconclusive)}")

v_all_called = [r for r in violations if r["all_atoms_called_at_runtime"]]
v_never_called = [r for r in violations if r["any_atom_never_called"]]
print(f"\nOf {len(violations)} VIOLATIONs:")
print(f"  {len(v_all_called)} have ALL referenced tasks actually called at runtime (potentially real violation)")
print(f"  {len(v_never_called)} reference at least one task NEVER called at runtime (spurious per definition-order lifting)")

# divergence mode lookup
f4 = json.load(open(os.path.join(os.path.dirname(__file__), "f4_divergence_results.json")))

c_omission_underneath = []
for r in compliants:
    mode = f4.get(r["variant"], {}).get("mode")
    if mode in ("omission only", "omission + reordering"):
        c_omission_underneath.append(r)
print(f"\nOf {len(compliants)} COMPLIANTs:")
print(f"  {len(c_omission_underneath)} occur on a variant independently classified (F4) as omission-divergent (false-COMPLIANT candidates)")

# breakdown table
print("\n--- sample VIOLATIONs with a never-called atom ---")
for r in v_never_called[:8]:
    print(r["uid"], r["variant"], r["origin_formula"], r["atom_called"])

print("\n--- sample COMPLIANTs on omission-divergent variants ---")
for r in c_omission_underneath[:8]:
    print(r["uid"], r["variant"], r["origin_formula"], f4[r["variant"]]["mode"])
