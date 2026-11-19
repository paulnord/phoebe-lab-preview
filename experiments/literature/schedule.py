import os
import json
import sys
from pathlib import Path
from common import OUT, status
import fcntl, signal, subprocess as sp, time, uuid

unit = "fifth42-lower100b.service"
tracker = Path("/home/pnord/fifth42-lower100b-20261113/STATUS.json")


def ctl(*args):
    return sp.check_output(["systemctl", "--user", *args], text=True).strip()


def progress():
    return json.loads(tracker.read_text())


def interrupted(*args):
    raise InterruptedError("scheduler interrupted")


def batch(ids, workers):
    start = progress()
    if ctl("show", "-p", "FreezerState", "--value", unit) != "running" or start["status"] not in (
        "running",
        "between_jobs",
    ):
        raise RuntimeError("unexpected fifth42 state")
    timer = "phoebe-thaw-" + uuid.uuid4().hex
    # Independent safety timer outlives the scheduler. Stop only after verified thaw.
    sp.run(
        [
            "systemd-run",
            "--user",
            "--quiet",
            "--unit=" + timer,
            "--on-active=150s",
            "--timer-property=AccuracySec=1s",
            "/usr/bin/systemctl",
            "--user",
            "thaw",
            unit,
        ],
        check=True,
    )
    t = time.monotonic()
    try:
        ctl("freeze", unit)
        proc = sp.Popen(
            [
                "nice",
                "-n",
                "15",
                "taskset",
                "-c",
                f"0-{workers-1}",
                sys.executable,
                str(Path(__file__).with_name("exact.py")),
                str(workers),
                *ids,
            ],
            start_new_session=True,
        )
        try:
            rc = proc.wait(timeout=125)
            if rc:
                raise RuntimeError(f"exact workers exited {rc}")
        except BaseException:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            proc.wait()
            raise
    finally:
        ctl("thaw", unit)
        assert ctl("show", "-p", "FreezerState", "--value", unit) == "running"
        ctl("stop", timer + ".timer")
        for _ in range(150):
            end = progress()
            if end["durable_native_cells"] > start["durable_native_cells"]:
                break
            time.sleep(1)
        else:
            raise RuntimeError("fifth42 progress not verified")
        with (OUT / "scheduling.jsonl").open("a") as f:
            print(
                json.dumps(
                    dict(
                        ids=ids,
                        workers=workers,
                        elapsed=time.monotonic() - t,
                        before=start["durable_native_cells"],
                        after=end["durable_native_cells"],
                        pid=end["pid"],
                    )
                ),
                file=f,
            )


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupted)
    lock = (OUT / "scheduler.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    (OUT / "curves").mkdir(exist_ok=True)
    spec = json.loads((OUT / "manifest.json").read_text())
    stage = sys.argv[1]
    if stage == "audit":
        from archive import study_rows

        os.environ["PHOEBE_AUDIT"] = "1"
        (OUT / "strict").mkdir(exist_ok=True)
        ids = []
        for r in study_rows():
            row = json.loads((OUT / "curves" / (r["id"] + ".json")).read_text())
            broad = r["family"] == "wide" and r["mode"] != "sphere"
            edge = r["family"] == "surface" and (
                r["split"] == "probe"
                or r["system"] in ("surface-train-0004", "surface-train-0069")
            )
            example = r["family"] == "eccentric" and r["system"] in (
                "eccentric-blind-0002",
                "eccentric-train-0000",
                "eccentric-train-0007",
            )
            if (
                r["triangles"] == 400
                and (broad or edge or example)
                and row["status"] == "ok"
                and not row.get("strict_atmosphere")
            ):
                ids.append(r["id"])
    elif stage == "paired-extension":
        ids = [r["id"] for r in json.loads((OUT / "paired-extension.json").read_text())]
    elif stage == "enrich":
        ids = [r["id"] for r in json.loads((OUT / "enrich.json").read_text())]
    elif stage in ("eccentric", "mixed"):
        ids = [
            r["id"]
            for r in json.loads((OUT / "supplement.json").read_text())
            if r["family"] == ("wide" if stage == "mixed" else "eccentric")
        ]
    elif stage == "pilot":
        ids = spec["pilot"]
    elif stage in ("wide", "surface", "resolution"):
        ids = [
            r["id"]
            for r in spec["cases"]
            if (stage == "wide" and r["family"] == "wide" and r["mode"] == "sphere")
            or (stage == "surface" and r["family"] == "surface" and r["triangles"] == 400)
            or (stage == "resolution" and r["triangles"] > 400)
        ]
    else:
        raise ValueError("Unknown stage: " + stage)
    workers = int(sys.argv[2])
    size = int(sys.argv[3])
    assert 1 <= workers <= 12 and 1 <= size <= 144
    dest = OUT / ("strict" if stage == "audit" else "curves")
    todo = [i for i in ids if not (dest / (i + ".json")).exists()]
    status(f"Starting {stage}, {len(todo)} remaining exact runs at {workers} workers.")
    for j in range(0, len(todo), size):
        batch(todo[j : j + size], workers)
        status(
            f"{stage} checkpoint {min(j+size,len(todo))}/{len(todo)}. fifth42 thaw and progress verified."
        )
