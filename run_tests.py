import subprocess
import sys
from pathlib import Path

tests = sorted((Path(__file__).resolve().parent / "tests").glob("test_*.py"))
failed = []
for t in tests:
    print(f"=== {t.name} ===")
    r = subprocess.run([sys.executable, str(t)])
    if r.returncode != 0:
        failed.append(t.name)
print("=" * 40)
print(f"{len(tests) - len(failed)}/{len(tests)} suites green"
      + (f" — RED: {', '.join(failed)}" if failed else ""))
sys.exit(1 if failed else 0)
