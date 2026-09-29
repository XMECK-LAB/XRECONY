from pathlib import Path
import re, sys
root=Path(__file__).resolve().parent
required=["README.md","CITATION.cff","SECURITY.md","CHANGELOG.md","assets/brand/xrecony-hero.svg","assets/diagrams/workflow.svg","assets/diagrams/architecture.svg","demo/index.html"]
missing=[p for p in required if not (root/p).exists()]
if missing:
    print("MISSING",missing); sys.exit(1)
for bad in ["__pycache__",".build-venv","build","dist"]:
    if any(p.name==bad for p in root.rglob('*')):
        print("FORBIDDEN",bad); sys.exit(2)
print("PASS_PUBLIC_REPO_STRUCTURE")
