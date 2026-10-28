"""`python -m vulntrace demo build --verdict <file> [--verdict ...] [--dir <dir>] [--out <file>]`."""

import sys
from pathlib import Path

from vulntrace.demo import page
from vulntrace.paths import REPO_ROOT

EXIT_OK, EXIT_INVALID_INPUT = 0, 2
DEFAULT_OUT = REPO_ROOT / "data" / "demo" / "index.html"


def add_parser(sub) -> None:
    dm = sub.add_parser("demo", help="CP7b: the offline demo page")
    dsub = dm.add_subparsers(dest="demo_command", required=True)
    b = dsub.add_parser("build", help="one self-contained static HTML page from verdict JSON files (no server, no network)")
    b.add_argument("--verdict", action="append", default=None, help="a verdict JSON file (repeatable)")
    b.add_argument("--dir", action="append", default=None, help="every *.json verdict file in this directory (repeatable)")
    b.add_argument("--out", default=None, help="output HTML file (default: data/demo/index.html)")


def cmd_build(args) -> int:
    paths = [Path(p) for p in args.verdict or []]
    for d in args.dir or []:
        for p in sorted(Path(d).glob("*.json")):
            if page.is_verdict_file(p):
                paths.append(p)
            else:
                print(f"skipped {p}: not a verdict JSON file", file=sys.stderr)
    if not paths:
        print("invalid input: give --verdict or --dir", file=sys.stderr)
        return EXIT_INVALID_INPUT
    try:
        verdicts = page.load_verdicts(paths)
    except (OSError, ValueError) as exc:
        print(f"invalid input: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    out = Path(args.out) if args.out else DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page.build_page(verdicts), encoding="utf-8")
    print(f"wrote {out} ({len(verdicts)} verdict(s), {out.stat().st_size} bytes)")
    return EXIT_OK
