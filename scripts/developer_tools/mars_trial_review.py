"""Read saved Remis API artifacts and create review documents, never translations."""
import argparse
import csv
import dataclasses
import html
import json
from pathlib import Path

from scripts.core.surviving_mars_csv import compare_newlines, compare_tags


def read_json(root, name):
    return json.loads((root / name).read_text(encoding="utf-8"))


def review_rows(root, reference, count=100):
    source = read_json(root, f"{count}-source-artifact.json")
    manifest = read_json(root, "manifest.json")
    collection = read_json(root, "100-collection.json" if count == 100 else "40-collection-artifact.json")
    requests = read_json(root, f"{count}-requests-artifact.json")
    remote = read_json(root, "100-native-completed-response.json" if count == 100 else "40-remote-artifact.json")
    groups = {item["custom_id"]: item for item in requests}
    candidates, ownership = {}, {}
    for result in remote["results"]:
        group = groups[result["custom_id"]]
        body = result["response"]["body"]
        parsed = json.loads(body["choices"][0]["message"]["content"])["translations"]
        assert set(parsed) == set(group["entry_ids"])
        assert not set(candidates).intersection(parsed)
        candidates.update(parsed)
        ownership.update({entry_id: result["custom_id"] for entry_id in parsed})
    selected = {item["source_id"]: item for item in manifest["sample_100"]}
    with reference.open(encoding="utf-8-sig", newline="") as stream:
        references = {row[0]: row for row in csv.reader(stream) if len(row) >= 3}
    rows = []
    for file in source["files"]:
        for entry in file["entries"]:
            entry_id, key = entry["id"], entry["key"]
            translated = candidates[entry_id]
            tags = compare_tags(entry["source"], translated)
            newlines = compare_newlines(entry["source"], translated)
            ref = references.get(key)
            ref_matches = bool(ref and ref[1] == entry["source"])
            rows.append({
                "entry_id": entry_id, "source_id": key,
                "category": selected[key]["category"],
                "length_bucket": selected[key]["length_bucket"],
                "context": entry["context"], "source": entry["source"],
                "official_sc": ref[2] if ref_matches else None,
                "official_sc_source_matches": ref_matches,
                "translation": translated,
                "individual_integrity_pass": not tags.is_mismatch and not newlines.is_mismatch,
                "tag_delta": dataclasses.asdict(tags),
                "newline_delta": dataclasses.asdict(newlines),
                "collector_accepted": entry_id in collection["translations"],
                "custom_id": ownership[entry_id],
                "included_in_batch_40": key in {item["source_id"] for item in manifest["batch_40"]},
                "language_review_status": "pending",
            })
    assert len(rows) == len(candidates) == count
    assert {row["entry_id"] for row in rows} == set(candidates)
    return rows, remote["usage"], collection["diagnostics"]


def readable(value):
    return (value or "").replace("\\n", "\n")


