"""test_harness.py -- tests for the M01 FLOW-BENCH evaluation harness.

Two kinds of test live here:

* **Unit tests** for the metric definitions and the statistics, which run
  fast and need no corpus.
* **Corpus regression tests** (marked ``slow``) that pin the figures this
  harness reproduces. These are the guard that a future refactor of
  ``src/`` cannot silently move a headline number: they assert the exact
  values independently verified in the memo's reproduction log and PR #89,
  not merely that the harness runs.

Run everything:            pytest module_01_spec/eval/
Skip the corpus sweep:     pytest module_01_spec/eval/ -m "not slow"
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).resolve().parent
MODULE01_DIR = EVAL_DIR.parent
sys.path.insert(0, str(EVAL_DIR))
sys.path.insert(0, str(MODULE01_DIR / "src"))

import mutate_eval  # noqa: E402
import report  # noqa: E402
import soundness  # noqa: E402
from gold_bpmn import CORPORA, corpus_files  # noqa: E402
from mutation_refiner import LTLfAuditor  # noqa: E402

# --------------------------------------------------------------------------
# Expected figures. Sources, so a future reader can re-check rather than
# trust: the soundness and crosstab numbers are the AFTER block of
# PR_fix_mod1_flowbench_defects.md, independently re-derived in
# "Phase 2 - Defect Fixes (PR #89)/reproduction_verification_log.txt".
# --------------------------------------------------------------------------

EXPECTED_CORPUS_SIZES = {"output": 100, "context": 48}
EXPECTED_SOUND = {"output": 98, "context": 47}
EXPECTED_BRANCH_SOUND = {"output": (31, 31), "context": (18, 19)}
EXPECTED_NOBRANCH_SOUND = {"output": (67, 69), "context": (29, 29)}
EXPECTED_UNSOUND_UIDS = {("output", "uid_67"), ("output", "uid_8"), ("context", "uid_92")}

#: Sound-suite mutant crosstab, both corpora pooled at the MUTANT level.
#: (Pooling mutants is fine; pooling *diagrams* across corpora is not,
#: which is why the rates in the report stay split.)
EXPECTED_SOUND_SUITE_MUTANTS = 2900
EXPECTED_SOUND_SUITE_PROPERTY_KILLS = 0
EXPECTED_SOUND_SUITE_DISCONNECTION_KILLS = 1672
EXPECTED_SOUND_SUITE_SURVIVED = 1228


@pytest.fixture(scope="module")
def sound_results():
    return soundness.run_all()


@pytest.fixture(scope="module")
def mutation_results():
    return mutate_eval.run_all()


class TestClopperPearson:
    """Statistics are inherited from module_02_extract/eval, not re-derived."""

    def test_interval_brackets_the_point_estimate(self):
        lo, hi = report.clopper_pearson(5, 10)
        assert lo < 0.5 < hi

    def test_zero_successes_has_zero_lower_bound(self):
        lo, hi = report.clopper_pearson(0, 20)
        assert lo == 0.0
        assert 0.0 < hi < 1.0

    def test_all_successes_has_unit_upper_bound(self):
        lo, hi = report.clopper_pearson(20, 20)
        assert hi == 1.0
        assert 0.0 < lo < 1.0

    def test_empty_sample_is_maximally_uninformative(self):
        assert report.clopper_pearson(0, 0) == (0.0, 1.0)

    def test_interval_narrows_as_n_grows(self):
        narrow = report.clopper_pearson(500, 1000)
        wide = report.clopper_pearson(5, 10)
        assert (narrow[1] - narrow[0]) < (wide[1] - wide[0])

    def test_known_value_matches_textbook(self):
        """Clopper-Pearson(2, 10) = [0.0252, 0.5561] to 4 dp."""
        lo, hi = report.clopper_pearson(2, 10)
        assert lo == pytest.approx(0.0252, abs=1e-4)
        assert hi == pytest.approx(0.5561, abs=1e-4)

    def test_rate_cell_never_prints_a_bare_rate(self):
        cell = report.rate_cell(98, 100)
        assert "98/100" in cell and "[" in cell and "]" in cell


class TestKillMechanismSeparation:
    """The secondary metric must never conflate the two kill mechanisms."""

    def test_mechanism_labels_come_from_the_auditor(self):
        assert mutate_eval.KILL_BY_PROPERTY == LTLfAuditor.KILL_BY_PROPERTY
        assert mutate_eval.KILL_BY_DISCONNECTION == LTLfAuditor.KILL_BY_DISCONNECTION
        assert mutate_eval.KILL_BY_PROPERTY != mutate_eval.KILL_BY_DISCONNECTION

    def test_discriminative_ratio_excludes_disconnection_kills(self):
        row = mutate_eval.DiagramMutationResult(
            corpus="output",
            uid="uid_test",
            sound=True,
            has_branch=False,
            mutants_requested=20,
            mutants_generated=20,
            killed_by_property=0,
            killed_by_disconnection=15,
            survived=5,
        )
        assert row.raw_kill_ratio == pytest.approx(0.75)
        assert row.discriminative_kill_ratio == pytest.approx(0.0)

    def test_ratios_are_zero_not_nan_when_no_mutants_generated(self):
        row = mutate_eval.DiagramMutationResult(
            corpus="output",
            uid="uid_test",
            sound=True,
            has_branch=False,
            mutants_requested=20,
            mutants_generated=0,
            killed_by_property=0,
            killed_by_disconnection=0,
            survived=0,
        )
        assert row.raw_kill_ratio == 0.0
        assert row.discriminative_kill_ratio == 0.0

    def test_phase3_configuration_is_the_shipped_one(self):
        assert mutate_eval.SEED == 42
        assert mutate_eval.MUTANTS_PER_DIAGRAM == 20


class TestCorpus:
    def test_corpora_are_reported_separately(self):
        assert CORPORA == ("output", "context")

    def test_corpus_sizes(self):
        for corpus, expected in EXPECTED_CORPUS_SIZES.items():
            assert len(corpus_files(corpus)) == expected

    def test_corpus_overlap_matches_the_memo(self):
        """Memo Section 1: 47 shared uids, 53 output-only, uid_90 context-only.

        This is the fact that forbids pooling, so it is pinned rather than
        recomputed-and-trusted each run.
        """
        overlap = report.corpus_overlap()
        assert overlap["shared"] == 47
        assert len(overlap["output_only"]) == 53
        assert overlap["context_only"] == ["uid_90"]

    def test_context_is_a_paired_replicate_not_a_held_out_set(self):
        """Guards the report's caveat against a future corpus swap.

        If someone later makes `context` genuinely disjoint, this test fails
        and the report's "paired near-replicate" wording must be revisited --
        the wording would then understate the evidence.
        """
        overlap = report.corpus_overlap()
        assert len(overlap["context_only"]) < 0.1 * overlap["context_n"]


@pytest.mark.slow
class TestSoundnessRegression:
    """Pins the primary metric to its independently-verified values."""

    def test_soundness_counts_match_pr89(self, sound_results):
        for corpus, expected in EXPECTED_SOUND.items():
            stats = soundness.summarize(sound_results[corpus])
            assert stats["n"] == EXPECTED_CORPUS_SIZES[corpus]
            assert stats["sound"] == expected

    def test_branch_stratification_matches_pr89(self, sound_results):
        for corpus in CORPORA:
            stats = soundness.summarize(sound_results[corpus])
            assert (stats["branch_sound"], stats["branch_n"]) == EXPECTED_BRANCH_SOUND[
                corpus
            ]
            assert (
                stats["nobranch_sound"],
                stats["nobranch_n"],
            ) == EXPECTED_NOBRANCH_SOUND[corpus]

    def test_the_three_unsound_diagrams_are_the_known_ones(self, sound_results):
        found = {
            (r.corpus, r.uid)
            for corpus in CORPORA
            for r in sound_results[corpus]
            if not r.sound
        }
        assert found == EXPECTED_UNSOUND_UIDS

    def test_every_unsound_suite_is_rejected_by_a_p1_property(self, sound_results):
        """The unsound diagrams fail on ordering, not on disconnection."""
        for corpus in CORPORA:
            for r in sound_results[corpus]:
                if not r.sound:
                    assert r.rejecting_tier == "P1_Structural_Control_Flow"
                    assert r.rejecting_property

    def test_unsoundness_coincides_with_duplicate_propositions(self, sound_results):
        """Every unsound diagram carries the duplicate-name construct.

        Labelled, never excluded -- excluding them would raise the headline
        soundness rate by redefining the denominator.
        """
        for corpus in CORPORA:
            for r in sound_results[corpus]:
                if not r.sound:
                    assert r.duplicate_proposition_names

    def test_no_unparseable_properties_remain(self, sound_results):
        """Regression guard for the PR #89 loop-bound fix.

        The memo's pilots had to strip an unparseable `/* loop_bound=10 */`
        P2 property. PR #89 moved the bound to typed `spec_metadata`. A
        non-zero count here means that defect came back.
        """
        total = sum(
            r.n_unparseable for corpus in CORPORA for r in sound_results[corpus]
        )
        assert total == 0

    def test_no_extraction_errors(self, sound_results):
        total = sum(
            1
            for corpus in CORPORA
            for r in sound_results[corpus]
            if r.extraction_error
        )
        assert total == 0


@pytest.mark.slow
class TestMutationRegression:
    """Pins the secondary metric to the PR #89 crosstab."""

    def test_sound_suite_crosstab_matches_pr89(self, mutation_results):
        mutants = property_kills = disconnection = survived = 0
        for corpus in CORPORA:
            bucket = mutate_eval.summarize(mutation_results[corpus])["sound_suite"]
            mutants += bucket["mutants"]
            property_kills += bucket["killed_by_property"]
            disconnection += bucket["killed_by_disconnection"]
            survived += bucket["survived"]
        assert mutants == EXPECTED_SOUND_SUITE_MUTANTS
        assert property_kills == EXPECTED_SOUND_SUITE_PROPERTY_KILLS
        assert disconnection == EXPECTED_SOUND_SUITE_DISCONNECTION_KILLS
        assert survived == EXPECTED_SOUND_SUITE_SURVIVED

    def test_headline_finding_zero_property_kills_on_sound_suites(
        self, mutation_results
    ):
        """The finding the whole metric exists to keep visible.

        If this ever fails with a POSITIVE count, that is good news and the
        report's central claim needs rewriting -- it is not a broken test.
        """
        for corpus in CORPORA:
            bucket = mutate_eval.summarize(mutation_results[corpus])["sound_suite"]
            assert bucket["killed_by_property"] == 0

    def test_raw_ratio_would_have_looked_strong(self, mutation_results):
        """Why the raw ratio is not reported as evidence.

        On sound-suite diagrams the raw kill ratio is substantial while the
        discriminative ratio is exactly zero -- the entire raw signal is
        disconnection.
        """
        killed_any = mutants = 0
        for corpus in CORPORA:
            bucket = mutate_eval.summarize(mutation_results[corpus])["sound_suite"]
            killed_any += bucket["killed_by_property"] + bucket["killed_by_disconnection"]
            mutants += bucket["mutants"]
        assert killed_any / mutants > 0.5

    def test_mutant_accounting_is_complete(self, mutation_results):
        """Every generated mutant lands in exactly one outcome bucket."""
        for corpus in CORPORA:
            for r in mutation_results[corpus]:
                assert (
                    r.killed_by_property + r.killed_by_disconnection + r.survived
                    == r.mutants_generated
                )


@pytest.mark.slow
class TestStructuralRegression:
    def test_extraction_is_exact_against_the_independent_labeler(self):
        rows = report.run_structural()
        for corpus in CORPORA:
            from gold_bpmn import aggregate_scores

            node_agg = aggregate_scores([r["node"] for r in rows[corpus]])
            edge_agg = aggregate_scores([r["edge"] for r in rows[corpus]])
            assert node_agg["fp"] == 0 and node_agg["fn"] == 0
            assert edge_agg["fp"] == 0 and edge_agg["fn"] == 0

    def test_subprocess_convention_is_load_bearing_and_measured(self):
        """The report must disclose the counterfactual, not assert inertness.

        58 of 148 diagrams carry a subProcess, so the wrapper-counts-as-node
        convention changes the number. The harness measures both.
        """
        sensitivity = report.subprocess_sensitivity()
        assert sensitivity["diagrams_with_subprocess"] > 0
        assert sensitivity["current"]["f1"] > sensitivity["flattened"]["f1"]
        assert sensitivity["flattened"]["fp"] == sensitivity["subprocess_wrappers"]
