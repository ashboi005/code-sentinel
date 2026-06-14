from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


TRUFFLEHOG_IMAGE = "trufflesecurity/trufflehog:latest"
TRUFFLEHOG_RESULTS = "verified,unknown,unverified,filtered_unverified"
DEFAULT_FINDING_LIMIT = 100


class TruffleHogError(RuntimeError):
    pass


@dataclass(frozen=True)
class TruffleHogCommand:
    source_kind: str
    argv: list[str]


@dataclass(frozen=True)
class TruffleHogFinding:
    source_kind: str
    detector_name: str | None = None
    detector_type: int | None = None
    decoder_name: str | None = None
    verified: bool | None = None
    file: str | None = None
    line: int | None = None
    commit: str | None = None
    email: str | None = None
    repository: str | None = None
    timestamp: str | None = None
    redacted: str | None = None
    extra_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TruffleHogSummary:
    total_findings: int
    included_findings: int
    findings: list[TruffleHogFinding]
    finding_counts_by_source: dict[str, int] = field(default_factory=dict)
    git_history_scanned: bool = False
    git_history_skipped: bool = False

    def to_prompt_text(self) -> str:
        if self.total_findings == 0:
            git_status = "Git history was scanned." if self.git_history_scanned else "Git history was skipped because the target is not a Git repository."
            return f"TruffleHog scan completed with no verified, unknown, unverified, or filtered unverified findings. {git_status}"

        heading = f"TruffleHog scan found {self.total_findings} finding(s)"
        if self.included_findings < self.total_findings:
            heading += f", showing {self.included_findings} of {self.total_findings}"
        heading += f". Counts by source: {json.dumps(self.finding_counts_by_source, sort_keys=True)}."
        heading += " Git history was scanned." if self.git_history_scanned else " Git history was skipped because the target is not a Git repository."

        payload = [
            {
                "source_kind": finding.source_kind,
                "detector_name": finding.detector_name,
                "detector_type": finding.detector_type,
                "decoder_name": finding.decoder_name,
                "verified": finding.verified,
                "file": finding.file,
                "line": finding.line,
                "commit": finding.commit,
                "email": finding.email,
                "repository": finding.repository,
                "timestamp": finding.timestamp,
                "redacted": finding.redacted,
                "extra_data": finding.extra_data,
            }
            for finding in self.findings
        ]
        return f"{heading}\n{json.dumps(payload, indent=2, sort_keys=True)}"


def build_trufflehog_command(scan_root: Path) -> list[str]:
    return build_trufflehog_commands(scan_root)[0].argv


def build_trufflehog_commands(scan_root: Path) -> list[TruffleHogCommand]:
    commands = [_build_filesystem_command(scan_root)]
    if (scan_root / ".git").exists():
        commands.append(_build_git_command(scan_root))
    return commands


def _build_filesystem_command(scan_root: Path) -> TruffleHogCommand:
    if shutil.which("trufflehog") is not None:
        return TruffleHogCommand(
            source_kind="filesystem",
            argv=[
                "trufflehog",
                "filesystem",
                str(scan_root),
                "--json",
                f"--results={TRUFFLEHOG_RESULTS}",
                "--no-update",
            ],
        )

    if shutil.which("docker") is not None:
        return TruffleHogCommand(
            source_kind="filesystem",
            argv=[
                "docker",
                "run",
                "--rm",
                "-v",
                f"{scan_root}:/pwd:ro",
                TRUFFLEHOG_IMAGE,
                "filesystem",
                "/pwd",
                "--json",
                f"--results={TRUFFLEHOG_RESULTS}",
                "--no-update",
            ],
        )

    raise TruffleHogError("TruffleHog was not found and Docker is not available for the TruffleHog fallback.")


def _build_git_command(scan_root: Path) -> TruffleHogCommand:
    if shutil.which("trufflehog") is not None:
        return TruffleHogCommand(
            source_kind="git",
            argv=[
                "trufflehog",
                "git",
                f"file://{scan_root}",
                "--json",
                f"--results={TRUFFLEHOG_RESULTS}",
                "--no-update",
            ],
        )

    if shutil.which("docker") is not None:
        return TruffleHogCommand(
            source_kind="git",
            argv=[
                "docker",
                "run",
                "--rm",
                "-v",
                f"{scan_root}:/pwd:ro",
                TRUFFLEHOG_IMAGE,
                "git",
                "file:///pwd",
                "--json",
                f"--results={TRUFFLEHOG_RESULTS}",
                "--no-update",
            ],
        )

    raise TruffleHogError("TruffleHog was not found and Docker is not available for the TruffleHog fallback.")


