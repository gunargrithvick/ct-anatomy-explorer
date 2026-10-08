"""Keep only the cases you choose in the website data (and put them in your order).

    python tools/select_cases.py docs/data s0011 s0034 s0102 s0207 s0381

Removes the other case folders and rewrites docs/data/cases.json.
Case titles become "Case 1", "Case 2", ... in the order given.
"""
import json
import shutil
import sys
from pathlib import Path

if len(sys.argv) < 3:
    sys.exit(__doc__)
data = Path(sys.argv[1])
keep = sys.argv[2:]
manifest_path = data / "cases.json"
m = json.loads(manifest_path.read_text())
by_id = {c["id"]: c for c in m["cases"]}
missing = [k for k in keep if k not in by_id]
if missing:
    sys.exit(f"Not in {manifest_path}: {missing}. Available: {list(by_id)}")
m["cases"] = [by_id[k] for k in keep]
for i, c in enumerate(m["cases"], 1):
    c["title"] = f"Case {i}"
for cid in by_id:
    if cid not in keep:
        shutil.rmtree(data / cid, ignore_errors=True)
manifest_path.write_text(json.dumps(m, indent=1))
print(f"Kept {len(keep)} cases: {', '.join(keep)}")
