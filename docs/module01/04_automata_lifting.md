# Phase 4: Automata Lifting

## Objective
To mathematically convert the validated temporal rules (LTLf strings) into deterministic state machines (Büchi Automata).

## Implementation (`automata_lifter.py`)
This phase utilizes the C++ `spot` library.
The module translates each formula (e.g., `!start(B) W done(A)`) into a minimal automaton structure. This is required because Module 03 (Stuttering Bisimulation) requires finite state machines to mathematically execute the equivalence proof.

## Fail-Safe Architecture
Since `spot` is a Linux/WSL library, the VibeCheck pipeline is designed not to crash if run on a standard Windows environment without WSL. If the library fails to import, the engine gracefully intercepts the error, emits a `PASS_NO_SPOT` certificate, and hands off the LTLf string arrays directly to Module 03 (allowing Module 03 to handle the automata generation in its own environment).
