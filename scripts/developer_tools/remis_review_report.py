"""Export review artifacts from Remis and render them without another model call."""
import argparse
import html
import json
from pathlib import Path
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("job_id")
    parser.add_argument("output", type=Path)
    parser.add_argument("--base", default="http://127.0.0.1:1456")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    def api(path):
        with urllib.request.urlopen(args.base + path, timeout=120) as response:
            return json.load(response)
    prefix = "/api/agent/localization-reviews/" + args.job_id
    job = api(prefix)
    assert job.get("report_artifact"), "Wait for the persisted report; do not resubmit"
    values = {kind: api(prefix + "/artifacts/" + kind) for kind in ["entries", "requests", "source", "reference", "remote", "report"]}
    values["job"] = job
    for kind, value in values.items():
        (args.output / (kind + ".json")).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    report = values["report"]
    markdown = ["# 模型审阅报告", "", f"覆盖输入 {report['expected_count']} 条；已收到审阅响应 {report['reviewed_count']} 条。",
        "模型未报告问题不代表已认证正确。修改建议由局部编辑在本地重建；原始译文没有覆盖。", "",
        "状态计数：" + json.dumps(report["status_counts"], ensure_ascii=False), "",
        "用量：" + json.dumps(job.get("usage"), ensure_ascii=False), ""]
    cards = []
    for index, entry in enumerate(values["entries"], 1):
        review = report["reviews"].get(entry["id"])
        status = review["status"] if review else "unreviewed"
        heading = f"{index:03d} · ID {entry['key']} · {status}"
        markdown += ["## " + heading, "", "英文：", "", entry["source"], "", "官方参考：", "", entry["reference"] or "无匹配参考",
                     "", "原始候选：", "", entry["candidate"], ""]
        findings = []
        if review:
            for finding in review["findings"]:
                text = f"{finding['severity']} / {finding['confidence']} / {finding['category']}：{finding['explanation']}"
                markdown += [text, ""]
                edits = "; ".join(repr(e["find"]) + " → " + repr(e["replace"]) for e in finding["edits"])
                if edits:
                    markdown += ["局部修改：" + edits, ""]
                findings.append(text + ("；" + edits if edits else ""))
            if review["suggested_translation"] is not None:
                markdown += ["本地重建的建议译文：", "", review["suggested_translation"], "",
                    "建议结构完整性：" + str(review["suggestion_integrity_pass"]), ""]
        fields = [("英文", entry["source"]), ("官方简中参考", entry["reference"] or "无匹配参考"),
                  ("原始译文", entry["candidate"]), ("建议译文 · 本地重建", (review or {}).get("suggested_translation") or "无修改建议")]
        columns = "".join('<section><h3>' + html.escape(label) + '</h3><pre>' + html.escape(value) + '</pre></section>' for label, value in fields)
        notes = "".join('<li>' + html.escape(note) + '</li>' for note in findings)
        search = html.escape(json.dumps(entry, ensure_ascii=False), quote=True)
        cards.append(f'<article data-issue="{str(status != "no_reported_issue").lower()}" data-search="{search}"><h2>{heading}</h2><div class="columns">{columns}</div><ul>{notes}</ul></article>')
    (args.output / "审阅报告.zh-CN.md").write_text("\n".join(markdown), encoding="utf-8")
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Remis 模型审阅</title><style>body{font:16px/1.7 system-ui,"Microsoft YaHei";background:#f3f5f9;color:#172338;margin:0}header,main{max-width:1600px;margin:auto;padding:24px}article{background:white;border:1px solid #d7dfeb;border-radius:12px;padding:22px;margin:22px 0}h2{font-size:18px}h3{font-size:14px}.columns{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:24px}pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere}nav{background:white;padding:12px;display:flex;gap:12px;position:sticky;top:0}[hidden]{display:none}@media(max-width:1000px){.columns{grid-template-columns:1fr}}</style><header><h1>模型审阅 · 稀疏问题与局部修改</h1><p>未报告问题不代表已认证正确；建议译文由程序重建，没有覆盖原始输出。</p><nav><input id="q" placeholder="搜索原文、译文或 ID"><label><input id="only" type="checkbox">只看问题条目</label><span id="count"></span></nav></header><main>CARDS</main><script>const q=document.querySelector('#q'),o=document.querySelector('#only'),a=[...document.querySelectorAll('article')];function run(){let n=0;for(const e of a){const show=(!o.checked||e.dataset.issue==='true')&&e.dataset.search.toLowerCase().includes(q.value.toLowerCase());e.hidden=!show;if(show)n++}document.querySelector('#count').textContent=n+'/'+a.length}q.oninput=o.oninput=run;run();</script></html>'''
    (args.output / "审阅报告.html").write_text(document.replace("CARDS", "\n".join(cards)), encoding="utf-8")
    print(json.dumps({"reviewed": report["reviewed_count"], "statuses": report["status_counts"], "output": str(args.output)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
