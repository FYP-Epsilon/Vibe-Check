"""Which mutation operators actually survive the equivalence filter,
and do surviving mutants have any traces at all?"""
import os
import sys
import glob
import json
import copy
import collections

os.chdir('/Users/kavindu/Projects/Vibe-Check')
sys.path.insert(0, 'module_01_spec/src')
from semantic_extractor import SemanticExtractionEngine
from ltlf_synthesizer import FLTLSynthesizer
from mutation_refiner import BPMNMutationEngine, LTLfAuditor

aud0 = LTLfAuditor({})


def classify(orig, mut):
    """Which operator produced this mutant?"""
    oe = [(e['source_id'], e['target_id']) for e in orig['edges']]
    me = [(e['source_id'], e['target_id']) for e in mut['edges']]
    if len(me) < len(oe):
        return 'sequence_flow_deletion'
    ot = {s['node_id']: s['node_type'] for s in orig['states']}
    for s in mut['states']:
        if ot.get(s['node_id']) != s['node_type']:
            return ('gateway_substitution' if 'ateway' in s['node_type']
                    or 'ateway' in str(ot.get(s['node_id'])) else 'task_retyping')
    for a, b in zip(orig['edges'], mut['edges']):
        if a.get('condition') != b.get('condition'):
            return 'condition_inversion'
    for a, b in zip(orig['states'], mut['states']):
        if a.get('atomic_propositions') != b.get('atomic_propositions'):
            return 'loop_boundary'
    return 'unknown'


op_tot = collections.Counter()
trace_tot = collections.Counter()
rows = []
for d in ('output', 'context'):
    for f in sorted(glob.glob('flow-bench/data/%s/*.bpmn' % d)):
        g = SemanticExtractionEngine(open(f).read()).run_pipeline()
        gr = g['semantic_graph']
        muts = BPMNMutationEngine(gr).generate_mutants(20, seed=42)
        for m in muts:
            op = classify(gr, m)
            n_tr = len(aud0._generate_traces(m, depth=10))
            op_tot[op] += 1
            trace_tot[(op, n_tr > 0)] += 1
        rows.append(dict(corpus=d, uid=int(os.path.basename(f).split('_')[1]),
                         n_requested=20, n_generated=len(muts)))

print('== mutants generated per diagram (requested 20) ==')
gen = collections.Counter(r['n_generated'] for r in rows)
print('  distribution:', dict(sorted(gen.items())))
print('  total mutants:', sum(r['n_generated'] for r in rows),
      'across', len(rows), 'diagrams')

print('\n== operator that produced each surviving mutant ==')
tot = sum(op_tot.values())
for op, n in op_tot.most_common():
    print('  %-26s %5d  (%.1f%%)' % (op, n, 100.0 * n / tot))

print('\n== does the mutant have ANY executable trace? ==')
for (op, has), n in sorted(trace_tot.items()):
    print('  %-26s has_traces=%-5s %5d' % (op, has, n))

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'handoff')
os.makedirs(OUT, exist_ok=True)
json.dump({'ops': dict(op_tot),
           'traces': {'%s|%s' % k: v for k, v in trace_tot.items()},
           'per_diagram': rows},
          open(os.path.join(OUT, 'mutdiag.json'), 'w'))
