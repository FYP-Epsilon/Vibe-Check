"""Local pytest configuration for the Module 01 eval harness.

Registers the ``slow`` marker used by the corpus-sweep regression tests, so
`pytest module_01_spec/eval/ -m "not slow"` runs the unit tests alone
without emitting unknown-marker warnings.
"""

from __future__ import annotations


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "slow: corpus-scale sweep over all 148 FLOW-BENCH diagrams",
    )
