"""Run ingest -> load -> clean -> validate as isolated, logged processes."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from db import DB_PATH, ROOT, connect
from pipeline_runtime import iso_time, run_clock, wall_time

LOG_PATH = ROOT / "data/pipeline_log.db"
LOCK_PATH = ROOT / "data/pipeline.lock"
STEPS = ("src/ingest.py", "src/load.py", "src/clean.py", "src/validate.py")
CREATE_LOG = """CREATE TABLE IF NOT EXISTS pipeline_run (
    run_id TEXT NOT NULL, run_time TEXT NOT NULL, step TEXT NOT NULL,
    started_at TEXT NOT NULL, finished_at TEXT NOT NULL, exit_code INTEGER NOT NULL,
    run_kind TEXT NOT NULL CHECK(run_kind IN ('scheduled','manual','rebuild')),
    detail TEXT NOT NULL, PRIMARY KEY(run_id,step)
) STRICT"""
INSERT_LOG = """INSERT INTO pipeline_run
    (run_id,run_time,step,started_at,finished_at,exit_code,run_kind,detail)
    VALUES (?,?,?,?,?,?,?,?)"""


def run_step(command, *, timeout, output, environment):
    """No production step spawns children; run() kills/waits for its child on timeout."""
    with output.open("w", encoding="utf-8") as stream:
        try:
            result = subprocess.run(command, cwd=ROOT, env=environment, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=timeout)
            return result.returncode
        except subprocess.TimeoutExpired:
            stream.write("\nERROR: step timeout; process terminated, exit_code=124\n")
            return 124
        except OSError as exc:
            stream.write("\nERROR: could not launch step: " + str(exc) + "\n")
            return 1


def run_pipeline(args):
    clock = iso_time(run_clock(args.run_time))
    kind = "rebuild" if args.skip_ingest else args.kind
    args.lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(args.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        print("Pipeline already locked; no steps ran. exit_code=75")
        return 75
    run_id = uuid.uuid4().hex
    log = None
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid(), "run_id": run_id, "run_time": clock}, stream)
        log = connect(args.log_db, create=True)
        log.execute(CREATE_LOG)
        log.commit()
        output_dir = ROOT / "logs" / run_id
        output_dir.mkdir(parents=True)
        environment = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONUTF8="1",
                           PIPELINE_RUN_ID=run_id, PIPELINE_LOG_DB=str(args.log_db.resolve()))
        metrics = output_dir/'load_metrics.json'
        environment['PIPELINE_METRICS'] = str(metrics)
        for step in STEPS[1:] if args.skip_ingest else STEPS:
            command = [sys.executable, step, "--run-time", clock]
            if step != "src/ingest.py":
                command += ["--db", str(args.db.resolve())]
            else:
                command += ["--raw-dir", str(args.raw_dir.resolve())]
            if step == "src/load.py":
                command += ["--raw-dir", str(args.raw_dir.resolve())]
            started = wall_time()
            output = output_dir / (Path(step).stem + ".txt")
            code = run_step(command, timeout=args.timeout, output=output, environment=environment)
            detail = {"output": output.relative_to(ROOT).as_posix(), "command": command,
                      "expected_steps": list(STEPS[1:] if args.skip_ingest else STEPS)}
            if step=='src/load.py' and code==0 and metrics.exists():
                detail['load'] = json.loads(metrics.read_text(encoding='utf-8'))
            with log:
                log.execute(INSERT_LOG, (run_id, clock, step, started, wall_time(), code,
                                         kind, json.dumps(detail)))
            print(output.read_text(encoding="utf-8"), end="", flush=True)
            if code:
                print(f"Pipeline FAILED: {step}; exit_code={code}; run_id={run_id}")
                return code
        print(f"Pipeline SUCCEEDED; run_id={run_id}; kind={kind}; run_time={clock}")
        return 0
    finally:
        if log is not None:
            log.close()
        args.lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-time")
    parser.add_argument("--skip-ingest", action="store_true")
    parser.add_argument("--kind", choices=("manual", "scheduled"), default="manual")
    parser.add_argument("--timeout", type=float, default=1800,
                        help="Maximum seconds per step (default 30 minutes)")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--log-db", type=Path, default=LOG_PATH)
    parser.add_argument("--lock", type=Path, default=LOCK_PATH)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.log_db.resolve() == args.db.resolve():
        parser.error("Run log must be separate from the data database")
    try:
        raise SystemExit(run_pipeline(args))
    except (OSError, ValueError) as exc:
        print("Pipeline FAILED: runner infrastructure: " + str(exc))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
