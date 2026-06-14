from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .presenter import print_note, print_semgrep_summary, print_stage, print_success


SEMGREP_IMAGE = "semgrep/semgrep"
DEFAULT_FINDING_LIMIT = 100
DEFAULT_SEMGREP_CONFIGS = ("p/ci", "p/security-audit", "p/owasp-top-ten")


class SemgrepError(RuntimeError):
    pass


@dataclass(frozen=True)
class SemgrepFinding:
    check_id: str | None = None
    path: str | None = None
    start_line: int | None = None
    start_col: int | None = None
    end_line: int | None = None
    end_col: int | None = None
    message: str | None = None
    severity: str | None = None
    category: str | None = None
    technology: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SemgrepSummary:
    total_findings: int
    included_findings: int
    findings: list[SemgrepFinding]
    configs_used: list[str] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        config_text = (
            "Configs used: " + ", ".join(self.configs_used) + ".\n"
            if self.configs_used
            else ""
        )
        if self.total_findings == 0:
            return f"{config_text}Semgrep scan completed with no findings."

        heading = f"Semgrep scan found {self.total_findings} finding(s)"
        if self.included_findings < self.total_findings:
            heading += f", showing {self.included_findings} of {self.total_findings}"
        heading += "."

        payload = [
            {
                "check_id": finding.check_id,
                "path": finding.path,
                "start_line": finding.start_line,
                "start_col": finding.start_col,
                "end_line": finding.end_line,
                "end_col": finding.end_col,
                "message": finding.message,
                "severity": finding.severity,
                "category": finding.category,
                "technology": finding.technology,
            }
            for finding in self.findings
        ]
        return (
            f"{config_text}{heading}\n{json.dumps(payload, indent=2, sort_keys=True)}"
        )


def build_semgrep_command(scan_root: Path) -> list[str]:
    configs = _configured_rulesets()
    include_local_config = _include_local_config()
    native_configs = _native_config_args(scan_root, configs, include_local_config)
    docker_configs = _docker_config_args(scan_root, configs, include_local_config)

    if shutil.which("semgrep") is not None:
        return [
            "semgrep",
            "scan",
            *native_configs,
            "--json",
            "--metrics=off",
            str(scan_root),
        ]

    if shutil.which("docker") is not None:
        return [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{scan_root}:/src:ro",
            SEMGREP_IMAGE,
            "semgrep",
            "scan",
            *docker_configs,
            "--json",
            "--metrics=off",
            "/src",
        ]

    raise SemgrepError(
        "Semgrep was not found and Docker is not available for the Semgrep fallback."
    )


def _configured_rulesets() -> list[str]:
    raw_configs = os.environ.get("CODESENTINEL_SEMGREP_CONFIGS", "")
    if not raw_configs.strip():
        return list(DEFAULT_SEMGREP_CONFIGS)

    configs = [config.strip() for config in raw_configs.split(",") if config.strip()]
    if not configs:
        return list(DEFAULT_SEMGREP_CONFIGS)
    return configs


def _include_local_config() -> bool:
    return (
        os.environ.get("CODESENTINEL_SEMGREP_INCLUDE_LOCAL_CONFIG", "").strip() == "1"
    )


def _native_config_args(
    scan_root: Path, configs: list[str], include_local_config: bool
) -> list[str]:
    args = [f"--config={config}" for config in configs]
    local_config = scan_root / ".semgrep.yml"
    if include_local_config and local_config.exists():
        args.append(f"--config={local_config}")
    return args


def _docker_config_args(
    scan_root: Path, configs: list[str], include_local_config: bool
) -> list[str]:
    args = [f"--config={config}" for config in configs]
    if include_local_config and (scan_root / ".semgrep.yml").exists():
        args.append("--config=/src/.semgrep.yml")
    return args


def parse_semgrep_json(
    stdout: str,
    limit: int = DEFAULT_FINDING_LIMIT,
    configs_used: list[str] | None = None,
) -> SemgrepSummary:
    try:
        payload = json.loads(stdout.strip() or "{}")
    except json.JSONDecodeError as exc:
        raise SemgrepError("Semgrep returned invalid JSON output.") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise SemgrepError("Semgrep JSON output did not include a results list.")

    all_findings = [
        _normalize_finding(result)
        for result in payload["results"]
        if isinstance(result, dict)
    ]
    findings = all_findings[:limit]
    return SemgrepSummary(
        total_findings=len(all_findings),
        included_findings=len(findings),
        findings=findings,
        configs_used=list(configs_used or []),
    )


def run_semgrep(scan_root: Path) -> SemgrepSummary:
    configs_used = _configured_rulesets()
    if _include_local_config() and (scan_root / ".semgrep.yml").exists():
        configs_used.append(str(scan_root / ".semgrep.yml"))
    command = build_semgrep_command(scan_root)
    print_stage(
        "Code Review",
        "Inspecting source paths for high-signal security issues",
        icon="+",
    )
    completed = subprocess.run(
        command,
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
        raise SemgrepError(
            f"Semgrep scan failed with exit code {completed.returncode}."
            + (f"\n\nstderr:\n{stderr}" if stderr else "")
        )

    summary = parse_semgrep_json(completed.stdout, configs_used=configs_used)
    print_semgrep_summary(summary)
    if summary.configs_used:
        print_note("Rulesets tuned for CI, security audit, and OWASP coverage")
    print_success("Code review completed")
    return summary


def _normalize_finding(payload: dict[str, Any]) -> SemgrepFinding:
    extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
    metadata = extra.get("metadata") if isinstance(extra.get("metadata"), dict) else {}
    start = payload.get("start") if isinstance(payload.get("start"), dict) else {}
    end = payload.get("end") if isinstance(payload.get("end"), dict) else {}

    return SemgrepFinding(
        check_id=_optional_str(payload.get("check_id")),
        path=_optional_str(payload.get("path")),
        start_line=_optional_int(start.get("line")),
        start_col=_optional_int(start.get("col")),
        end_line=_optional_int(end.get("line")),
        end_col=_optional_int(end.get("col")),
        message=_optional_str(extra.get("message")),
        severity=_optional_str(extra.get("severity")),
        category=_optional_str(metadata.get("category")),
        technology=_string_list(metadata.get("technology")),
    )


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _string_list(value: object) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []
