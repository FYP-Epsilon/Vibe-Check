"""Invalidation checks for the two saturated pilot figures.

Q1. Is structural F1=1.0 an artifact of a gold labeler that shares
    semantic_extractor's own tag vocabulary (circularity)?
    -> Re-derive gold from the BPMN 2.0 SPEC flow-node set instead of
       EXECUTABLE_NODES/NON_NODE_TAGS, and re-score.
Q2. Is kill=1.0 real discrimination, or does the auditor kill mutants
    for reasons unrelated to the property suite (empty trace set,
    parse-error-as-False, trivially-false suite)?
    -> Decompose each kill by CAUSE.
"""
import os
import sys
import glob
import json
import collections
import xml.etree.ElementTree as ET

os.chdir('/Users/kavindu/Projects/Vibe-Check')
sys.path.insert(0, 'module_01_spec/src')
from semantic_extractor import SemanticExtractionEngine
from ltlf_synthesizer import FLTLSynthesizer
from mutation_refiner import BPMNMutationEngine, LTLfAuditor
from ltlf_eval import evaluate_ltlf

NS = 'http://www.omg.org/spec/BPMN/20100524/MODEL'

# BPMN 2.0 spec flow-node taxonomy, written from the standard, NOT copied
# from semantic_extractor.EXECUTABLE_NODES.
SPEC_FLOW_NODES = {
    'startEvent', 'endEvent', 'intermediateCatchEvent', 'intermediateThrowEvent',
    'boundaryEvent',
    'task', 'userTask', 'serviceTask', 'scriptTask', 'manualTask', 'receiveTask',
    'sendTask', 'businessRuleTask',
    'subProcess', 'transaction', 'adHocSubProcess', 'callActivity',
    'exclusiveGateway', 'parallelGateway', 'inclusiveGateway', 'eventBasedGateway',
    'complexGateway',
}


def gold_spec(path):
    """Ground truth from the BPMN 2.0 flow-node taxonomy (allowlist)."""
    root = ET.parse(path).getroot()
    nodes, edges = set(), set()
    for e in root.iter():
        if not e.tag.startswith('{%s}' % NS):
            continue
        t = e.tag.split('}')[-1]
        if t == 'sequenceFlow':
            edges.add((e.get('id'), e.get('sourceRef'), e.get('targetRef')))
        elif t in SPEC_FLOW_NODES and e.get('id'):
            nodes.add((e.get('id'), t))
    return nodes, edges


def kill_cause(auditor, mutant):
    """Why was this mutant killed? Separate real property violations from
    degenerate causes."""
    traces = auditor._generate_traces(mutant, depth=10)
    if not traces:
        return 'degenerate:no_traces_generated'
    for trace in traces:
        for prop in auditor.properties:
            try:
                ok = evaluate_ltlf(prop, trace)
            except Exception:
                return 'degenerate:parse_error_as_violation'
            if not ok:
                tier = ('P4' if prop.startswith('F(')
                        else 'P0' if prop.startswith('!done')
                        else 'P1')
                return 'real_violation:' + tier
    return 'survived'


rows = []
cause_tot = collections.Counter()
for d in ('output', 'context'):
    for f in sorted(glob.glob('flow-bench/data/%s/*.bpmn' % d)):
        gn, ge = gold_spec(f)
        g = SemanticExtractionEngine(open(f).read()).run_pipeline()
        gr = g['semantic_graph']
        xn = {(s['node_id'], s['node_type']) for s in gr['states']}
        xe = {(e['flow_id'], e['source_id'], e['target_id']) for e in gr['edges']}
        suite = FLTLSynthesizer(g).run_pipeline()['ltlf_property_suite']
        clean = {k: [p for p in v if not p.startswith('/*')] for k, v in suite.items()}
        aud = LTLfAuditor(clean)
        sound = not aud.is_killed(gr)[0]
        muts = BPMNMutationEngine(gr).generate_mutants(20, seed=42)
        causes = collections.Counter(kill_cause(aud, m) for m in muts)
        if sound:
            cause_tot.update(causes)
        rows.append(dict(corpus=d, uid=int(os.path.basename(f).split('_')[1]),
                         sound=sound,
                         ntp=len(gn & xn), nfp=len(xn - gn), nfn=len(gn - xn),
                         etp=len(ge & xe), efp=len(xe - ge), efn=len(ge - xe),
                         n_props=sum(len(v) for v in clean.values()),
                         causes=dict(causes)))

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'handoff')
os.makedirs(OUT, exist_ok=True)
json.dump(rows, open(os.path.join(OUT, 'invalidate_rows.json'), 'w'))

print('== Q1: structural scoring vs SPEC-derived gold (independent vocabulary) ==')
for d in ('output', 'context'):
    R = [r for r in rows if r['corpus'] == d]
    for lbl, p in (('node', 'n'), ('edge', 'e')):
        tp = sum(r[p + 'tp'] for r in R)
        fp = sum(r[p + 'fp'] for r in R)
        fn = sum(r[p + 'fn'] for r in R)
        P = tp / (tp + fp) if tp + fp else 1.0
        Rc = tp / (tp + fn) if tp + fn else 1.0
        F = 2 * P * Rc / (P + Rc) if P + Rc else 0.0
        print('  %-8s %-5s P=%.4f R=%.4f F1=%.4f  tp=%d fp=%d fn=%d'
              % (d, lbl, P, Rc, F, tp, fp, fn))

print('\n== Q2: kill-cause decomposition (sound-suite diagrams only) ==')
tot = sum(cause_tot.values())
for c, n in cause_tot.most_common():
    print('  %-42s %5d  (%.1f%%)' % (c, n, 100.0 * n / tot))
print('  TOTAL mutants scored: %d' % tot)

print('\n== Q3: property-suite size on sound diagrams ==')
S = [r for r in rows if r['sound']]
print('  suites with 0 properties: %d / %d' % (sum(1 for r in S if r['n_props'] == 0), len(S)))
print('  min=%d median=%d max=%d' % (min(r['n_props'] for r in S),
                                     sorted(r['n_props'] for r in S)[len(S) // 2],
                                     max(r['n_props'] for r in S)))
