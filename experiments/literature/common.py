import os

for key in (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "BLIS_NUM_THREADS",
):
    os.environ[key] = "1"
os.environ.update(
    PHOEBE_MULTIPROC_NPROCS="0",
    PHOEBE_ENABLE_MPI="FALSE",
    PHOEBE_ENABLE_PLOTTING="FALSE",
    PHOEBE_ENABLE_SYMPY="FALSE",
    PHOEBE_ENABLE_ONLINE_PASSBANDS="FALSE",
    PYTHONDONTWRITEBYTECODE="1",
)
import sys, json, hashlib
from pathlib import Path
from datetime import datetime, timezone

TREE = Path(__file__).resolve().parents[2]
SCRATCH = Path(os.getenv("PHOEBE_STUDY_SCRATCH", TREE.parent))
OUT = Path(os.getenv("PHOEBE_STUDY_OUT", SCRATCH / "phoebe-literature-results-20261118"))
OLD = SCRATCH / "phoebe-eight-results-20261118"
sys.dont_write_bytecode = True
sys.path.insert(0, str(TREE / "site/engine"))
KEYS = [
    "inclination",
    "radius_primary",
    "radius_secondary",
    "temperature_ratio",
    "mass_ratio",
    "period",
    "eccentricity",
    "omega",
]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(path, obj):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, allow_nan=False) + "\n")
    tmp.replace(path)


def status(message):
    with (OUT / "STATUS.md").open("a") as f:
        print(
            "\n" + datetime.now(timezone.utc).isoformat(timespec="seconds") + "  " + message,
            file=f,
        )
