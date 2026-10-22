"""Command implementations for `eval select` and `eval retrieval --hyde` (CP5).

Kept out of `__main__` so the argument parser stays small. All three evaluations:
- take the LLM only through `llm.factory.make_client` (loopback endpoint rule, disk cache);
- refuse to write anything when the evidence is empty or differs from the committed case list;
- write compact result JSON (no prompts, no raw responses, no hypothetical texts).
"""

import json
import sys
from pathlib import Path
from typing import Any

from vulntrace.eval import evidence_gate
from vulntrace.eval import retrieval as er
from vulntrace.llm import factory, hyde, models_config, prompts
from vulntrace.llm.select import SELECTION_SETTINGS as select_settings
from vulntrace.models.llm import DEFAULT_BASE_URL, EndpointError
from vulntrace.retrieval import fixed

EXIT_OK, EXIT_INVALID_INPUT = 0, 2
DEFAULT_OUT = "results/cp5"


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _progress(i: int, n: int, what: str) -> None:
    if i == 1 or i % 10 == 0 or i == n:
        _log(f"  {i}/{n} {what}")


def model_block(client, alias: str, dry_run: bool) -> dict[str, Any]:
    m = models_config.resolve(alias)
    return {**client.info(), "alias": m["alias"], "ollama_tag": m["ollama_tag"], "params": m["params"],
            "quantization": m["quantization"], "cutoff": m["cutoff"], "cutoff_source": m["cutoff_source"],
            "dry_run": dry_run}


def _client(args):
    cache = Path(args.llm_cache) if args.llm_cache else Path("data") / "llm_cache"
    model = models_config.FAKE_MODEL if args.dry_run else args.model
    return factory.make_client(model, args.llm_url or DEFAULT_BASE_URL, cache), model


def _out_dir(args) -> Path:
    return Path(args.out) if args.out else Path(DEFAULT_OUT)


def retriever_config(dry_run: bool) -> tuple[er.Config, er.Config | None, fixed.FixedRetriever]:
    """The fixed retriever (and the BM25 secondary row) from the config file. `--dry-run` swaps the
    embedder alias for the fake; nothing else about the file can be overridden."""
    f = fixed.load()
    name = f.config.replace("bge-small", "fake") if dry_run else f.config
    sec = er.parse_config(f.secondary_config) if f.secondary_config else None
    return er.parse_config(name), sec, f


def cmd_select(args, argv, load_d4_harness) -> int:
    from vulntrace.dataset import build as dataset_build
    from vulntrace.dataset import datasets
    from vulntrace.eval import select_eval

    try:
        client, model = _client(args)
    except EndpointError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    out = _out_dir(args)
    env = er.environment(argv)
    alias = models_config.resolve(model)["alias"]
    if args.mode == "fix":
        case_list_path = Path(args.cases) if args.cases else dataset_build.RESULTS_DATASETS_DIR / "D1_cases.json"
        case_list = json.loads(case_list_path.read_text(encoding="utf-8"))
        data_dir = Path(args.data_dir) if args.data_dir else dataset_build.DATA_DIR
        statuses, n_cand = evidence_gate.evidence_statuses(case_list, data_dir, "fix_evidence")
        try:
            evidence_gate.require_valid_evidence(case_list, statuses, n_cand)
        except evidence_gate.EvidenceGateError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_INVALID_INPUT
        cases, _ = datasets.load_all_cases(Path(args.cache) if args.cache else None)
        evidence = {}
        for e in case_list["cases"]:
            p = data_dir / "fix_evidence" / f"{e['id']}.json"
            if p.is_file():
                evidence[e["id"]] = json.loads(p.read_text(encoding="utf-8"))
        _log(f"E1 on {len(evidence)} D1 cases with model {client.model_id}")
        doc = select_eval.run_e1(case_list, {c["id"]: c for c in cases}, evidence, client, _progress)
        doc["prompt"] = {"version": prompts.FIX_PROMPT, "sha256": prompts.template_sha256(
            prompts.SYSTEM_PROMPT, prompts.FIX_PROMPT, prompts.RETRY_PROMPT)}
        path = out / f"select_fix__{alias}.json"
    else:
        try:
            ev_cases, ranges, notes, harness = load_d4_harness(args)
        except er.HarnessError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_INVALID_INPUT
        cfg, _sec, f = retriever_config(args.dry_run)
        k = args.k or f.default_k
        _log(f"S1 on {len(ev_cases)} D4 cases, retriever {cfg.name} [{f.variant}], k={k}, model {client.model_id}")
        doc = select_eval.run_s1(harness, cfg, f.variant, k, client, _progress)
        doc["prompt"] = {"version": prompts.TOPK_PROMPT, "sha256": prompts.template_sha256(
            prompts.SYSTEM_PROMPT, prompts.TOPK_PROMPT, prompts.RETRY_PROMPT)}
        doc["embedding_model"] = harness.embedder(cfg.embedder).info() if cfg.embedder else None
        path = out / f"select_release__{alias}__k{k}.json"
    doc["model"] = model_block(client, model, args.dry_run)
    doc["settings"] = select_settings.as_dict()
    doc["environment"] = er.environment(argv, base=env)
    if doc["counts"]["asked"] == 0:
        print("error: the model was asked nothing (0 cases with candidates); refusing to write", file=sys.stderr)
        return EXIT_INVALID_INPUT
    er.write_json(path, doc)
    c = doc["counts"]
    print(f"{doc['experiment']} [{alias}]: {c['asked']} asked, {c['valid']} valid, {c['invalid']} INVALID, "
          f"{c['error']} errors, {c['abstain']} abstained, {c['retried']} retried; {c['input_tokens']} in / "
          f"{c['output_tokens']} out tokens; cache hits {c['cached_calls']}/{c['calls']} -> {path}")
    return EXIT_OK


