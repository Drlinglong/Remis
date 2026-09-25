"""RimWorld adapter discovery, mod metadata and language package rendering."""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .contracts import Diagnostic, Discovery, Document, Entry, Resource
from .rimworld_text import parse_rules_strings, parse_strings, render_text, validate_tokens
from .rimworld_xml import language_folder, parse_defs, parse_language_xml, render_xml

FORMAT_RULES_VERSION = "rimworld-1.6-v1"
_V16_DEF_FIELDS = frozenset({
    "ThingDef::labelShort", "ThingDef::labelPlural", "ThingDef::ingestible.ingestCommandString",
    "ThingDef::ingestible.ingestReportString", "ThingDef::ingestible.ingestReportStringEat",
    "ThingDef::chargeNoun", "ThingDef::tools.*.label", "ThingDef::comps.*.gizmoLabel",
    "ThingDef::comps.*.gizmoDesc", "WorkGiverDef::gerund", "WorkGiverDef::verb",
    "RecipeDef::jobString", "HediffDef::stages.*.label", "HediffDef::stages.*.description",
    "ThoughtDef::stages.*.label", "ThoughtDef::stages.*.description",
    "RulePackDef::rulePack.rulesStrings", "RulePackDef::generalRules.rulesStrings",
    "RulePackDef::descriptionMaker.rules.rulesStrings",
})


class RimWorldAdapter:
    id = "rimworld"
    game_id = "rimworld"

    def language_folder(self, language: dict) -> str:
        return language_folder(language)

    def discover(self, root: Path, source_lang: dict,
                 game_version: str | None = None) -> Discovery:
        root = Path(root)
        diagnostics: list[Diagnostic] = []
        if not root.is_dir():
            return Discovery((), (Diagnostic("mod_root_missing", "Mod root does not exist", str(root), "error"),))
        source_folder = self.language_folder(source_lang)
        if game_version is None:
            game_version = _infer_version(root)
            if game_version:
                diagnostics.append(Diagnostic("game_version_inferred", f"Using local folder evidence for {game_version}; confirm the target game version."))
        if game_version is None:
            diagnostics.append(Diagnostic("game_version_unknown", "Game version is unknown; versioned overlay is a candidate set."))
        elif not re.match(r"^1\.6(?:\.|$)", game_version):
            diagnostics.append(Diagnostic("game_version_rules_unverified", f"Known field rules remain enabled for {game_version}; runtime behavior is unverified for this version."))
        selection, load_diags = _effective_roots(root, game_version, source_lang)
        diagnostics.extend(load_diags)
        resources = _collect_resources(root, selection, source_folder, game_version)
        resources, collisions = _deduplicate_resources(resources)
        diagnostics.extend(collisions)
        resources, fallback_count = _apply_language_overrides(self, resources, source_folder)
        diagnostics.extend(_resource_key_diagnostics(self, resources))
        if source_folder.casefold() != "english" and fallback_count:
            diagnostics.append(Diagnostic("source_language_def_fallback", f"{fallback_count} fields fall back to source Defs because {source_folder} has no matching DefInjected value."))
        if not resources:
            diagnostics.append(Diagnostic("no_localization_resources", f"No {source_folder} language files or Defs found under effective mod roots", str(root)))
        diagnostics.extend(_runtime_diagnostics(selection))
        return Discovery(tuple(resources), tuple(diagnostics), {
            "package_id": _package_id(root), "source_language": source_folder,
            "game_version": game_version, "rules_version": FORMAT_RULES_VERSION,
        })

    def parse(self, path: Path, metadata: dict | None = None) -> Document:
        try:
            with Path(path).open("r", encoding="utf-8", newline="") as handle:
                text = handle.read()
        except (OSError, UnicodeError) as exc:
            return Document(Path(path), "", (), {"diagnostics": [Diagnostic("read_failed", str(exc), str(path), "error").as_dict()]})
        return self.parse_text(text, Path(path), metadata)

    def parse_text(self, text: str, path: Path, metadata: dict | None = None) -> Document:
        info = dict(metadata or {})
        kind = info.get("kind") or _resource_kind(path)
        if "relative_output_path" not in info:
            info["relative_output_path"] = _package_relative_from_kind(path, kind)
        if "relative_key_path" not in info and kind == "strings":
            info["relative_key_path"] = _strings_key_path(path)
        if kind == "defs":
            return parse_defs(text, path, info, _def_fields_for(path, info))
        if kind == "strings":
            return parse_strings(text, path, info)
        if kind == "rules_strings":
            return parse_rules_strings(text, path, info)
        if kind in {"keyed", "definjected"}:
            return parse_language_xml(text, path, info)
        return Document(path, text, (), {**info, "kind": "unknown", "diagnostics": [Diagnostic("unknown_format", "Unsupported RimWorld resource path", str(path)).as_dict()]})

    def render(self, document: Document, translations: dict[str, str],
               target_lang: dict) -> dict[str, str]:
        _reject_document_errors(document)
        kind = document.metadata.get("kind")
        if kind in {"keyed", "definjected"}:
            return render_xml(document, translations, target_lang)
        if kind in {"strings", "rules_strings"}:
            result = render_text(document, translations)
            return {_replace_language_path(path, self.language_folder(target_lang)): text for path, text in result.items()}
        if kind == "defs":
            return _render_defs(document, translations, self.language_folder(target_lang))
        return {}

    def package_metadata(self, root: Path, target_lang: dict,
                         game_version: str | None = None) -> dict[str, str]:
        package_id = _package_id(Path(root))
        if not package_id:
            raise ValueError("About/About.xml does not contain a valid packageId")
        lang_name = self.language_folder(target_lang)
        versions = _supported_game_versions(Path(root), game_version)
        version_block = ("  <supportedVersions>\n" + "".join(f"    <li>{item}</li>\n" for item in versions) + "  </supportedVersions>\n") if versions else ""
        about_path = "About/About.xml"
        about = ("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
                 "<ModMetaData>\n"
                 f"  <packageId>{_xml_escape(package_id + '.' + lang_name)}</packageId>\n"
                 f"  <name>{_xml_escape(lang_name)} translation for {_xml_escape(package_id)}</name>\n"
                 "  <author>Remis</author>\n"
                 f"{version_block}"
                 "  <description>Translation package generated from local source files.</description>\n"
                 "  <modDependencies>\n    <li>\n"
                 f"      <packageId>{_xml_escape(package_id)}</packageId>\n"
                 f"      <displayName>{_xml_escape(package_id)}</displayName>\n"
                 "    </li>\n  </modDependencies>\n"
                 "  <loadAfter>\n"
                 f"    <li>{_xml_escape(package_id)}</li>\n"
                 "  </loadAfter>\n</ModMetaData>\n")
        return {about_path: about}

    def validate(self, source: str, target: str) -> list[Diagnostic]:
        return validate_tokens(source, target)


def _resource_kind(path: Path) -> str:
    parts = [part.casefold() for part in path.parts]
    suffix = path.suffix.casefold()
    if "keyed" in parts and suffix == ".xml":
        return "keyed"
    if "definjected" in parts and suffix == ".xml":
        return "definjected"
    if "strings" in parts and suffix == ".txt":
        return "strings"
    if "defs" in parts and suffix == ".xml":
        return "defs"
    return "unknown"


def _collect_resources(root: Path, selection: list[tuple[Path, str]],
                       source_folder: str, game_version: str | None) -> list[Resource]:
    resources: list[Resource] = []
    seen: set[Path] = set()
    for selected_root, condition in selection:
        lang_root = selected_root / "Languages" / source_folder
        if lang_root.exists():
            for path in sorted(lang_root.rglob("*")):
                if path.is_file() and path.suffix.lower() in {".xml", ".txt"}:
                    kind = _resource_kind(path)
                    if kind != "unknown":
                        _add_resource(resources, seen, root, selected_root, path, kind, source_folder, condition, game_version)
        defs_root = selected_root / "Defs"
        if defs_root.exists():
            for path in sorted(defs_root.rglob("*.xml")):
                _add_resource(resources, seen, root, selected_root, path, "defs", source_folder, condition, game_version)
    return resources