def write_review(root, rows, usage, diagnostics, count=100):
    integrity_pass = sum(row["individual_integrity_pass"] for row in rows)
    accepted = sum(row["collector_accepted"] for row in rows)
    mode = "普通" if count == 100 else "Batch"
    if count == 40:
        normal = {row["source_id"]: row for row in read_json(root, "100-review.json")["rows"]}
        for row in rows:
            original = normal[row["source_id"]]
            assert original["source"] == row["source"]
            row["ordinary_translation"] = original["translation"]
            row["ordinary_integrity_pass"] = original["individual_integrity_pass"]
    report = {"schema": "mars-trial-review/1", "model": "gpt-6-luna",
              "reasoning": {"mode": "pro", "effort": "medium"},
              "term_release_id": "terms_2b0191f02045f3a5f82cbeab",
              "usage": usage, "diagnostics": diagnostics, "rows": rows}
    (root / f"{count}-review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    intro = [f"# Luna Pro 原生接口：{count} 条{mode}试译审阅", "",
             f"全部 {count} 条均返回候选译文，覆盖科技、事件、教程、百科和标签。",
             f"{integrity_pass} 条独立标签/换行检查通过；{count-integrity_pass} 条失败。按十条请求整组收集，{accepted} 条已接受。",
             "技术检查通过不等于语言质量通过。语言和机制审阅均待我们共同检查。没有自动付费重试或修饰模型答案。",
             "官方简中仅供事后对照，未作为标准答案发送；只有 ID 与英文原文同时匹配才展示。",
             "显示时把字面量 \\n 展开为换行；100-review.json 与原始 API 快照保留未经修改的字符串。", "",
             f"输入 {usage['input_tokens']:,} tokens（缓存 {usage['cached_input_tokens']:,}）；输出 {usage['output_tokens']:,} tokens（已包含思考 {usage['reasoning_tokens']:,}）。", ""]
    markdown = list(intro)
    cards = []
    labels = {"technology": "科技", "events": "事件", "tutorial": "教程", "encyclopedia": "百科", "labels": "标签"}
    for index, row in enumerate(rows, 1):
        status = "独立技术检查通过" if row["individual_integrity_pass"] else "标签遗漏：待修正"
        accepted = "已收集" if row["collector_accepted"] else "整组暂扣"
        title = f"{index:03d} · {labels.get(row['category'], row['category'])} · ID {row['source_id']} · {status} / {accepted}"
        markdown.extend(["## " + title, "", row["context"], "", "英文：", "", readable(row["source"]), "",
                         "官方简中（对照）：", "", readable(row["official_sc"]) or "无匹配来源", "",
                         "Luna Pro 原始译文：", "", readable(row["translation"]), ""])
        if count == 40:
            markdown.extend(["同 ID 普通试译（对照）：", "", readable(row["ordinary_translation"]), ""])
        if not row["individual_integrity_pass"]:
            markdown.extend(["技术诊断：", "", "```json", json.dumps(row["tag_delta"], ensure_ascii=False, indent=2), "```", ""])
        fields = [("英文原文", "source"), ("官方简中 · 事后对照", "official_sc"), (f"Luna Pro {mode} · 原始译文", "translation")]
        if count == 40:
            fields.append(("同 ID 普通试译 · 对照", "ordinary_translation"))
        columns = "".join(f'<div><h3>{label}</h3><pre>{html.escape(readable(row[field]) or "无匹配来源")}</pre></div>' for label, field in fields)
        search = html.escape(" ".join(str(row[field] or "") for field in ["source_id", "context", "source", "translation", "official_sc"]), quote=True)
        cards.append(f'<article data-category="{row["category"]}" data-issue="{str(not row["individual_integrity_pass"]).lower()}" data-search="{search}"><h2>{html.escape(title)}</h2><p class="context">{html.escape(row["context"])}</p><div class="columns">{columns}</div></article>')
    (root / f"{count}-试译逐条审阅.zh-CN.md").write_text("\n".join(markdown), encoding="utf-8")
    options = '<option value="">全部类别</option>' + "".join(f'<option value="{key}">{label}</option>' for key, label in labels.items())
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Remis · Luna Pro REVIEW_TITLE</title>
<style>body{margin:0;background:#f4f6fa;color:#172338;font:16px/1.65 system-ui,"Microsoft YaHei",sans-serif}header,main{max-width:1560px;margin:auto;padding:24px}h1{font-size:28px;margin:0 0 10px}header p{max-width:1100px}nav{display:flex;gap:12px;align-items:center;flex-wrap:wrap;padding:14px;background:white;border:1px solid #dce3ee;border-radius:10px;position:sticky;top:0;z-index:1}input,select{font:inherit;padding:7px;border:1px solid #bac6d8;border-radius:5px}input[type=search]{min-width:320px}article{background:white;border:1px solid #dce3ee;border-radius:12px;margin:22px 0;padding:20px}h2{font-size:18px;margin:0}h3{font-size:14px;color:#52617a}article[data-issue=true]{border:2px solid #cb671d}.context{color:#66768e;font-size:13px;overflow-wrap:anywhere}.columns{display:grid;grid-template-columns:repeat(COLUMN_COUNT,minmax(0,1fr));gap:24px}pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere;margin:0}#count{margin-left:auto;color:#52617a}[hidden]{display:none}@media(max-width:1000px){.columns{grid-template-columns:1fr}input[type=search]{min-width:180px}}</style>
<header><h1>Luna Pro · REVIEW_TITLE</h1><p>原生 OpenAI / gpt-6-luna / Pro medium · 词典 v0.1.4。REVIEW_SUMMARY<strong>语言质量尚待共同审阅。</strong></p><p>官方简中只在来源匹配时供事后对照。未修改或付费重试模型输出。页面为独立审阅文件；JSON 和 Remis 的原始响应保留完整记录。</p><nav><input id="query" type="search" placeholder="搜索原文、译文、ID 或语境"><select id="category">OPTIONS</select><label><input id="issues" type="checkbox">仅技术问题</label><span id="count"></span></nav></header><main>CARDS</main>
<script>const q=document.querySelector('#query'),c=document.querySelector('#category'),i=document.querySelector('#issues'),a=[...document.querySelectorAll('article')];function update(){let n=0;const query=q.value.toLowerCase();for(const el of a){const show=(!c.value||el.dataset.category===c.value)&&(!i.checked||el.dataset.issue==='true')&&el.dataset.search.toLowerCase().includes(query);el.hidden=!show;if(show)n++}document.querySelector('#count').textContent=n+' / TOTAL_COUNT 条'}for(const el of [q,c,i])el.addEventListener('input',update);update();</script></html>'''
    summary = f"{count} 条均返回；{integrity_pass} 条独立标签与换行检查通过，{count-integrity_pass} 条失败，{accepted} 条整组收集接受。"
    replacements = {"OPTIONS": options, "CARDS": "\n".join(cards), "REVIEW_TITLE": f"{count} 条{mode}试译审阅",
                    "REVIEW_SUMMARY": summary, "TOTAL_COUNT": str(count), "COLUMN_COUNT": "4" if count == 40 else "3"}
    for token, value in replacements.items():
        document = document.replace(token, value)
    (root / f"{count}-试译审阅.html").write_text(document, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--count", type=int, choices=[100, 40], default=100)
    args = parser.parse_args()
    rows, usage, diagnostics = review_rows(args.root, args.reference, args.count)
    write_review(args.root, rows, usage, diagnostics, args.count)
    print(json.dumps({"rows": len(rows), "individual_integrity_pass": sum(row["individual_integrity_pass"] for row in rows),
                      "collector_accepted": sum(row["collector_accepted"] for row in rows),
                      "official_sc_matches": sum(row["official_sc_source_matches"] for row in rows)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
