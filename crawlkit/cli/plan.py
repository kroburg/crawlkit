"""ck-plan — turn a work-list and a prompt document into dispatchable prompts.

Nothing here talks to a model. The output is text on disk, which is the point:
a fanout composed by a script from a versioned document is reproducible, and a
regression in it shows up as a diff rather than as a bad harvest three days
later.

Every emitted prompt carries a machine-readable item marker, and every run
writes a manifest recording which prompt version and which document produced
it — so a later recovery knows what it is looking at, and a later argument
about what the agents were asked has an answer.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from crawlkit.agents import emit, prompt, version, worklist
from crawlkit.cli import _common
from crawlkit.exits import Exit

KNOWN_PLACEHOLDERS = {
    "item_id",
    "item_title",
    "source_url",
    "schema_block",
    "today",
    "run_id",
}


def load_done(path):
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_prompts(document, schema_block, items, today, run):
    body = prompt.slice_canonical(document, source="prompt document")
    prompt.validate_template(body, KNOWN_PLACEHOLDERS, source="prompt document")

    out = []
    for item in items:
        values = {
            "item_id": item["id"],
            "item_title": item.get("title", item["id"]),
            "source_url": item.get("url", ""),
            "schema_block": schema_block,
            "today": today,
            "run_id": run,
        }
        out.append((item["id"], prompt.compose(body, values, known=KNOWN_PLACEHOLDERS)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--worklist", required=True, help="JSON array of {id, title, url}")
    ap.add_argument("--prompt", required=True, help="markdown document with BEGIN/END anchors")
    ap.add_argument("--schema", help="markdown document to lift the schema block from")
    ap.add_argument("--schema-heading", default="Record schema")
    ap.add_argument("--done", help="JSON map of id -> status, to skip finished work")
    ap.add_argument("--out", help="write one prompt file per item into this directory")
    ap.add_argument("--label", default="harvest", help="run label, used in the run id")
    _common.add_selection_arguments(ap)
    args = ap.parse_args(argv)

    document = Path(args.prompt).read_text(encoding="utf-8")

    # A prompt is an interface. Refusing to emit against an undocumented
    # version is what makes "which contract did this fanout run against?"
    # answerable later.
    try:
        number, dated = version.version_of(document, source=args.prompt)
        version.check_protocol(document, source=args.prompt)
    except version.VersionError as exc:
        return _fail(str(exc))

    schema_block = ""
    if args.schema:
        schema_text = Path(args.schema).read_text(encoding="utf-8")
        try:
            schema_block = prompt.lift_block(schema_text, args.schema_heading, source=args.schema)
        except prompt.PromptError as exc:
            return _fail(str(exc))

    items = worklist.Worklist.load(args.worklist)
    if args.only:
        picked = items.get(args.only)
        if picked is None:
            return _fail(f"{args.only!r} is not in the work-list")
        items = worklist.Worklist([picked], label=items.label)
    else:
        items = worklist.select(list(items), load_done(args.done), reverify=args.reverify)

    if args.dry_run:
        sys.stdout.write(emit.dry_run(items))
        return int(Exit.OK)

    if not len(items):
        print("nothing to dispatch: every item is already done", file=sys.stderr)
        return int(Exit.OK)

    from datetime import date

    today = date.today().isoformat()
    run = emit.run_id(args.label)
    prompts = build_prompts(document, schema_block, list(items), today, run)

    missing = version.guard_phrases_present(prompts[0][1], _guard_phrases(document))
    if missing:
        return _fail(f"the emitted prompt lost drift guards: {missing}")

    if args.out:
        directory = Path(args.out)
        directory.mkdir(parents=True, exist_ok=True)
        for item_id, text in prompts:
            (directory / f"{item_id}.md").write_text(emit.block(text, item_id, run), "utf-8")
        manifest = {
            "run": run,
            "prompt_document": str(args.prompt),
            "prompt_version": number,
            "prompt_dated": dated,
            "document_sha256": hashlib.sha256(document.encode()).hexdigest(),
            "items": [item_id for item_id, _ in prompts],
        }
        (directory / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", "utf-8"
        )
        print(f"{len(prompts)} prompts -> {directory}  (run {run})", file=sys.stderr)
    else:
        sys.stdout.write(emit.emit(prompts, run=run))

    return int(Exit.OK)


def _guard_phrases(document):
    """The bulleted phrases under the document's own drift-guard heading."""
    phrases = []
    inside = False
    for line in document.splitlines():
        if line.startswith("## "):
            inside = line.strip().lower().startswith("## drift guard")
            continue
        if inside and line.strip().startswith("- `"):
            phrases.append(line.strip()[3:].rstrip("`"))
    return phrases


def _fail(message):
    print(message, file=sys.stderr)
    return int(Exit.ERROR)


if __name__ == "__main__":
    raise SystemExit(main())
