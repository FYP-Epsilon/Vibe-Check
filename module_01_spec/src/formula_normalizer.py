import re


class FormulaNormalizer:
    """
    UNUSED — not part of the real pipeline. Never imported by api.py or
    main.py; confirmed by grep, not assumed (Next Steps.md item #11).
    Module 03's property_ingest.py ports its own LTLf normalization
    instead of importing this class (dual-track independence: Module 03
    deploys as its own container with no access to Module 01's source),
    and that ported version does something different from this one —
    it collapses start(T)/done(T) into a single flat, quoted atom per
    task, whereas this class keeps them as separate start_X/done_X
    atoms. So even setting aside that this is dead code, its specific
    output format is not what real SPOT ingestion actually expects
    today; do not resurrect this class as-is under the assumption its
    grammar still matches property_ingest.py's.

    Original docstring, describing what the code below still does if
    called directly: normalizes hand-rolled LTLf strings into
    SPOT-compatible grammar, and provides a round-trip denormalization
    method.

    Normalization rules:
        && -> &
        || -> |
        start(X) -> start_X
        done(X)  -> done_X
    """

    @staticmethod
    def normalize(formula: str) -> str:
        """
        Converts M01 LTLf string to SPOT grammar.
        - && -> &  (but not a bare & that was already single)
        - || -> |
        - start(X) -> start_X
        - done(X) -> done_X
        """
        # Replace && with a single &
        f = formula.replace("&&", "&")
        # Replace || with a single |
        f = f.replace("||", "|")

        # Mangle start(X) and done(X) — X can contain alphanumeric, underscores,
        # dots, hyphens, slashes, and spaces (cleaned to underscores)
        def _mangle_atom(match: re.Match) -> str:
            prefix = match.group(1)  # 'start' or 'done'
            name = match.group(2)
            # Clean special chars to underscores for SPOT identifiers
            clean = re.sub(r'[^a-zA-Z0-9_]', '_', name)
            return f"{prefix}_{clean}"

        f = re.sub(r'(start|done)\(([^)]+)\)', _mangle_atom, f)

        return f

    @staticmethod
    def denormalize(formula: str) -> str:
        """
        Reverts SPOT grammar back to M01 LTLf string.
        - Single & (not already &&) -> &&
        - Single | (not already ||) -> ||
        - start_X -> start(X)
        - done_X  -> done(X)
        """
        # First, restore start_X and done_X back to start(X) and done(X).
        # Match start_ or done_ followed by one or more word characters,
        # but only if not already in the form start(X) or done(X).
        f = re.sub(r'\b(start|done)_([a-zA-Z0-9_]+)', r'\1(\2)', formula)

        # Restore & -> && and | -> ||
        # Use negative lookbehind/lookahead to avoid doubling already-doubled operators.
        # Replace single & that is not part of && with &&
        f = re.sub(r'(?<!\&)\&(?!\&)', '&&', f)
        # Replace single | that is not part of || with ||
        f = re.sub(r'(?<!\|)\|(?!\|)', '||', f)

        return f
