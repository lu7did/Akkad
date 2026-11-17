"""BNN evaluator subprocess entrypoint; Nurse's standard JSONL interface."""
from ..evaluator import main
if __name__ == '__main__':
    raise SystemExit(main('bnn'))
