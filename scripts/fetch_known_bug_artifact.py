"""Fetch only the licensed, pinned source/trace subset used by this cohort."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request

from rtl_agent.common import ROOT


def main():
    manifest = json.loads((ROOT / "research/known_bug_benchmark/UPSTREAM_MANIFEST.json").read_text())
    destination = ROOT / "research/known_bug_benchmark/upstream"
    revision = manifest["commit"]
    def fetch(item):
        path = Path(item["path"])
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Unsafe pinned source path")
        url = f"https://raw.githubusercontent.com/ekiwi/rtl-repair/{revision}/{path.as_posix()}"
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read(64 * 1024 * 1024 + 1)
        if len(data) > 64 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("Pinned research source hash mismatch")
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch, manifest["files"]))
    print({"fetched_and_verified": len(manifest["files"]), "commit": revision, "source_scripts_executed": False})


if __name__ == "__main__":
    main()
