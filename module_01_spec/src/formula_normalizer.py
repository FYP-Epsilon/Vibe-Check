import re


class FormulaNormalizer:
    """
    Normalizes hand-rolled LTLf strings into a standardized grammar,
    and provides a round-trip denormalization method.

    Normalization rules:
        && -> &
        || -> |
        start(X) -> start_X
        done(X)  -> done_X
    """

    @staticmethod
    def normalize(formula: str) -> str:
        """
        Converts M01 LTLf string to standard grammar.
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
            # Clean special chars to underscores for standard identifiers
            clean = re.sub(r'[^a-zA-Z0-9_]', '_', name)
            return f"{prefix}_{clean}"

        f = re.sub(r'(start|done)\(([^)]+)\)', _mangle_atom, f)

        return f

    @staticmethod
    def denormalize(formula: str) -> str:
        """
        Reverts standard grammar back to M01 LTLf string.
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