def _add_resource(resources: list[Resource], seen: set[Path], root: Path,
                  selected_root: Path, path: Path, kind: str, source_folder: str,
                  condition: str, game_version: str | None) -> None:
    if path in seen:
        return
    seen.add(path)
    relative = _package_relative(root, path)
    output_relative = _package_relative(selected_root, path)
    metadata = {
        "root": str(root), "source_root": str(root), "source_mod_id": _package_id(root), "kind": kind,
        "relative_output_path": output_relative,
        "effective_root": str(selected_root), "condition": condition,
        "rules_version": FORMAT_RULES_VERSION, "game_version": game_version,
    }
    if kind != "defs":
        metadata["source_language"] = source_folder
    resources.append(Resource(path, relative, metadata))


def _apply_language_overrides(adapter: RimWorldAdapter, resources: list[Resource],
                              source_language: str) -> tuple[list[Resource], int]:
    explicit_keys: set[str] = set()
    definition_documents: dict[Path, Document] = {}
    for resource in resources:
        if resource.metadata.get("kind") == "definjected":
            parsed = adapter.parse(resource.path, resource.metadata)
            explicit_keys.update(entry.key for entry in parsed.entries)
        elif resource.metadata.get("kind") == "defs":
            definition_documents[resource.path] = adapter.parse(resource.path, resource.metadata)
    fallback_count = 0
    result: list[Resource] = []
    for resource in resources:
        if resource.metadata.get("kind") != "defs":
            result.append(resource)
            continue
        document = definition_documents[resource.path]
        excluded = {entry.key for entry in document.entries if entry.key in explicit_keys}
        fallback_count += sum(entry.key not in excluded for entry in document.entries)
        metadata = dict(resource.metadata)
        metadata["excluded_keys"] = sorted(excluded)
        metadata["source_override_count"] = len(excluded)
        result.append(Resource(resource.path, resource.relative_path, metadata))
    return result, fallback_count


def _resource_key_diagnostics(adapter: RimWorldAdapter,
                              resources: list[Resource]) -> list[Diagnostic]:
    key_paths: dict[str, str] = {}
    diagnostics: list[Diagnostic] = []
    for resource in resources:
        if resource.metadata.get("kind") not in {"keyed", "definjected", "defs"}:
            continue
        parsed = adapter.parse(resource.path, resource.metadata)
        for entry in parsed.entries:
            previous = key_paths.get(entry.key)
            if previous is not None:
                diagnostics.append(Diagnostic("duplicate_resource_key", f"Localization key {entry.key!r} also occurs in {previous}", str(resource.path), "error"))
            else:
                key_paths[entry.key] = str(resource.path)
    return diagnostics


def _deduplicate_resources(resources: list[Resource]) -> tuple[list[Resource], list[Diagnostic]]:
    destinations: dict[str, Resource] = {}
    diagnostics: list[Diagnostic] = []
    for resource in resources:
        destination = resource.metadata.get("relative_output_path", resource.relative_path)
        if destination in destinations:
            diagnostics.append(Diagnostic("overlay_collision", f"Multiple effective layers provide {destination}; later layer takes precedence", str(resource.path)))
        destinations[destination] = resource
    return list(destinations.values()), diagnostics


def _runtime_diagnostics(selection: list[tuple[Path, str]]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for selected_root, _condition in selection:
        patches = selected_root / "Patches"
        assemblies = selected_root / "Assemblies"
        if patches.is_dir() and any(patches.rglob("*.xml")):
            diagnostics.append(Diagnostic("patch_runtime_unknown", "PatchOperations can alter translatable Defs; offline extraction cannot resolve their runtime results", str(patches)))
        if assemblies.is_dir() and any(assemblies.glob("*.dll")):
            diagnostics.append(Diagnostic("assembly_strings_unavailable", "Compiled assemblies may contain runtime strings that this adapter cannot inspect", str(assemblies)))
    return diagnostics


def _def_fields_for(path: Path, metadata: dict) -> frozenset[str]:
    return _V16_DEF_FIELDS


def _render_defs(document: Document, translations: dict[str, str], language: str) -> dict[str, str]:
    by_type: dict[str, list[Entry]] = {}
    for entry in document.entries:
        if entry.key in translations:
            by_type.setdefault(entry.metadata["def_type"], []).append(entry)
    rendered: dict[str, str] = {}
    source_name = re.sub(r"[^A-Za-z0-9_-]+", "_", document.path.stem) or "Defs"
    identity = str(document.metadata.get("relative_output_path", document.path.name)).replace("\\", "/")
    suffix = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8]
    for def_type, entries in by_type.items():
        lines = ['<?xml version="1.0" encoding="utf-8"?>', "<LanguageData>"]
        for entry in entries:
            tag = entry.metadata["xml_tag"]
            value = entry.metadata.get("grammar_prefix", "") + str(translations[entry.key]) + entry.metadata.get("grammar_suffix", "")
            text = _xml_escape(value)
            lines.append(f"  <{tag}>{text}</{tag}>")
        lines.append("</LanguageData>")
        rendered[f"Languages/{language}/DefInjected/{def_type}/Remis_{source_name}_{suffix}.xml"] = "\n".join(lines) + "\n"
    return rendered


def _effective_roots(root: Path, game_version: str | None,
                     source_lang: dict) -> tuple[list[tuple[Path, str]], list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []
    load_file = root / "LoadFolders.xml"
    if load_file.exists():
        if not game_version:
            diagnostics.append(Diagnostic("loadfolders_version_unknown", "LoadFolders.xml requires a target game version to select a branch", str(load_file)))
            candidates = [(root, "unresolved-loadfolders")]
            candidates.extend((item, f"candidate:{item.relative_to(root).as_posix()}") for item in root.iterdir() if item.is_dir() and re.fullmatch(r"1\.\d+", item.name))
            return candidates, diagnostics
        try:
            text = load_file.read_text(encoding="utf-8-sig")
            if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I):
                raise ValueError("DTD/entity declarations are not supported")
            tree = ET.fromstring(text)
            branch = tree.find(f"v{game_version}")
            if branch is None:
                diagnostics.append(Diagnostic("loadfolders_branch_missing", f"No v{game_version} branch in LoadFolders.xml", str(load_file)))
                return [], diagnostics
            result: list[tuple[Path, str]] = []
            active = set(source_lang.get("active_mods", [])) if isinstance(source_lang, dict) else set()
            for item in branch.findall("li"):
                required = item.get("IfModActive")
                forbidden = item.get("IfModNotActive")
                required_all = item.get("IfModActiveAll")
                if required and not active:
                    diagnostics.append(Diagnostic("loadfolders_condition_unknown", f"Conditional path {item.text!r} needs active mod IDs", str(load_file)))
                    relative = (item.text or "").strip().strip("/")
                    _append_load_path(root, relative, f"unresolved:{relative}", result, diagnostics, load_file)
                    continue
                if required and not (set(required.split(",")) & active):
                    continue
                if forbidden and not active:
                    diagnostics.append(Diagnostic("loadfolders_condition_unknown", f"Conditional path {item.text!r} needs active mod IDs", str(load_file)))
                    relative = (item.text or "").strip().strip("/")
                    _append_load_path(root, relative, f"unresolved:{relative}", result, diagnostics, load_file)
                    continue
                if forbidden and set(forbidden.split(",")) & active:
                    continue
                if required_all and not active:
                    diagnostics.append(Diagnostic("loadfolders_condition_unknown", f"Conditional path {item.text!r} needs active mod IDs", str(load_file)))
                    relative = (item.text or "").strip().strip("/")
                    _append_load_path(root, relative, f"unresolved:{relative}", result, diagnostics, load_file)
                    continue
                if required_all and not set(required_all.split(",")).issubset(active):
                    continue
                relative = (item.text or "").strip().strip("/")
                _append_load_path(root, relative, relative or "/", result, diagnostics, load_file)
            return result, diagnostics
        except (ET.ParseError, OSError, ValueError) as exc:
            diagnostics.append(Diagnostic("loadfolders_invalid", str(exc), str(load_file), "error"))
            return [], diagnostics
    roots: list[tuple[Path, str]] = [(root, "/")]
    if (root / "Common").is_dir():
        roots.append((root / "Common", "Common"))
    version_dirs = []
    for child in root.iterdir():
        if child.is_dir() and re.fullmatch(r"1\.\d+", child.name):
            version_dirs.append(child)
    if version_dirs:
        if game_version:
            requested = tuple(map(int, game_version.split(".")))
            candidates = [directory for directory in version_dirs if tuple(map(int, directory.name.split("."))) <= requested]
            if candidates:
                chosen = max(candidates, key=lambda item: tuple(map(int, item.name.split("."))))
                roots.append((chosen, chosen.name))
        else:
            diagnostics.append(Diagnostic("versioned_overlay_unknown", "Versioned folders cannot be resolved without game version; versioned resources are returned as candidates."))
            roots.extend((directory, f"candidate:{directory.name}") for directory in version_dirs)
    return roots, diagnostics


def _package_id(root: Path) -> str | None:
    path = root / "About" / "About.xml"
    try:
        text = path.read_text(encoding="utf-8-sig")
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I):
            return None
        element = ET.fromstring(text).find("packageId")
        value = element.text.strip() if element is not None and element.text else ""
        return value if re.fullmatch(r"[A-Za-z0-9_.-]+", value) else None
    except (OSError, UnicodeError, ET.ParseError):
        return None


def _supported_game_versions(root: Path, game_version: str | None) -> list[str]:
    if game_version:
        match = re.match(r"1\.\d+", game_version)
        return [match.group(0)] if match else []
    about_path = root / "About" / "About.xml"
    try:
        text = about_path.read_text(encoding="utf-8-sig")
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I):
            return []
        about = ET.fromstring(text)
        supported = about.find("supportedVersions")
        return [node.text.strip() for node in supported.findall("li")
                if node.text and re.fullmatch(r"1\.\d+", node.text.strip())] if supported is not None else []
    except (OSError, UnicodeError, ET.ParseError):
        return []


def _reject_document_errors(document: Document) -> None:
    diagnostics = document.metadata.get("diagnostics", [])
    if any(item.get("severity") == "error" for item in diagnostics if isinstance(item, dict)):
        raise ValueError(f"Cannot render invalid RimWorld document: {document.path}")


def _package_relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _package_relative_from_kind(path: Path, kind: str) -> str:
    parts = list(path.parts)
    target = "Languages" if kind in {"keyed", "definjected", "strings"} else "Defs"
    for index, part in enumerate(parts):
        if part.casefold() == target.casefold():
            return Path(*parts[index:]).as_posix()
    return path.name


def _strings_key_path(path: Path) -> str:
    parts = list(path.parts)
    for index, part in enumerate(parts):
        if part.casefold() == "strings":
            return Path(*parts[index + 1:]).as_posix()
    return path.name


def _infer_version(root: Path) -> str | None:
    candidates = [item.name for item in root.iterdir() if item.is_dir() and re.fullmatch(r"1\.\d+", item.name)]
    load_file = root / "LoadFolders.xml"
    if load_file.is_file():
        try:
            text = load_file.read_text(encoding="utf-8-sig")
            if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I):
                return max(candidates, key=lambda value: tuple(map(int, value.split(".")))) if candidates else None
            tree = ET.fromstring(text)
            candidates.extend(node.tag[1:] for node in tree if re.fullmatch(r"v1\.\d+", node.tag))
        except (OSError, ET.ParseError):
            return None
    return max(candidates, key=lambda value: tuple(map(int, value.split(".")))) if candidates else None


def _append_load_path(root: Path, relative: str, condition: str,
                      result: list[tuple[Path, str]], diagnostics: list[Diagnostic],
                      load_file: Path) -> None:
    candidate = (root / relative).resolve() if relative else root.resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        diagnostics.append(Diagnostic("loadfolders_path_outside_mod", f"LoadFolders path {relative!r} resolves outside the selected mod", str(load_file), "error"))
        return
    result.append((candidate, condition))


def _replace_language_path(path: str, language: str) -> str:
    return re.sub(r"(^|/)Languages/[^/]+/", rf"\1Languages/{language}/", path, flags=re.I)


def _xml_escape(value: str) -> str:
    from html import escape
    return escape(value, quote=False)
