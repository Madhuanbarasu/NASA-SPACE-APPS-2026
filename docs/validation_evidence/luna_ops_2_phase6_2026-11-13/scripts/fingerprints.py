"""Print the validated-engine fingerprints and the official report hash (read only).
Run from backend/:  python <this file>"""
import hashlib, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from lunaops import ALGORITHM_VERSION
from lunaops.fingerprint import code_fingerprint, suite_fingerprint
from validation.terrain_gate import acceptance_digest
print("algorithm", ALGORITHM_VERSION)
print("code_fingerprint", code_fingerprint())
print("suite_fingerprint", suite_fingerprint())
print("terrain_acceptance_digest", acceptance_digest())
print(hashlib.sha256(Path("validation/report.json").read_bytes()).hexdigest(), "*validation/report.json")