def parse_trufflehog_jsonl(stdout: str, source_kind: str, limit: int = DEFAULT_FINDING_LIMIT) -> TruffleHogSummary:
    all_findings = []
    for line in stdout.splitlines():
        if not line.strip():
            continue

        payload = json.loads(line)
        if _is_finding_payload(payload):
            all_findings.append(_normalize_finding(payload, source_kind))

    findings = all_findings[:limit]
    finding_counts_by_source = _count_findings_by_source(findings)
    return TruffleHogSummary(
        total_findings=len(all_findings),
        included_findings=len(findings),
        findings=findings,
        finding_counts_by_source=finding_counts_by_source,
        git_history_scanned=source_kind == "git",
        git_history_skipped=source_kind != "git",
    )


def run_trufflehog(scan_root: Path) -> TruffleHogSummary:
    commands = build_trufflehog_commands(scan_root)
    summaries = []
    for command in commands:
        print(
            "[codesentinel] starting trufflehog "
            + json.dumps({"scan_root": str(scan_root), "source_kind": command.source_kind}, sort_keys=True),
            file=sys.stderr,
        )
        completed = subprocess.run(
            command.argv,
            cwd=scan_root,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=180,
        )

        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            raise TruffleHogError(
                f"TruffleHog {command.source_kind} scan failed with exit code {completed.returncode}."
                + (f"\n\nstderr:\n{stderr}" if stderr else "")
            )

        summaries.append(parse_trufflehog_jsonl(completed.stdout, source_kind=command.source_kind))

    summary = _merge_summaries(summaries)
    print(
        "[codesentinel] trufflehog completed "
        + json.dumps(
            {
                "total_findings": summary.total_findings,
                "included_findings": summary.included_findings,
                "finding_counts_by_source": summary.finding_counts_by_source,
                "git_history_scanned": summary.git_history_scanned,
            },
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    return summary


def _is_finding_payload(payload: object) -> bool:
    return isinstance(payload, dict) and isinstance(payload.get("SourceMetadata"), dict) and "DetectorName" in payload


def _normalize_finding(payload: dict[str, Any], source_kind: str) -> TruffleHogFinding:
    source = _source_data(payload)
    return TruffleHogFinding(
        source_kind=source_kind,
        detector_name=_optional_str(payload.get("DetectorName")),
        detector_type=_optional_int(payload.get("DetectorType")),
        decoder_name=_optional_str(payload.get("DecoderName")),
        verified=payload.get("Verified") if isinstance(payload.get("Verified"), bool) else None,
        file=_optional_str(source.get("file")),
        line=_optional_int(source.get("line")),
        commit=_optional_str(source.get("commit")),
        email=_optional_str(source.get("email")),
        repository=_optional_str(source.get("repository")),
        timestamp=_optional_str(source.get("timestamp")),
        redacted=_optional_str(payload.get("Redacted")),
        extra_data=payload.get("ExtraData") if isinstance(payload.get("ExtraData"), dict) else {},
    )


def _source_data(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("SourceMetadata")
    if not isinstance(metadata, dict):
        return {}

    data = metadata.get("Data")
    if not isinstance(data, dict):
        return {}

    for value in data.values():
        if isinstance(value, dict):
            return value
    return {}


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _merge_summaries(summaries: list[TruffleHogSummary]) -> TruffleHogSummary:
    findings = [finding for summary in summaries for finding in summary.findings]
    total_findings = sum(summary.total_findings for summary in summaries)
    return TruffleHogSummary(
        total_findings=total_findings,
        included_findings=len(findings),
        findings=findings,
        finding_counts_by_source=_count_findings_by_source(findings),
        git_history_scanned=any(summary.git_history_scanned for summary in summaries),
        git_history_skipped=not any(summary.git_history_scanned for summary in summaries),
    )


def _count_findings_by_source(findings: list[TruffleHogFinding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.source_kind] = counts.get(finding.source_kind, 0) + 1
    return counts
