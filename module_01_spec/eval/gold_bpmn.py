"""gold_bpmn.py -- independent gold-standard BPMN labeler for the M01 eval.

Anti-circularity rule (load-bearing -- do not violate): this module must
NEVER import anything from ``module_01_spec/src/``. It derives the gold
node/edge set straight from the BPMN 2.0 XML with ``ElementTree``,
independently of the ``SemanticExtractionEngine`` being evaluated. If this
module ever imports the extractor, the structural-fidelity numbers become
circular and meaningless -- enforced by ``eval/test_gold_bpmn.py``'s
import-scan test, the same discipline as Module 02's ``eval/gold_wir.py``.

Vocabulary independence (the reason this file exists at all). The design
memo records that its *first* labeler derived the node set by excluding a
``NON_NODE_TAGS``-shaped list -- which is ``semantic_extractor``'s own
vocabulary, so agreement would have been partly definitional.
``SPEC_FLOW_NODES`` below is therefore an explicit **allowlist transcribed
from the BPMN 2.0 flow-node taxonomy** (the event, activity and gateway
families of the standard's ``FlowNode`` hierarchy), not a copy of
``semantic_extractor.EXECUTABLE_NODES`` nor a complement of its
``NON_NODE_TAGS``. The two vocabularies are deliberately *not* identical:
this allowlist carries ``transaction`` and ``adHocSubProcess`` (BPMN 2.0
activity subclasses the extractor omits) and ``complexGateway`` (a gateway
subclass the extractor omits). Those element types do not occur in the
FLOW-BENCH corpus, so the two definitions coincide *on this data* without
being copies of each other -- which is the condition under which agreement
is evidence rather than tautology.

Scope decisions, stated because they set the structural denominator:

* ``subProcess`` counts as **one node**, and its children are *also*
  counted (the walk is fully recursive). This matches the extractor, which
  finds nested elements via ``.//``, and matches the memo's choice. The memo
  logs the alternative -- flattening a subProcess into its children without
  counting the wrapper -- as an ``[OPEN]`` question; see the harness report
  for the decision and its measured effect.
* Only elements in the BPMN MODEL namespace carrying an ``id`` are eligible.
  ``bpmndi:`` / ``dc:`` / ``di:`` presentation elements are never nodes.
* An edge is a ``sequenceFlow`` keyed by ``(flow_id, sourceRef, targetRef)``.
  Message flows and associations are not sequence flows and are excluded.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple

EVAL_DIR = Path(__file__).resolve().parent
MODULE01_DIR = EVAL_DIR.parent
REPO_ROOT = MODULE01_DIR.parent
CORPUS_ROOT = REPO_ROOT / "flow-bench" / "data"
RESULTS_DIR = EVAL_DIR / "results"

#: BPMN 2.0 MODEL namespace.
BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"

#: BPMN 2.0 flow-node taxonomy, transcribed from the standard's FlowNode
#: hierarchy (events, activities, gateways). NOT copied from
#: semantic_extractor.EXECUTABLE_NODES -- see the module docstring.
SPEC_FLOW_NODES: Set[str] = {
    # --- Event family -------------------------------------------------
    "startEvent",
    "endEvent",
    "intermediateCatchEvent",
    "intermediateThrowEvent",
    "boundaryEvent",
    # --- Activity family ----------------------------------------------
    "task",
    "userTask",
    "serviceTask",
    "scriptTask",
    "manualTask",
    "receiveTask",
    "sendTask",
    "businessRuleTask",
    "subProcess",
    "transaction",
    "adHocSubProcess",
    "callActivity",
    # --- Gateway family -----------------------------------------------
    "exclusiveGateway",
    "parallelGateway",
    "inclusiveGateway",
    "eventBasedGateway",
    "complexGateway",
}

#: Corpora, in the order they are reported. Kept separate rather than
#: pooled: 47 uids appear in both, so pooling would double-count related
#: diagrams and violate the independence assumption behind a binomial
#: interval. ``context`` is a held-out replication set.
CORPORA: Tuple[str, ...] = ("output", "context")


def _localname(tag: str) -> str:
    """Strip a Clark-notation namespace from an ElementTree tag."""
    return tag.split("}")[-1] if "}" in tag else tag


def _in_bpmn_namespace(tag: str) -> bool:
    return tag.startswith("{%s}" % BPMN_NS)


def gold_label(xml_text: str) -> Dict[str, object]:
    """Label one BPMN document from the XML alone.

    Returns a dict with:
        ``nodes``            -- set of ``(node_id, node_type)``
        ``edges``            -- set of ``(flow_id, source_ref, target_ref)``
        ``has_branch``       -- True iff some node has >1 outgoing sequence flow
        ``branch_points``    -- sorted ids of those nodes
        ``duplicate_names``  -- clean_name -> sorted ids, for names shared by
            more than one *activity* node (the construct that collapses two
            distinct task node-ids onto a single atomic proposition)
    """
    root = ET.fromstring(xml_text)

    nodes: Set[Tuple[str, str]] = set()
    edges: Set[Tuple[str, str, str]] = set()
    activity_names: Dict[str, List[str]] = {}

    for elem in root.iter():
        if not _in_bpmn_namespace(elem.tag):
            continue
        tag = _localname(elem.tag)

        if tag == "sequenceFlow":
            source, target = elem.get("sourceRef"), elem.get("targetRef")
            if source and target:
                edges.add((elem.get("id"), source, target))
            continue

        node_id = elem.get("id")
        if tag not in SPEC_FLOW_NODES or not node_id:
            continue
        nodes.add((node_id, tag))

        # semantic_extractor derives an atomic proposition from the name
        # (falling back to the id), so two distinct activity ids sharing a
        # name collapse to one proposition. Recorded here from the XML only.
        if "task" in tag.lower():
            raw_name = elem.get("name", node_id)
            clean = raw_name.replace(" ", "_").replace("\n", "_")
            activity_names.setdefault(clean, []).append(node_id)

    out_degree: Dict[str, int] = {}
    for _flow_id, source, _target in edges:
        out_degree[source] = out_degree.get(source, 0) + 1
    branch_points = sorted(nid for nid, deg in out_degree.items() if deg > 1)

    duplicate_names = {
        name: sorted(ids) for name, ids in activity_names.items() if len(ids) > 1
    }

    return {
        "nodes": nodes,
        "edges": edges,
        "has_branch": bool(branch_points),
        "branch_points": branch_points,
        "duplicate_names": duplicate_names,
    }


def gold_label_file(path: Path) -> Dict[str, object]:
    """Label one BPMN file on disk."""
    return gold_label(Path(path).read_text(encoding="utf-8"))


def corpus_files(corpus: str, corpus_root: Path = CORPUS_ROOT) -> List[Path]:
    """All ``.bpmn`` files of one corpus, in a stable sorted order."""
    return sorted((Path(corpus_root) / corpus).glob("*.bpmn"))


def uid_of(path: Path) -> str:
    """``.../uid_20_output.bpmn`` -> ``uid_20``."""
    parts = Path(path).stem.split("_")
    return "_".join(parts[:2])


def score_sets(gold: Set[object], extracted: Set[object]) -> Dict[str, float]:
    """Micro precision/recall/F1 plus raw tp/fp/fn for two label sets."""
    tp = len(gold & extracted)
    fp = len(extracted - gold)
    fn = len(gold - extracted)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def aggregate_scores(rows: Sequence[Dict[str, float]]) -> Dict[str, float]:
    """Micro-aggregate per-diagram tp/fp/fn dicts into one P/R/F1."""
    tp = sum(r["tp"] for r in rows)
    fp = sum(r["fp"] for r in rows)
    fn = sum(r["fn"] for r in rows)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }
