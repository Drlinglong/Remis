"""Package reviewed static glossaries beside every desktop release.

Builds consume repository assets only: no service, user database, model call,
or provider configuration is needed. JSON remains sense-aware and CSV is a
readable companion, never a global replacement table.
"""
import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path


RESOURCE_PATH = Path("assets/release_glossaries/surviving_mars")
JSON_FILES = ("surviving-mars.en-zh-CN.json", "surviving-mars.en-zh-CN-zh-TW.json")
REQUIRED_FILES = {*JSON_FILES, "README.zh-CN.md", "SOURCES.json"}


def read_resources(project_root):
    root = Path(project_root) / RESOURCE_PATH
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "remis-release-glossaries/1":
        raise ValueError("Unsupported glossary resource manifest")
    if set(manifest["files"]) != REQUIRED_FILES:
        raise ValueError("Release glossary file allowlist differs from the manifest")
    contents = {}
    for name, digest in manifest["files"].items():
        content = (root / name).read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError(f"Release glossary hash mismatch: {name}")
        contents[name] = content
    locales = set()
    for name in JSON_FILES:
        document = json.loads(contents[name].decode("utf-8"))
        if document.get("schema_version") != "remis-glossary-distribution/1":
            raise ValueError(f"Unsupported glossary snapshot: {name}")
        payload, snapshot = document["import_payload"], document["snapshot"]
        if payload["game_id"] != "surviving_mars" or payload["approved"] is not False:
            raise ValueError(f"Invalid glossary identity / import authorization: {name}")
        terms = payload["terms"]
        if not terms or len(terms) != snapshot["eligible_count"]:
            raise ValueError(f"Release glossary count mismatch: {name}")
        identities = [term["concept_id"] for term in terms]
        if len(identities) != len(set(identities)):
            raise ValueError(f"Duplicate glossary concepts: {name}")
        if any(not term["source"].strip() or not term["translation"].strip()
               or term["review_state"] not in {"candidate", "reviewed", "approved"} for term in terms):
            raise ValueError(f"Invalid / pending glossary terms: {name}")
        locales.add(payload["locale"])
    if locales != {"zh-CN", "zh-TW"}:
        raise ValueError("Both Simplified and Traditional Chinese snapshots are required")
    return manifest, contents


def csv_companion(document):
    stream = io.StringIO(newline="")
    fields = ("source_id", "concept_id", "en", "zh-CN", "zh-TW", "aliases",
              "context_keys", "sense", "review_state", "confidence")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    payload = document["import_payload"]
    for term in payload["terms"]:
        translations = {**term["reference_translations"], "en": term["source"],
                        payload["locale"]: term["translation"]}
        row = {field: term.get(field, "") for field in fields}
        row.update({locale: translations.get(locale, "") for locale in ("en", "zh-CN", "zh-TW")})
        row.update({field: json.dumps(term[field], ensure_ascii=False) for field in ("aliases", "context_keys")})
        writer.writerow(row)
    return stream.getvalue().encode("utf-8-sig")


def package_glossaries(project_root, output_dir, version):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,99}", version):
        raise ValueError("Invalid release version")
    manifest, contents = read_resources(project_root)
    manifest = {**manifest, "remis_release_version": version}
    for name in JSON_FILES:
        contents[name.removesuffix(".json") + ".csv"] = csv_companion(json.loads(contents[name].decode("utf-8")))
    manifest["files"] = {name: hashlib.sha256(content).hexdigest() for name, content in sorted(contents.items())}
    contents["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, content in sorted(contents.items()):
            member = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = 0o100644 << 16
            archive.writestr(member, content)
    output = Path(output_dir) / f"Remis-SurvivingMars-Glossary_{version}.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    data = stream.getvalue()
    if output.exists() and output.read_bytes() != data:
        raise FileExistsError(f"Different glossary bundle already exists: {output}")
    output.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    output.with_suffix(".zip.sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(package_glossaries(Path(__file__).resolve().parents[1], args.output_dir, args.version))


if __name__ == "__main__":
    main()
