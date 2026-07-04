"""composer.py -- multi-modal certificate composer (MultiModalCertificateComposer).

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

from typing import Any, Callable, Optional, get_type_hints


class MultiModalCertificateComposer:
    """
    Combine the independent V1, V2, and V3 correctness certificates into
    a single multi-modal confidence score.
    """

    @staticmethod
    def compose(
        v1_cert: dict[str, Any],
        v2_cert: dict[str, Any],
        v3_cert: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Compute combined confidence from the two behavioral (correctness)
        layers, assuming independence of failure modes::

            combined = 1 - (1 - v1) * (1 - v2)

        V3 measures extraction fidelity, not correctness -- it does not
        enter the OR-composition (a saturated V3 term made the verdict
        vacuous for any structurally extractable program). Instead V3 acts
        as a gate: if extraction fidelity is below threshold (``abort``),
        the result fails regardless of V1/V2, since a low-fidelity WIR means
        V1/V2 were run against an unfaithful model in the first place.
        """
        v1 = v1_cert.get("confidence", 0.0)
        v2 = v2_cert.get("confidence", 0.0)
        v3 = v3_cert.get("confidence", 0.0)
        v3_abort = v3_cert.get("abort", False)

        combined = 1.0 - (1.0 - v1) * (1.0 - v2)

        if v3_abort:
            passed = False
            message = "V3 extraction fidelity below threshold -- manual review required."
        else:
            passed = combined >= 0.95
            message = (
                "WIR validated -- passed to Module 03."
                if passed
                else "Flag for manual review -- combined confidence below 0.95."
            )

        return {
            "version": "V1+V2+V3",
            "combined_confidence": combined,
            "v1_confidence": v1,
            "v2_confidence": v2,
            "v3_confidence": v3,  # extraction-fidelity score, not a correctness signal
            "v3_abort": v3_abort,
            "passed": passed,
            "message": message,
        }
