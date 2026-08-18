#!/usr/bin/env python3
"""Validate skill-local resource declarations in source trees and built ZIPs."""
from __future__ import annotations

import os
import re
import stat
import urllib.parse
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable


RESOURCE_KINDS = ("scripts", "references", "assets")
WINDOWS_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
RESOURCE_MARKER_RE = re.compile(
    r"(?:^|[/\\])(?:scripts|references|assets)(?:[/\\])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MarkdownToken:
    surface: str
    raw: str
    line: int
    column: int
    angle_destination: bool = False


@dataclass(frozen=True)
class ResourceReference:
    plugin_name: str
    skill_name: str
    document: Path
    line: int
    column: int
    surface: str
    raw: str
    resource_path: str
    resource_type: str
    fragment: str | None

    @property
    def zip_member(self) -> str:
        return f"skills/{self.skill_name}/{self.resource_path}"


@dataclass(frozen=True)
class ResourceFinding:
    code: str
    message: str
    plugin_name: str
    skill_name: str | None = None
    document: Path | None = None
    line: int | None = None
    reference: str | None = None

    def format(self) -> str:
        location = self.plugin_name
        if self.skill_name is not None:
            location += f"/{self.skill_name}"
        if self.document is not None:
            location += f":{self.document.as_posix()}"
        if self.line is not None:
            location += f":{self.line}"
        return f"{location}: {self.message}"


class ResourceClosureError(ValueError):
    """A machine-readable packaged-resource closure failure."""

    def __init__(self, finding: ResourceFinding) -> None:
        self.finding = finding
        super().__init__(finding.format())


def _fail(
    code: str,
    message: str,
    *,
    plugin_name: str,
    skill_name: str | None = None,
    document: Path | None = None,
    line: int | None = None,
    reference: str | None = None,
) -> None:
    raise ResourceClosureError(
        ResourceFinding(
            code=code,
            message=message,
            plugin_name=plugin_name,
            skill_name=skill_name,
            document=document,
            line=line,
            reference=reference,
        )
    )


def is_reparse_point(metadata: os.stat_result) -> bool:
    return bool(getattr(metadata, "st_file_attributes", 0) & WINDOWS_REPARSE_POINT)


def _inspect(path: Path, *, plugin_name: str, skill_name: str | None = None) -> os.stat_result:
    try:
        return path.lstat()
    except OSError as exc:
        _fail(
            "inspect_error",
            f"cannot inspect packaged resource path {path}: {exc}",
            plugin_name=plugin_name,
            skill_name=skill_name,
        )


def _reject_link_or_reparse(
    path: Path,
    metadata: os.stat_result,
    *,
    plugin_name: str,
    skill_name: str | None = None,
) -> None:
    if stat.S_ISLNK(metadata.st_mode):
        _fail(
            "linked_resource",
            f"packaged resource paths may not use symlinks: {path}",
            plugin_name=plugin_name,
            skill_name=skill_name,
        )
    if is_reparse_point(metadata):
        _fail(
            "reparse_resource",
            f"packaged resource paths may not use junctions or reparse points: {path}",
            plugin_name=plugin_name,
            skill_name=skill_name,
        )


def _require_real_directory(
    path: Path, *, plugin_name: str, skill_name: str | None = None
) -> Path:
    metadata = _inspect(path, plugin_name=plugin_name, skill_name=skill_name)
    _reject_link_or_reparse(
        path,
        metadata,
        plugin_name=plugin_name,
        skill_name=skill_name,
    )
    if not stat.S_ISDIR(metadata.st_mode):
        _fail(
            "not_directory",
            f"packaged resource container is not a directory: {path}",
            plugin_name=plugin_name,
            skill_name=skill_name,
        )
    try:
        return path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        _fail(
            "resolve_error",
            f"cannot resolve packaged resource directory {path}: {exc}",
            plugin_name=plugin_name,
            skill_name=skill_name,
        )


def _scandir(path: Path, *, plugin_name: str, skill_name: str | None = None) -> list[os.DirEntry[str]]:
    try:
        with os.scandir(path) as entries:
            return sorted(entries, key=lambda entry: entry.name)
    except OSError as exc:
        _fail(
            "scan_error",
            f"cannot scan packaged resource directory {path}: {exc}",
            plugin_name=plugin_name,
            skill_name=skill_name,
        )


def _is_escaped(text: str, index: int) -> bool:
    slashes = 0
    index -= 1
    while index >= 0 and text[index] == "\\":
        slashes += 1
        index -= 1
    return bool(slashes % 2)


def _location(text: str, index: int) -> tuple[int, int]:
    line = text.count("\n", 0, index) + 1
    previous = text.rfind("\n", 0, index)
    return line, index - previous


def _mask_fenced_code(text: str) -> str:
    output: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    for line in text.splitlines(keepends=True):
        match = FENCE_RE.match(line)
        if fence_character is None and match:
            run = match.group(1)
            fence_character = run[0]
            fence_length = len(run)
            output.append("".join("\n" if char == "\n" else " " for char in line))
            continue
        if fence_character is not None:
            stripped = line.lstrip(" \t")
            run_length = len(stripped) - len(stripped.lstrip(fence_character))
            closes = (
                len(line) - len(stripped) <= 3
                and run_length >= fence_length
                and not stripped[run_length:].strip()
            )
            output.append("".join("\n" if char == "\n" else " " for char in line))
            if closes:
                fence_character = None
                fence_length = 0
            continue
        output.append(line)
    return "".join(output)


def _inline_code_tokens(text: str) -> tuple[str, list[MarkdownToken]]:
    masked = list(text)
    tokens: list[MarkdownToken] = []
    index = 0
    while index < len(text):
        if text[index] != "`" or _is_escaped(text, index):
            index += 1
            continue
        run_length = 1
        while index + run_length < len(text) and text[index + run_length] == "`":
            run_length += 1
        delimiter = "`" * run_length
        end = text.find(delimiter, index + run_length)
        if end < 0 or "\n" in text[index + run_length : end]:
            index += run_length
            continue
        raw = text[index + run_length : end]
        line, column = _location(text, index)
        tokens.append(MarkdownToken("inline_code", raw, line, column))
        for position in range(index, end + run_length):
            if masked[position] != "\n":
                masked[position] = " "
        index = end + run_length
    return "".join(masked), tokens


def _markdown_link_tokens(text: str) -> list[MarkdownToken]:
    tokens: list[MarkdownToken] = []
    index = 0
    while index < len(text):
        if text[index] != "[" or _is_escaped(text, index):
            index += 1
            continue
        label_end = index + 1
        while label_end < len(text):
            if text[label_end] == "\n":
                break
            if text[label_end] == "]" and not _is_escaped(text, label_end):
                break
            label_end += 1
        if (
            label_end >= len(text)
            or text[label_end] != "]"
            or label_end + 1 >= len(text)
            or text[label_end + 1] != "("
        ):
            index += 1
            continue
        destination_start = label_end + 2
        while destination_start < len(text) and text[destination_start] in " \t":
            destination_start += 1

        destination_end = destination_start
        closing = destination_start
        angle_destination = (
            destination_start < len(text) and text[destination_start] == "<"
        )
        if angle_destination:
            destination_start += 1
            destination_end = destination_start
            while destination_end < len(text):
                character = text[destination_end]
                if character == "\n" or character == "<":
                    break
                if character == ">" and not _is_escaped(text, destination_end):
                    break
                destination_end += 1
            if destination_end >= len(text) or text[destination_end] != ">":
                index += 1
                continue
            closing = destination_end + 1
        else:
            depth = 0
            while destination_end < len(text):
                character = text[destination_end]
                if character == "\n":
                    break
                if character in " \t" and depth == 0:
                    break
                if character == "(" and not _is_escaped(text, destination_end):
                    depth += 1
                elif character == ")" and not _is_escaped(text, destination_end):
                    if depth == 0:
                        break
                    depth -= 1
                destination_end += 1
            if depth:
                index += 1
                continue
            closing = destination_end

        had_separator = closing < len(text) and text[closing] in " \t"
        while closing < len(text) and text[closing] in " \t":
            closing += 1

        if closing < len(text) and text[closing] != ")":
            if not had_separator or text[closing] not in "\"'(":
                index += 1
                continue
            title_opener = text[closing]
            title_closer = ")" if title_opener == "(" else title_opener
            closing += 1
            while closing < len(text):
                if text[closing] == "\n":
                    break
                if text[closing] == title_closer and not _is_escaped(text, closing):
                    break
                closing += 1
            if closing >= len(text) or text[closing] != title_closer:
                index += 1
                continue
            closing += 1
            while closing < len(text) and text[closing] in " \t":
                closing += 1

        if closing >= len(text) or text[closing] != ")":
            index += 1
            continue
        raw = text[destination_start:destination_end]
        line, column = _location(text, index)
        surface = "markdown_image" if index > 0 and text[index - 1] == "!" else "markdown_link"
        tokens.append(
            MarkdownToken(
                surface,
                raw,
                line,
                column,
                angle_destination=angle_destination,
            )
        )
        index = closing + 1
    return tokens


def markdown_tokens(text: str) -> list[MarkdownToken]:
    """Extract deterministic link/image and standalone inline-code tokens."""
    outside_fences = _mask_fenced_code(text)
    outside_inline, inline_tokens = _inline_code_tokens(outside_fences)
    return sorted(
        [*inline_tokens, *_markdown_link_tokens(outside_inline)],
        key=lambda token: (token.line, token.column, token.surface),
    )


def _looks_like_resource(
    raw: str, *, surface: str, angle_destination: bool
) -> bool:
    candidate = raw.strip()
    if not candidate or candidate.startswith("#"):
        return False
    if candidate.startswith("//"):
        return False
    scheme = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", candidate)
    if scheme and not re.match(r"^[A-Za-z]:[/\\]", candidate):
        return False
    if any(marker in candidate for marker in ("*", "[", "]", "<", ">", "${", "{", "}")):
        return False
    if "$" in candidate:
        return False
    if "?" in candidate and surface == "inline_code":
        before_question, _, after_question = candidate.partition("?")
        filename_before_question = before_question.rsplit("/", 1)[-1]
        if (
            "=" not in after_question
            and "&" not in after_question
            and "." not in filename_before_question
            and (not after_question or "." in after_question)
        ):
            return False
    has_literal_space = any(
        character.isspace() and ord(character) >= 32 for character in candidate
    )
    if has_literal_space and not (
        angle_destination and surface in {"markdown_link", "markdown_image"}
    ):
        return False
    without_fragment = candidate.split("#", 1)[0]
    without_query = without_fragment.split("?", 1)[0]
    directory_examples = {f"{kind}/" for kind in RESOURCE_KINDS}
    if without_query.casefold() in directory_examples:
        return False
    decoded = urllib.parse.unquote(without_query)
    return bool(
        RESOURCE_MARKER_RE.search(without_query)
        or RESOURCE_MARKER_RE.search(decoded)
    )


def _normalize_token(
    token: MarkdownToken,
    *,
    plugin_name: str,
    skill_name: str,
    document: Path,
) -> ResourceReference | None:
    raw = token.raw.strip()
    if not _looks_like_resource(
        raw,
        surface=token.surface,
        angle_destination=token.angle_destination,
    ):
        return None

    def invalid(code: str, message: str) -> None:
        _fail(
            code,
            message,
            plugin_name=plugin_name,
            skill_name=skill_name,
            document=document,
            line=token.line,
            reference=raw,
        )

    if any(ord(character) < 32 or ord(character) == 127 for character in raw):
        invalid("control_character", f"resource reference contains a control character: {raw!r}")
    if "?" in raw:
        invalid("query_string", f"resource reference contains a query string: {raw}")
    path_text, separator, fragment = raw.partition("#")
    decoded = urllib.parse.unquote(path_text)
    if decoded != path_text:
        invalid("percent_encoding", f"resource reference uses percent encoding: {raw}")
    if "\\" in path_text:
        invalid("backslash", f"resource reference must use POSIX separators: {raw}")
    windows_path = PureWindowsPath(path_text)
    posix_path = PurePosixPath(path_text)
    if posix_path.is_absolute():
        invalid("absolute_path", f"resource reference is absolute: {raw}")
    if windows_path.is_absolute() or windows_path.drive:
        invalid("windows_absolute_path", f"resource reference uses drive or UNC syntax: {raw}")
    parts = path_text.split("/")
    if any(not part for part in parts):
        invalid("empty_segment", f"resource reference contains an empty path segment: {raw}")
    if any(part == "." for part in parts):
        invalid("dot_segment", f"resource reference contains a '.' path segment: {raw}")
    if any(part == ".." for part in parts):
        invalid("parent_traversal", f"resource reference contains '..' traversal: {raw}")
    if not parts or parts[0] not in RESOURCE_KINDS:
        invalid(
            "unsupported_prefix",
            "resource reference must begin exactly with scripts/, references/, or assets/: "
            f"{raw}",
        )
    if len(parts) < 2:
        invalid("missing_filename", f"resource reference does not name a file: {raw}")
    resource_type = parts[0]
    fragment_value = fragment if separator else None
    if fragment_value is not None and not (
        resource_type == "references" and path_text.casefold().endswith(".md")
    ):
        invalid(
            "invalid_fragment",
            f"only Markdown references/ resources may use fragments: {raw}",
        )
    return ResourceReference(
        plugin_name=plugin_name,
        skill_name=skill_name,
        document=document,
        line=token.line,
        column=token.column,
        surface=token.surface,
        raw=raw,
        resource_path=path_text,
        resource_type=resource_type,
        fragment=fragment_value,
    )


def extract_resource_references(
    text: str,
    *,
    plugin_name: str,
    skill_name: str,
    document: Path,
) -> list[ResourceReference]:
    references: list[ResourceReference] = []
    for token in markdown_tokens(text):
        reference = _normalize_token(
            token,
            plugin_name=plugin_name,
            skill_name=skill_name,
            document=document,
        )
        if reference is not None:
            references.append(reference)
    return references


def _entry_metadata(
    entry: os.DirEntry[str],
    path: Path,
    *,
    plugin_name: str,
    skill_name: str | None,
) -> os.stat_result:
    try:
        metadata = entry.stat(follow_symlinks=False)
    except OSError as exc:
        _fail(
            "inspect_error",
            f"cannot inspect packaged resource path {path}: {exc}",
            plugin_name=plugin_name,
            skill_name=skill_name,
        )
    _reject_link_or_reparse(
        path,
        metadata,
        plugin_name=plugin_name,
        skill_name=skill_name,
    )
    return metadata


def _exact_entry(
    directory: Path,
    name: str,
    *,
    plugin_name: str,
    skill_name: str | None,
    reference: ResourceReference | None = None,
) -> os.DirEntry[str]:
    entries = _scandir(directory, plugin_name=plugin_name, skill_name=skill_name)
    exact = [entry for entry in entries if entry.name == name]
    if len(exact) == 1:
        return exact[0]
    insensitive = [entry.name for entry in entries if entry.name.casefold() == name.casefold()]
    kwargs = {
        "plugin_name": plugin_name,
        "skill_name": skill_name,
        "document": reference.document if reference else None,
        "line": reference.line if reference else None,
        "reference": reference.raw if reference else None,
    }
    if insensitive:
        _fail(
            "case_mismatch",
            f"resource path component {name!r} does not match source casing {insensitive!r}",
            **kwargs,
        )
    declared = f" (declared as {reference.raw})" if reference is not None else ""
    _fail(
        "missing_resource",
        f"packaged resource path is missing: {directory / name}{declared}",
        **kwargs,
    )


def _discover_skill_roots(plugin_root: Path, plugin_name: str) -> list[Path]:
    resolved_plugin = _require_real_directory(plugin_root, plugin_name=plugin_name)
    skills_entry = _exact_entry(
        plugin_root,
        "skills",
        plugin_name=plugin_name,
        skill_name=None,
    )
    skills_root = plugin_root / skills_entry.name
    metadata = _entry_metadata(
        skills_entry,
        skills_root,
        plugin_name=plugin_name,
        skill_name=None,
    )
    if not stat.S_ISDIR(metadata.st_mode):
        _fail(
            "not_directory",
            f"plugin skills path is not a directory: {skills_root}",
            plugin_name=plugin_name,
        )
    try:
        skills_root.resolve(strict=True).relative_to(resolved_plugin)
    except (OSError, RuntimeError, ValueError) as exc:
        _fail(
            "containment",
            f"plugin skills path escapes its plugin root: {skills_root}: {exc}",
            plugin_name=plugin_name,
        )

    skill_roots: list[Path] = []
    for entry in _scandir(skills_root, plugin_name=plugin_name):
        path = skills_root / entry.name
        metadata = _entry_metadata(
            entry,
            path,
            plugin_name=plugin_name,
            skill_name=entry.name,
        )
        if stat.S_ISDIR(metadata.st_mode):
            skill_roots.append(path)
        elif not stat.S_ISREG(metadata.st_mode):
            _fail(
                "special_file",
                f"unsupported special file below plugin skills/: {path}",
                plugin_name=plugin_name,
            )
    return skill_roots


def _validate_plugin_location(
    plugin_root: Path, repository_root: Path, plugin_name: str
) -> None:
    resolved_repository = _require_real_directory(
        repository_root, plugin_name=plugin_name
    )
    try:
        relative = plugin_root.relative_to(repository_root)
    except ValueError:
        _fail(
            "containment",
            f"plugin root is outside the repository root: {plugin_root}",
            plugin_name=plugin_name,
        )
    if not relative.parts:
        _fail(
            "containment",
            f"plugin root names the repository root: {plugin_root}",
            plugin_name=plugin_name,
        )
    current = repository_root
    for part in relative.parts:
        entry = _exact_entry(
            current,
            part,
            plugin_name=plugin_name,
            skill_name=None,
        )
        current /= entry.name
        metadata = _entry_metadata(
            entry,
            current,
            plugin_name=plugin_name,
            skill_name=None,
        )
        if not stat.S_ISDIR(metadata.st_mode):
            _fail(
                "not_directory",
                f"plugin path component is not a directory: {current}",
                plugin_name=plugin_name,
            )
    try:
        current.resolve(strict=True).relative_to(resolved_repository)
    except (OSError, RuntimeError, ValueError) as exc:
        _fail(
            "containment",
            f"plugin root escapes the repository root: {plugin_root}: {exc}",
            plugin_name=plugin_name,
        )


def _markdown_documents(skill_root: Path, plugin_name: str) -> list[Path]:
    skill_name = skill_root.name
    resolved_skill = _require_real_directory(
        skill_root,
        plugin_name=plugin_name,
        skill_name=skill_name,
    )
    skill_entry = _exact_entry(
        skill_root,
        "SKILL.md",
        plugin_name=plugin_name,
        skill_name=skill_name,
    )
    skill_path = skill_root / skill_entry.name
    skill_metadata = _entry_metadata(
        skill_entry,
        skill_path,
        plugin_name=plugin_name,
        skill_name=skill_name,
    )
    if not stat.S_ISREG(skill_metadata.st_mode):
        _fail(
            "not_regular_file",
            f"skill declaration is not a regular file: {skill_path}",
            plugin_name=plugin_name,
            skill_name=skill_name,
        )
    documents = [skill_path]

    references_entries = [
        entry
        for entry in _scandir(skill_root, plugin_name=plugin_name, skill_name=skill_name)
        if entry.name.casefold() == "references"
    ]
    if not references_entries:
        return documents
    references_entry = references_entries[0]
    if references_entry.name != "references":
        _fail(
            "case_mismatch",
            f"resource directory 'references' does not match source casing {references_entry.name!r}",
            plugin_name=plugin_name,
            skill_name=skill_name,
        )
    references_root = skill_root / references_entry.name
    metadata = _entry_metadata(
        references_entry,
        references_root,
        plugin_name=plugin_name,
        skill_name=skill_name,
    )
    if not stat.S_ISDIR(metadata.st_mode):
        _fail(
            "not_directory",
            f"skill references path is not a directory: {references_root}",
            plugin_name=plugin_name,
            skill_name=skill_name,
        )

    def walk(directory: Path) -> None:
        for entry in _scandir(directory, plugin_name=plugin_name, skill_name=skill_name):
            path = directory / entry.name
            entry_metadata = _entry_metadata(
                entry,
                path,
                plugin_name=plugin_name,
                skill_name=skill_name,
            )
            try:
                path.resolve(strict=True).relative_to(resolved_skill)
            except (OSError, RuntimeError, ValueError) as exc:
                _fail(
                    "containment",
                    f"reference document escapes its skill root: {path}: {exc}",
                    plugin_name=plugin_name,
                    skill_name=skill_name,
                )
            if stat.S_ISDIR(entry_metadata.st_mode):
                walk(path)
            elif stat.S_ISREG(entry_metadata.st_mode) and path.suffix.casefold() == ".md":
                documents.append(path)
            elif not stat.S_ISREG(entry_metadata.st_mode):
                _fail(
                    "special_file",
                    f"unsupported special file below references/: {path}",
                    plugin_name=plugin_name,
                    skill_name=skill_name,
                )

    walk(references_root)
    return sorted(documents, key=lambda path: path.relative_to(skill_root).as_posix())


def _validate_source_reference(skill_root: Path, reference: ResourceReference) -> Path:
    resolved_skill = _require_real_directory(
        skill_root,
        plugin_name=reference.plugin_name,
        skill_name=reference.skill_name,
    )
    current = skill_root
    parts = reference.resource_path.split("/")
    metadata: os.stat_result | None = None
    for index, part in enumerate(parts):
        entry = _exact_entry(
            current,
            part,
            plugin_name=reference.plugin_name,
            skill_name=reference.skill_name,
            reference=reference,
        )
        current /= entry.name
        metadata = _entry_metadata(
            entry,
            current,
            plugin_name=reference.plugin_name,
            skill_name=reference.skill_name,
        )
        if index < len(parts) - 1 and not stat.S_ISDIR(metadata.st_mode):
            _fail(
                "not_directory",
                f"resource path component is not a directory: {current}",
                plugin_name=reference.plugin_name,
                skill_name=reference.skill_name,
                document=reference.document,
                line=reference.line,
                reference=reference.raw,
            )
    assert metadata is not None
    if not stat.S_ISREG(metadata.st_mode):
        _fail(
            "not_regular_file",
            f"resource target is not a regular file: {current}",
            plugin_name=reference.plugin_name,
            skill_name=reference.skill_name,
            document=reference.document,
            line=reference.line,
            reference=reference.raw,
        )
    try:
        current.resolve(strict=True).relative_to(resolved_skill)
    except (OSError, RuntimeError, ValueError) as exc:
        _fail(
            "containment",
            f"resource target escapes its skill root: {current}: {exc}",
            plugin_name=reference.plugin_name,
            skill_name=reference.skill_name,
            document=reference.document,
            line=reference.line,
            reference=reference.raw,
        )
    return current


def validate_source_plugin(
    plugin_root: Path,
    plugin_name: str,
    *,
    repository_root: Path | None = None,
) -> list[ResourceReference]:
    """Validate and return all declarations from one plugin source tree."""
    if repository_root is not None:
        _validate_plugin_location(plugin_root, repository_root, plugin_name)
    references: list[ResourceReference] = []
    for skill_root in _discover_skill_roots(plugin_root, plugin_name):
        skill_name = skill_root.name
        for document in _markdown_documents(skill_root, plugin_name):
            try:
                text = document.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                _fail(
                    "read_error",
                    f"cannot read packaged Markdown document {document}: {exc}",
                    plugin_name=plugin_name,
                    skill_name=skill_name,
                    document=document.relative_to(skill_root),
                )
            document_relative = document.relative_to(skill_root)
            for reference in extract_resource_references(
                text,
                plugin_name=plugin_name,
                skill_name=skill_name,
                document=document_relative,
            ):
                _validate_source_reference(skill_root, reference)
                references.append(reference)
    return references


def validate_zip_closure(
    plugin_root: Path,
    plugin_name: str,
    archive: zipfile.ZipFile,
    *,
    references: Iterable[ResourceReference] | None = None,
    repository_root: Path | None = None,
) -> list[ResourceReference]:
    """Require every source declaration exactly once in an actual built ZIP."""
    validated = validate_source_plugin(
        plugin_root,
        plugin_name,
        repository_root=repository_root,
    )
    if references is not None:
        supplied = list(references)
        if Counter(_reference_identity(item) for item in supplied) != Counter(
            _reference_identity(item) for item in validated
        ):
            _fail(
                "source_declaration_changed",
                "source resource declarations changed during package construction",
                plugin_name=plugin_name,
            )
    names = [entry.filename for entry in archive.infolist()]
    duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
    if duplicates:
        _fail(
            "duplicate_zip_member",
            f"built plugin ZIP contains duplicate members: {duplicates}",
            plugin_name=plugin_name,
        )

    skill_roots = {
        skill_root.name: skill_root
        for skill_root in _discover_skill_roots(plugin_root, plugin_name)
    }
    expected_documents: set[str] = set()
    for skill_name, skill_root in skill_roots.items():
        for document in _markdown_documents(skill_root, plugin_name):
            expected_documents.add(
                f"skills/{skill_name}/{document.relative_to(skill_root).as_posix()}"
            )
    for expected_document in sorted(expected_documents):
        if names.count(expected_document) != 1:
            _fail(
                "missing_zip_document",
                f"built plugin ZIP is missing packaged Markdown document {expected_document}",
                plugin_name=plugin_name,
            )

    archive_references: list[ResourceReference] = []
    for name in sorted(names):
        parts = PurePosixPath(name).parts
        is_skill = len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md"
        is_reference_markdown = (
            len(parts) >= 4
            and parts[0] == "skills"
            and parts[2] == "references"
            and parts[-1].casefold().endswith(".md")
        )
        if not (is_skill or is_reference_markdown):
            continue
        skill_name = parts[1]
        skill_root = skill_roots.get(skill_name)
        if skill_root is None:
            _fail(
                "unknown_zip_skill",
                f"built plugin ZIP contains Markdown for unknown skill {skill_name!r}: {name}",
                plugin_name=plugin_name,
            )
        try:
            text = archive.read(name).decode("utf-8")
        except (KeyError, OSError, UnicodeError) as exc:
            _fail(
                "zip_read_error",
                f"cannot read packaged Markdown document {name}: {exc}",
                plugin_name=plugin_name,
                skill_name=skill_name,
            )
        document = Path(*parts[2:])
        for reference in extract_resource_references(
            text,
            plugin_name=plugin_name,
            skill_name=skill_name,
            document=document,
        ):
            _validate_source_reference(skill_root, reference)
            archive_references.append(reference)

    if Counter(_reference_identity(item) for item in archive_references) != Counter(
        _reference_identity(item) for item in validated
    ):
        _fail(
            "zip_declaration_drift",
            "built plugin ZIP resource declarations differ from the validated source tree",
            plugin_name=plugin_name,
        )

    for reference in archive_references:
        count = names.count(reference.zip_member)
        if count == 1:
            continue
        case_matches = [
            name for name in names if name.casefold() == reference.zip_member.casefold()
        ]
        if case_matches:
            _fail(
                "zip_case_mismatch",
                f"built plugin ZIP member casing differs: expected {reference.zip_member!r}, "
                f"found {case_matches!r}",
                plugin_name=plugin_name,
                skill_name=reference.skill_name,
                document=reference.document,
                line=reference.line,
                reference=reference.raw,
            )
        _fail(
            "missing_zip_member",
            f"built plugin ZIP is missing declared resource {reference.zip_member}",
            plugin_name=plugin_name,
            skill_name=reference.skill_name,
            document=reference.document,
            line=reference.line,
            reference=reference.raw,
        )
    return validated


def _reference_identity(reference: ResourceReference) -> tuple[object, ...]:
    return (
        reference.skill_name,
        reference.document.as_posix(),
        reference.line,
        reference.column,
        reference.surface,
        reference.raw,
        reference.resource_path,
        reference.fragment,
    )


def inventory_plugins(
    repository_root: Path, plugins: Iterable[dict[str, object]]
) -> dict[str, list[ResourceReference]]:
    """Return validated, machine-readable declarations grouped by plugin."""
    inventory: dict[str, list[ResourceReference]] = {}
    for plugin in plugins:
        name = plugin.get("name")
        path = plugin.get("path")
        if not isinstance(name, str) or not isinstance(path, str):
            raise ValueError("plugin inventory requires string name and path fields")
        inventory[name] = validate_source_plugin(
            repository_root / path,
            name,
            repository_root=repository_root,
        )
    return inventory
