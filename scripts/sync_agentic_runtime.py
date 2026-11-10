"""Copy the explicit research-runtime subset, retaining source notices and hashes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sync(source: Path):
    source = source.resolve(strict=True)
    target = ROOT / "vendor" / "agentic"
    paths = ["LICENSE", "ATTRIBUTION.md", "LOCAL_APP.md",
             "local_app/__init__.py", "local_app/engine.py", "local_app/server.py", "local_app/test_journeys.py",
             "local_app/static/index.html", "local_app/static/app.js", "local_app/static/style.css",
             "scripts/cli_contract.py", "scripts/opening_bell.py", "scripts/stop_cost.py"]
    paths.extend(p.relative_to(source).as_posix() for p in sorted((source / "agents").glob("*.md")))
    for skill in sorted((source / "skills").glob("*/SKILL.md")):
        paths.extend((skill.parent / name).relative_to(source).as_posix()
                     for name in ("SKILL.md", "LICENSE", "ATTRIBUTION.md"))
    if len(list((source / "agents").glob("*.md"))) != 7 or len(list((source / "skills").glob("*/SKILL.md"))) != 17:
        raise ValueError("Expected the reviewed seven-role, seventeen-skill source layout.")
    # Validate every source and destination before copying anything.
    for relative in paths:
        src, dst = source / relative, target / relative
        if src.is_symlink() or not src.is_file() or not src.resolve().is_relative_to(source):
            raise ValueError(f"Untrusted or missing source file: {relative}")
        if dst.is_symlink() or not dst.resolve().is_relative_to(target.resolve()):
            raise ValueError(f"Invalid destination: {relative}")
    manifest = {}
    for relative in paths:
        data = (source / relative).read_bytes()
        dst = target / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        manifest[relative] = hashlib.sha256(data).hexdigest()
    (target / "SOURCE_MANIFEST.json").write_text(json.dumps({
        "upstream": "https://github.com/galleonlabs/hypergrok-trading-desk",
        "upstream_instruction_version": "1.7.1",
        "edition": "Unpublished local Agentic derivative with the OpenAI research app and Radar bridge",
        "license": "MIT; see LICENSE and skill-local notices",
        "files": manifest,
    }, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Saved {len(manifest)} explicit runtime files with notices and SHA-256 hashes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    sync(parser.parse_args().source)
