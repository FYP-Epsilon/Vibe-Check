"""Crosstab: suite soundness x mutant connectivity x kill cause.

is_killed() returns True whenever a mutant has no complete trace
(mutation_refiner.py, LTLfAuditor.is_killed: "if not traces: return True").
So a kill can mean either (a) a property was violated -- real detection --
or (b) the mutation disconnected the graph -- detection by fiat.
This separates them.
"""
import os
import sys
import glob
import json
import collections

os.chdir('/Users/kavindu/Projects/Vibe-Check')
sys.path.insert(0, 'module_01_spec/src')
from semantic_extractor import SemanticExtractionEngine
from ltlf_synthesizer import FLTLSynthesizer
from mutation_refiner import BPMNMutationEngine, LTLfAuditor
from ltlf_eval import evaluate_ltlf

aud0 = LTLfAuditor({})
cross = collections.Counter()
prop_kill_detail = collections.Counter()
per_diag = []

for d in ('output', 'context'):
    for f in sorted(glob.glob('flow-bench/data/%s/*.bpmn' % d)):
        g = SemanticExtractionEngine(open(f).read()).run_pipeline()
        gr = g['semantic_graph']
        suite = FLTLSynthesizer(g).run_pipeline()['ltlf_property_suite']
        clean = {k: [p for p in v if not p.startswith('/*')] for k, v in suite.items()}
        aud = LTLfAuditor(clean)
        sound = not aud.is_killed(gr)[0]
        muts = BPMNMutationEngine(gr).generate_mutants(20, seed=42)
        n_disc = n_propkill = n_surv = 0
        for m in muts:
            traces = aud0._generate_traces(m, depth=10)
            if not traces:
                cross[(sound, 'disconnected->killed_by_fiat')] += 1
                n_disc += 1
                continue
            hit = None
            for tr in traces:
                for p in aud.properties:
                    try:
                        if not evaluate_ltlf(p, tr):
                            hit = p
                            break
                    except Exception:
                        hit = 'PARSE_ERROR'
                        break
                if hit:
                    break
            if hit:
                cross[(sound, 'connected->killed_by_property')] += 1
                n_propkill += 1
                tier = ('P4' if hit.startswith('F(') else
                        'P0' if hit.startswith('!done') else 'P1')
                prop_kill_detail[(sound, tier)] += 1
            else:
                cross[(sound, 'connected->SURVIVED')] += 1
                n_surv += 1
        per_diag.append(dict(corpus=d, uid=int(os.path.basename(f).split('_')[1]),
                             sound=sound, disc=n_disc, propkill=n_propkill,
                             surv=n_surv))

print('== suite soundness x kill mechanism (2960 mutants, 148 diagrams) ==')
print('  %-7s %-34s %6s' % ('sound', 'mechanism', 'n'))
for k in sorted(cross, key=lambda x: (not x[0], x[1])):
    print('  %-7s %-34s %6d' % (k[0], k[1], cross[k]))

sound_tot = sum(v for k, v in cross.items() if k[0])
sound_prop = cross[(True, 'connected->killed_by_property')]
print('\n== on SOUND-suite diagrams (the only ones where a kill is interpretable) ==')
print('  mutants: %d' % sound_tot)
print('  killed by a property violation: %d (%.1f%%)'
      % (sound_prop, 100.0 * sound_prop / sound_tot if sound_tot else 0))
print('  killed only because the mutation disconnected the graph: %d (%.1f%%)'
      % (cross[(True, 'disconnected->killed_by_fiat')],
         100.0 * cross[(True, 'disconnected->killed_by_fiat')] / sound_tot if sound_tot else 0))
print('  survived: %d' % cross[(True, 'connected->SURVIVED')])

print('\n== property-driven kills by tier (unsound suites included, for contrast) ==')
for k, v in sorted(prop_kill_detail.items()):
    print('  sound=%-5s %-4s %5d' % (k[0], k[1], v))

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'handoff')
os.makedirs(OUT, exist_ok=True)
json.dump({'cross': {'%s|%s' % k: v for k, v in cross.items()},
           'tiers': {'%s|%s' % k: v for k, v in prop_kill_detail.items()},
           'per_diagram': per_diag},
          open(os.path.join(OUT, 'crosstab.json'), 'w'))