def cmd_hyde(args, argv, load_d4_harness) -> int:
    from vulntrace.eval import hyde_eval
    from vulntrace.retrieval import chunking

    bad = [v for v in args.hyde if v not in hyde.HYDE_VARIANTS]
    if bad:
        print(f"error: unknown HyDE variant(s) {bad}; expected {list(hyde.HYDE_VARIANTS)}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    if args.config:
        print("error: --hyde uses the fixed retriever from retrieval/fixed_retriever.json; do not pass --config",
              file=sys.stderr)
        return EXIT_INVALID_INPUT
    try:
        client, model = _client(args)
        ev_cases, ranges, notes, harness = load_d4_harness(args)
    except (EndpointError, er.HarnessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    cfg, sec, f = retriever_config(args.dry_run)
    if f.variant not in chunking.VARIANTS:
        print(f"error: fixed retriever variant {f.variant!r} unknown", file=sys.stderr)
        return EXIT_INVALID_INPUT
    configs = [cfg] + ([sec] if sec else [])
    alias = models_config.resolve(model)["alias"]
    out = _out_dir(args) / f"hyde__{alias}"
    env = er.environment(argv)
    _log(f"HyDE generation for {len(ev_cases)} D4 cases with {client.model_id}")
    hyps = hyde_eval.generate_all(client, ev_cases, _progress)
    runs = hyde_eval.run_hyde(harness, configs, f.variant, args.hyde, hyps)
    cases_doc = er.cases_document(ev_cases, ranges, notes)
    meta = hyde_eval.hyde_meta(client, ev_cases, hyps)
    meta["model"] = model_block(client, model, args.dry_run)
    if meta["counts"]["cases"] == 0 or all(not r["rows"] for r in runs):
        print("error: no cases or empty runs; refusing to write", file=sys.stderr)
        return EXIT_INVALID_INPUT
    er.write_json(out / "cases.json", cases_doc)
    er.write_json(out / "hyde_meta.json", {**meta, "retriever": {"config": cfg.name, "secondary": sec.name if sec else None,
                                                                 "variant": f.variant}})
    from vulntrace.eval.retrieval_report import Summaries

    for run in runs:
        run["environment"] = er.environment(argv, base=env)
        run["dry_run"] = args.dry_run
        name = f"{run['config'].replace(':', '_')}__hyde-{run['hyde'].replace('+', '-')}.json"
        p = er.write_json(out / "runs" / name, run)
        sm = Summaries(cases_doc, [run]).summary(0)
        print(f"{run['config']} + {run['hyde']}: R@1={sm['recall@1']['mean']:.3f} R@10={sm['recall@10']['mean']:.3f} "
              f"MRR={sm['mrr']['mean']:.3f} (n={sm['mrr']['n']}) -> {p}", flush=True)
    c = meta["counts"]
    print(f"HyDE generation: {c['cases']} cases, {c['empty']} empty, {c['truncated']} truncated, {c['errors']} errors")
    return EXIT_OK
