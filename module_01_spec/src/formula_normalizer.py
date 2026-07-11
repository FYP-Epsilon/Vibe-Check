import re

class FormulaNormalizer:
    """
    Normalizes hand-rolled LTLf strings into SPOT-compatible grammar,
    and provides a round-trip denormalization method.
    """
    
    @staticmethod
    def normalize(formula: str) -> str:
        """
        Converts M01 LTLf string to SPOT grammar.
        - && -> &
        - || -> |
        - start(X) -> start_X
        - done(X) -> done_X
        """
        f = formula.replace("&&", "&").replace("||", "|")
        
        # Mangle start(X) and done(X)
        # Assuming X contains only alphanumeric and underscores
        f = re.sub(r'start\(([^)]+)\)', r'start_\1', f)
        f = re.sub(r'done\(([^)]+)\)', r'done_\1', f)
        
        # Handle <-> to <-> (SPOT supports <->, no change needed usually, but just in case)
        # Handle -> to -> (SPOT supports ->)
        return f

    @staticmethod
    def denormalize(formula: str) -> str:
        """
        Reverts SPOT grammar back to M01 LTLf string.
        """
        f = formula.replace("&", "&&").replace("|", "||")
        
        # We need to be careful not to replace &&& if that happens, but simple replace is fine for this subset
        f = re.sub(r'start_([a-zA-Z0-9_]+)', r'start(\1)', f)
        f = re.sub(r'done_([a-zA-Z0-9_]+)', r'done(\1)', f)
        
        return f
