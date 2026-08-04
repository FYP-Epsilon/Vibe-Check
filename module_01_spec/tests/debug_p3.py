import sys
from pathlib import Path
sys.path.insert(0, str(Path('../../module_01_spec/src').resolve()))
from api import run_module_01_pipeline
from test_harness import _first_corpus_diagram

res = run_module_01_pipeline(_first_corpus_diagram())
print(res)
