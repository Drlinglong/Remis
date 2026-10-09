"""Compare zhconvert candidates against retained Remis trials without project writes.

Inputs come from Agent APIs; isolated experiment files are not project outputs.
No model calls, credentials, glossary edits, candidate apply, or deployment.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.parse import urlparse

import requests

from scripts.core.localization_quality_checks import check_quality

CONVERTER_BASE = "https://api.zhconvert.org"
USER_AGENT = "Remis-Localization-Comparison/0.1"


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".pending")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def get(session, url):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def conversion_payload(text):
    # Complete tokens remain visible to the service; do not convert a CSV container.
    protect = sorted(set(re.findall(r"<[^<>]*>", text)) | {r"\n"})
    return {"text": text, "converter": "Taiwan", "modules": "{}",
            "userPreReplace": "", "userPostReplace": "", "userProtectReplace": "\n".join(protect),
            "jpTextConversionStrategy": "none", "jpStyleConversionStrategy": "none",
            "cleanUpText": False, "ensureNewlineAtEof": False, "trimTrailingWhiteSpaces": False,
            "translateTabsToSpaces": -1, "unifyLeadingHyphen": False, "diffEnable": False}


def align_peer(entries, snapshot, collection):
    sources = {e["key"]: e for f in snapshot["files"] for e in f["entries"]}
    translations = collection["translations"]
    aligned = {}
    for entry in entries:
        peer = sources.get(entry["key"])
        if not peer or peer["source"] != entry["source"] or peer["id"] not in translations:
            raise ValueError(f"Peer source/candidate mismatch for {entry['key']}")
        aligned[entry["id"]] = translations[peer["id"]]
    return aligned


def parse_conversion(response):
    if response.get("code") != 0:
        raise ValueError("converter_service_error: " + str(response.get("msg")))
    data = response.get("data", {})
    if data.get("converter") != "Taiwan":
        raise ValueError("converter_mode_mismatch")
    text = data.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty_converter_output")
    return text


def render(root, rows, summary):
    heading = "40 条：繁化姬与原生模型对照" if len(rows) == 40 else "繁化姬与原生模型对照"
    introduction = "官方简中 → 繁化姬 Taiwan；保留转换原样，未做词典替换、人工修改或模型审阅。模型候选来自旧试验，英文与 ID 对齐，但模型原先直接翻英文，两条路线的输入不同。"
    markdown = ["# " + heading, "", introduction, "", "统计：" + json.dumps(summary, ensure_ascii=False), ""]
    cards = []
    for number, row in enumerate(rows, 1):
        title = f"{number:03d} · ID {row['key']}"
        fields = [("英文", row["source"]), ("官方简中 · 转换输入", row["reference"]),
                  ("繁化姬 · Taiwan 原始输出", row.get("converted") or "失败：" + row.get("error", "未完成")),
                  (summary["candidate_label"], row["candidate"]), (summary["peer_label"], row["peer_candidate"])]
        markdown += ["## " + title, "", "语境：" + row.get("context", ""), ""]
        for label, text in fields:
            markdown += [label + "：", "", text, ""]
        checks = {"转换前后技术诊断": row.get("conversion_checks"), "相对英文诊断": row.get("source_checks")}
        markdown += ["规则检查（不是语言认证）：" + json.dumps(checks, ensure_ascii=False), ""]
        columns = "".join('<section><h3>' + html.escape(label) + '</h3><pre>' + html.escape(text.replace(r"\n", "\n")) + '</pre></section>' for label, text in fields)
        search = html.escape(json.dumps(row, ensure_ascii=False), quote=True)
        cards.append(f'<article data-search="{search}"><h2>{html.escape(title)}</h2><p>{html.escape(row.get("context", ""))}</p><div class="columns">{columns}</div><details><summary>规则诊断</summary><pre>{html.escape(json.dumps(checks,ensure_ascii=False,indent=2))}</pre></details></article>')
    (root / "40-繁化姬与模型对照.zh-CN.md").write_text("\n".join(markdown), encoding="utf-8")
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>繁化姬与模型对照</title><style>body{font:16px/1.7 system-ui,"Microsoft YaHei";background:#f3f5f9;color:#172338;margin:0}header,main{max-width:2000px;margin:auto;padding:24px}article{background:white;border:1px solid #d7dfeb;border-radius:12px;padding:22px;margin:22px 0}h2{font-size:18px}h3{font-size:14px}.columns{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:24px}pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere}nav{background:white;padding:12px;position:sticky;top:0}input{font:inherit;padding:8px}[hidden]{display:none}@media(max-width:1200px){.columns{grid-template-columns:1fr 1fr}}@media(max-width:650px){.columns{grid-template-columns:1fr}}</style><header><h1>TITLE</h1><p>INTRO</p><nav><input id="q" placeholder="搜索 ID、原文或译文"><span id="count"></span></nav></header><main>CARDS</main><script>const q=document.querySelector('#q'),a=[...document.querySelectorAll('article')];function run(){let n=0;for(const e of a){e.hidden=!e.dataset.search.toLowerCase().includes(q.value.toLowerCase());if(!e.hidden)n++}document.querySelector('#count').textContent=n+'/'+a.length}q.oninput=run;run();</script></html>'''
    (root / "40-繁化姬与模型对照.html").write_text(document.replace("TITLE", heading).replace("INTRO", html.escape(introduction)).replace("CARDS", "\n".join(cards)), encoding="utf-8")


def run(args):
    if urlparse(args.base).hostname != "127.0.0.1":
        raise ValueError("Remis backend must be localhost")
    if not args.output.is_absolute():
        raise ValueError("Choose an absolute isolated experiment directory")
    root = args.output.resolve()
    forbidden = [Path.cwd() / part for part in ["source_mod", "my_translation", "outputs", ".runtime", "data"]]
    if any(root == p.resolve() or p.resolve() in root.parents for p in forbidden):
        raise ValueError("Do not write an experiment into managed project/runtime storage")
    root.mkdir(parents=True, exist_ok=True)
    (root / "responses").mkdir(exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    base = args.base.rstrip("/") + "/api/agent"
    preflight = get(session, base + "/preflight")
    save(root / "preflight.json", preflight)
    if preflight["status"] != "ready":
        raise ValueError("Remis preflight is not ready")
    print(json.dumps({"release_check": preflight["release_check"]}), flush=True)
    entries = []
    for job_id in args.review_jobs:
        prefix = base + "/localization-reviews/" + job_id
        snapshot = get(session, prefix + "/artifacts/source")
        if snapshot["adapter_id"] != "surviving_mars_csv":
            raise ValueError("This converter trial currently validates Mars references only")
        entries.extend(get(session, prefix + "/artifacts/entries"))
    if len(entries) != args.expected_count or len({e["id"] for e in entries}) != len(entries):
        raise ValueError("Exact input count and unique entry IDs are required")
    if any(not e.get("reference") or not e.get("reference_source_matches") for e in entries):
        raise ValueError("All SC references must match the exact source ID and English")
    peer_prefix = base + "/batch-jobs/" + args.peer_job
    peer_source = get(session, peer_prefix + "/artifacts/source")
    peer_collection = get(session, peer_prefix + "/artifacts/collection")
    aligned = align_peer(entries, peer_source, peer_collection)
    release = get(session, base + "/term-releases/" + args.term_release_id)
    inputs = {"review_jobs": args.review_jobs, "peer_job": args.peer_job, "term_release_id": args.term_release_id, "entries": entries}
    input_hash = fingerprint(inputs)
    previous = root / "INPUTS.json"
    if previous.exists() and fingerprint(json.loads(previous.read_text(encoding="utf-8"))) != input_hash:
        raise ValueError("Experiment input changed; choose a new directory")
    save(previous, inputs)
    save(root / "peer-source.json", peer_source)
    save(root / "peer-collection.json", peer_collection)
    save(root / "term-release.json", release)
    info = get(session, CONVERTER_BASE + "/service-info")
    if info.get("code") != 0 or "Taiwan" not in info.get("data", {}).get("converters", {}):
        raise ValueError("Taiwan converter unavailable")
    save(root / "service-info.json", info)
    rows, requests_sent = [], 0
    for number, entry in enumerate(entries, 1):
        payload = conversion_payload(entry["reference"])
        key = fingerprint({"payload": payload, "build": info["revisions"]["build"]})
        path = root / "responses" / (entry["id"] + ".json")
        if path.exists():
            retained = json.loads(path.read_text(encoding="utf-8"))
            if retained["request_hash"] != key:
                raise ValueError("Settings or converter revision changed; choose a new directory")
        else:
            retained = {"source_id": entry["key"], "entry_id": entry["id"], "request_hash": key, "request": payload}
            save(path, retained)
            try:
                requests_sent += 1
                response = session.post(CONVERTER_BASE + "/convert", json=payload, timeout=45)
                retained["http_status"] = response.status_code
                retained["raw_body"] = response.text
                response.raise_for_status()
                retained["response"] = response.json()
            except (requests.RequestException, ValueError) as error:
                retained["error"] = str(error)
            save(path, retained)
        row = {**entry, "peer_candidate": aligned[entry["id"]], "response_path": str(path)}
        try:
            if retained.get("error"):
                raise ValueError(retained["error"])
            raw = retained["response"]
            if raw["revisions"]["build"] != info["revisions"]["build"]:
                raise ValueError("converter_revision_changed_during_run")
            row["converted"] = parse_conversion(raw)
            row["conversion_checks"] = check_quality(entry["reference"], row["converted"])
            row["source_checks"] = check_quality(entry["source"], row["converted"], release["terms"])
            row["used_modules"] = raw["data"].get("usedModules", [])
        except (KeyError, ValueError, TypeError) as error:
            row["error"] = str(error)
        rows.append(row)
        if number % 10 == 0:
            print(f"Converter results retained: {number}/{len(entries)}", flush=True)
    summary = {"schema": "remis-converter-trial/1", "input_count": len(rows), "converted_count": sum("converted" in r for r in rows),
               "conversion_integrity_errors": sum(any(i["severity"] == "error" for i in r.get("conversion_checks", [])) for r in rows),
               "english_integrity_error_rows": sum(any(i["severity"] == "error" for i in r.get("source_checks", [])) for r in rows),
               "service_revisions": info["revisions"], "input_hash": input_hash, "automatic_apply": False,
               "model_calls": 0, "glossary_applied_to_conversion": False, "term_release_for_diagnostics": args.term_release_id,
               "candidate_label": args.candidate_label, "peer_label": args.peer_label,
               "conversion_requests_this_run": requests_sent, "cached_conversion_results": len(rows) - requests_sent}
    save(root / "comparison.json", {"summary": summary, "rows": rows})
    render(root, rows, summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0 if summary["converted_count"] == len(rows) and summary["conversion_integrity_errors"] == 0 else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:1456")
    parser.add_argument("--review-jobs", nargs="+", required=True)
    parser.add_argument("--peer-job", required=True)
    parser.add_argument("--term-release-id", required=True)
    parser.add_argument("--expected-count", type=int, required=True)
    parser.add_argument("--candidate-label", default="Luna Pro · medium 原始译文")
    parser.add_argument("--peer-label", default="GPT-6.1 Sol · high 原始译文")
    parser.add_argument("--output", type=Path, required=True)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
