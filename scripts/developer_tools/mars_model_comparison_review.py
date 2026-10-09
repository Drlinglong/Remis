"""Archive Remis trial artifacts and render anonymous or revealed comparisons."""
import argparse
import csv
import dataclasses
import html
import json
from pathlib import Path
import secrets
import urllib.request

from scripts.core.surviving_mars_csv import compare_newlines, compare_tags


def load(root, name):
    return json.loads((root / name).read_text(encoding="utf-8"))


def save(root, name, value):
    (root / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def download(root):
    state = load(root, "COMPARISON-STATE.json")
    summaries = {}
    for label, job_id in state["jobs"].items():
        prefix = state["backend"] + "/api/agent/batch-jobs/" + job_id
        with urllib.request.urlopen(prefix, timeout=30) as response:
            job = json.load(response)
        assert job["remote_status"] == "completed", "Wait for terminal state"
        save(root, label + "-latest.json", job)
        for kind in ["source", "requests", "catalog", "remote", "collection"]:
            with urllib.request.urlopen(prefix + "/artifacts/" + kind, timeout=30) as response:
                value = json.load(response)
            save(root, label + "-" + kind + "-artifact.json", value)
        summaries[label] = {key: job.get(key) for key in ["completed_requests", "collection_status", "allowed_actions"]}
    state.update(status="completed", terminal_summaries=summaries)
    save(root, "COMPARISON-STATE.json", state)


def candidates(root, label):
    answers, errors = {}, {}
    remote = load(root, label + "-remote-artifact.json")
    groups = {r["custom_id"]: r for r in load(root, label + "-requests-artifact.json")}
    for result in remote["results"]:
        group = groups[result["custom_id"]]
        try:
            raw = result["response"]["body"]["choices"][0]["message"]["content"]
            parsed = json.loads(raw)["translations"]
            assert set(parsed) == set(group["entry_ids"])
            assert all(isinstance(v, str) and v.strip() for v in parsed.values())
            answers.update(parsed)
        except (KeyError, TypeError, ValueError, AssertionError):
            for entry_id in group["entry_ids"]:
                errors[entry_id] = "request/empty/parser/count failure: inspect retained raw response"
    return answers, errors


def anonymous(root, reference):
    sources = load(root, "sol-source-artifact.json")
    assert sources == load(root, "luna-source-artifact.json")
    manifest = {e["source_id"]: e for e in load(root, "manifest.json")["entries"]}
    with reference.open(encoding="utf-8-sig", newline="") as stream:
        refs = {r[0]: r for r in csv.reader(stream) if len(r) >= 3}
    answers = {label: candidates(root, label) for label in ["sol", "luna"]}
    accepted = {label: load(root, label + "-collection-artifact.json")["translations"] for label in answers}
    mapping_path = root / "unblinding-map.json"
    mapping = load(root, mapping_path.name) if mapping_path.exists() else {}
    rows = []
    for file in sources["files"]:
        for entry in file["entries"]:
            key, entry_id = entry["key"], entry["id"]
            if key not in mapping:
                labels = ["sol", "luna"] if secrets.randbelow(2) else ["luna", "sol"]
                mapping[key] = dict(zip(["A", "B"], labels))
            ref = refs.get(key)
            row = {"source_id": key, "category": manifest[key]["category"], "source": entry["source"],
                   "context": entry["context"], "official_sc": ref[2] if ref and ref[1] == entry["source"] else None}
            for side, label in mapping[key].items():
                text = answers[label][0].get(entry_id)
                tags = compare_tags(entry["source"], text) if text is not None else None
                lines = compare_newlines(entry["source"], text) if text is not None else None
                row[side] = {"translation": text, "failure": answers[label][1].get(entry_id),
                             "integrity_pass": bool(tags and not tags.is_mismatch and not lines.is_mismatch),
                             "collector_accepted": entry_id in accepted[label],
                             "tag_delta": dataclasses.asdict(tags) if tags else None,
                             "newline_delta": dataclasses.asdict(lines) if lines else None}
            rows.append(row)
    assert len(rows) == 40 and len(mapping) == 40
    save(root, "unblinding-map.json", mapping)
    save(root, "anonymous-review.json", {"schema": "mars-anonymous-review/1", "rows": rows})
    write_reports(root, rows, False)


def write_reports(root, rows, revealed):
    title = "40 条模型对照与审阅" if revealed else "40 条匿名 A/B 审阅"
    stem = "40-模型对照与审阅" if revealed else "40-匿名审阅"
    markdown = ["# " + title, "", "同一英文、词典 v0.1.5、上下文与翻译工作流。官方简中仅供事后对照。原始输出未改写。", ""]
    cards = []
    for i, row in enumerate(rows, 1):
        heading = f"{i:03d} · {row['category']} · ID {row['source_id']}"
        markdown += ["## " + heading, "", "语境：" + row["context"], "", "英文：", "", row["source"], ""]
        fields = [("英文", row["source"]), ("官方简中（事后对照）", row.get("official_sc") or "无匹配")]
        markdown += ["官方简中（事后对照）：", "", row.get("official_sc") or "无匹配", ""]
        for side in ["A", "B"]:
            name = row[side].get("model", side)
            text = row[side]["translation"] or row[side]["failure"] or "无回答"
            fields.append((name, text))
            markdown += [name + "：", "", text, "", "技术完整性：" + str(row[side]["integrity_pass"]), ""]
        opinion = row.get("review")
        if opinion:
            notes = f"审阅：{opinion['preference']}；{opinion['reason']}（置信度 {opinion['confidence']}）"
            markdown += [notes, ""]
        else:
            notes = "语言审阅待完成"
        columns = "".join('<section><h3>' + html.escape(label) + '</h3><pre>' + html.escape(text.replace('\\n', '\n')) + '</pre></section>' for label, text in fields)
        search = html.escape(json.dumps(row, ensure_ascii=False), quote=True)
        cards.append(f'<article data-search="{search}" data-category="{row["category"]}"><h2>{heading}</h2><details><summary>英文上下文</summary><pre>{html.escape(row["context"])}</pre></details><div class="columns">{columns}</div><p class="review">{html.escape(notes)}</p></article>')
    (root / (stem + ".zh-CN.md")).write_text("\n".join(markdown), encoding="utf-8")
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TITLE</title><style>body{background:#f3f5f9;color:#172338;font:16px/1.7 system-ui,"Microsoft YaHei";margin:0}header,main{max-width:1600px;margin:auto;padding:24px}h1{font-size:28px}article{background:white;border:1px solid #d7dfeb;border-radius:12px;padding:22px;margin:22px 0}h2{font-size:18px}h3{font-size:14px;color:#52617a}.columns{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:24px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}details{color:#65738c}nav{position:sticky;top:0;background:white;padding:12px;display:flex;gap:12px}input,select{font:inherit;padding:6px}.review{background:#eef3fb;padding:12px}[hidden]{display:none}@media(max-width:1100px){.columns{grid-template-columns:1fr}}</style><header><h1>TITLE</h1><p>同条件 40 条；词典 v0.1.5。完整记录保留原始输出和技术诊断。语言意见为 Codex 初审，供共同复核。</p><nav><input id="q" placeholder="搜索 ID、原文、译文"><select id="c"><option value="">全部</option><option>technology</option><option>events</option><option>tutorial</option><option>encyclopedia</option><option>labels</option></select><span id="count"></span></nav></header><main>CARDS</main><script>const q=document.querySelector('#q'),c=document.querySelector('#c'),a=[...document.querySelectorAll('article')];function run(){let n=0;for(const e of a){const show=(!c.value||c.value===e.dataset.category)&&e.dataset.search.toLowerCase().includes(q.value.toLowerCase());e.hidden=!show;if(show)n++}document.querySelector('#count').textContent=n+'/40'}q.oninput=c.oninput=run;run();</script></html>'''
    (root / (stem + ".html")).write_text(document.replace("TITLE", title).replace("CARDS", "\n".join(cards)), encoding="utf-8")


def reveal(root):
    rows = load(root, "anonymous-review.json")["rows"]
    judgments = load(root, "blind-verdicts.json")
    mapping = load(root, "unblinding-map.json")
    assert set(judgments) == {r["source_id"] for r in rows}, "Review every row before revealing"
    for row in rows:
        review = dict(judgments[row["source_id"]])
        side = review["preference"]
        review["blind_preference"] = side
        review["preference"] = mapping[row["source_id"]].get(side, side)
        row["review"] = review
        for side in ["A", "B"]:
            row[side]["model"] = side + " · " + {"sol": "GPT-6.1 Sol · high", "luna": "Luna Pro · medium"}[mapping[row["source_id"]][side]]
    save(root, "revealed-review.json", {"schema": "mars-model-comparison-review/2", "rows": rows})
    write_reports(root, rows, True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--reveal", action="store_true")
    args = parser.parse_args()
    if args.reveal:
        reveal(args.root)
    else:
        assert args.reference
        download(args.root)
        anonymous(args.root, args.reference)
    print("Comparison reports saved; raw model outputs unchanged.")


if __name__ == "__main__":
    main()
