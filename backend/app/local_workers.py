from __future__ import annotations

import re
import statistics
import time
from collections import Counter
from datetime import datetime, timezone


def _telemetry(worker_id: str, worker_name: str, latency_ms: float, *, requests: int = 1) -> dict[str, object]:
    return {
        "provider": "local", "worker_id": worker_id, "model": "deterministic-local-v1",
        "configured": True, "execution_ready": True, "free_only": True, "free_model_verified": True,
        "quota_status": "not_applicable", "quota_exact": None, "quota_estimate": None,
        "observed_requests": requests, "successful_requests": requests, "failed_requests": 0,
        "last_success_at": datetime.now(timezone.utc).isoformat(), "last_failure_at": None,
        "last_latency_ms": round(latency_ms, 2), "failure_class": None, "last_error": None,
        "note": "Local deterministic execution; no external AI quota is consumed.",
    }


def _split_rows(content: str) -> list[tuple[str | None, list[str]]]:
    rows: list[tuple[str | None, list[str]]] = []
    current_sheet: str | None = None
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("[truncated"):
            continue
        match = re.fullmatch(r"\[SHEET:\s*(.*?)\]", line)
        if match:
            current_sheet = match.group(1).strip() or "Sheet"
            continue
        if line.startswith("[PAGE "):
            current_sheet = line.strip("[]")
            continue
        rows.append((current_sheet, [part.strip() for part in raw.split(" | ")]))
    return rows


def _is_number(value: str) -> bool:
    return bool(re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value.strip().replace(",", "")))


def _numeric(value: str) -> float:
    return float(value.strip().replace(",", ""))


def _tabular_analysis(item: dict[str, object]) -> str:
    content = str(item.get("content", ""))
    extension = str(item.get("extension", "")).lower()
    filename = str(item.get("filename", "uploaded file"))
    parsed = _split_rows(content)
    if not parsed:
        return f"File: {filename}\nNo tabular rows were extracted."
    grouped: dict[str, list[list[str]]] = {}
    order: list[str] = []
    for sheet, row in parsed:
        name = sheet or ("CSV" if extension == ".csv" else "Sheet")
        if name not in grouped:
            grouped[name] = []
            order.append(name)
        grouped[name].append(row)
    report = [f"File: {filename}", f"Type: {extension or 'unknown'}"]
    total_rows = 0
    total_columns = 0
    for sheet_name in order:
        raw_rows = grouped[sheet_name]
        header = raw_rows[0]
        columns = [value if value else f"Column {i + 1}" for i, value in enumerate(header)]
        data = [row + [""] * max(0, len(columns) - len(row)) for row in raw_rows[1:]]
        data = [row[:len(columns)] for row in data]
        total_rows += len(data)
        total_columns = max(total_columns, len(columns))
        report.append(f"\n[{sheet_name}] rows={len(data)}, columns={len(columns)}")
        report.append("Columns: " + ", ".join(columns))
        duplicate_count = len(data) - len({tuple(row) for row in data})
        if duplicate_count > 0:
            report.append(f"Duplicate rows: {duplicate_count}")
        numeric_columns = 0
        missing_cells = 0
        for index, column in enumerate(columns):
            values = [row[index].strip() for row in data]
            non_empty = [value for value in values if value]
            missing_cells += len(values) - len(non_empty)
            numeric_values = [_numeric(value) for value in non_empty if _is_number(value)]
            ratio = len(numeric_values) / len(non_empty) if non_empty else 0
            if numeric_values and ratio >= 0.8:
                numeric_columns += 1
                report.append(f"- {column}: numeric; non-empty={len(non_empty)}/{len(values)}; avg={statistics.mean(numeric_values):.2f}; min={min(numeric_values):.2f}; max={max(numeric_values):.2f}")
            else:
                distinct = len(set(non_empty))
                detail = f"categorical/text; non-empty={len(non_empty)}/{len(values)}; unique={distinct}"
                if non_empty and distinct <= 10:
                    detail += "; top=" + ", ".join(f"{v} ({c})" for v, c in Counter(non_empty).most_common(3))
                report.append(f"- {column}: {detail}")
        report.append(f"Missing cells: {missing_cells}; numeric columns: {numeric_columns}")
    report.extend(["", "Dataset overview:", f"- Sheets/tables: {len(order)}", f"- Data rows: {total_rows}", f"- Maximum columns in a table: {total_columns}", "- Analysis method: deterministic column profiling."])
    return "\n".join(report)


def _data_analysis_output(prompt: str, files: list[dict[str, object]]) -> str:
    if not files:
        numbers = [float(value) for value in re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?", prompt)]
        if not numbers:
            return "Deterministic local analysis completed.\nNo uploaded dataset or numeric dataset was detected."
        return "Deterministic local analysis completed.\n" + "\n".join([
            f"Numeric values detected: {len(numbers)}", f"Average: {statistics.mean(numbers):.2f}",
            f"Minimum: {min(numbers):.2f}", f"Maximum: {max(numbers):.2f}",
        ])
    sections = ["Deterministic local dataset analysis completed.", f"Files analyzed: {len(files)}", ""]
    for item in files:
        ext = str(item.get("extension", "")).lower()
        sections.append(_tabular_analysis(item) if ext in {".csv", ".xlsx", ".xlsm"} else f"File: {item.get('filename', 'file')}\nType: {ext or 'unknown'}\nExtracted characters: {len(str(item.get('content', '')))}")
        sections.append("\n" + "-" * 40 + "\n")
    sections.append("No external AI was used; reported statistics come from supplied contents.")
    return "\n".join(sections)


def _quality_review(prompt: str) -> str:
    text = prompt.strip()
    checks = [
        "task_context_present" if "Mission objective:" in text and "Current task:" in text else "task_context_missing",
        "upstream_artifact_present" if "Previous task outputs:" in text else "upstream_artifact_missing",
        "sufficient_artifact_content" if len(text) >= 180 else "artifact_too_short",
    ]
    passed = all(check.endswith("present") or check == "sufficient_artifact_content" for check in checks)
    recommendation = "PASS" if passed else "REWORK"
    if passed:
        problem = "None identified."
    else:
        problems = {
            "task_context_missing": "The review task is missing required mission/task context.",
            "upstream_artifact_missing": "The upstream employee artifact is missing from the review input.",
            "artifact_too_short": "The supplied work artifact is too short for a reliable quality review.",
        }
        problem = "; ".join(problems[check] for check in checks if check in problems) or "Quality requirements were not satisfied."
    return (
        "Quality review employee completed an independent review.\n"
        f"Checks: {', '.join(checks)}.\n"
        f"Problem identified: {problem}\n"
        f"Recommendation to NEXUS Manager: {recommendation}\n"
        "The Manager retains final authority over acceptance."
    )


def execute_local_task(task_type: str, prompt: str, *, file_context: list[dict[str, object]] | None = None) -> dict[str, object]:
    started = time.perf_counter()
    files = file_context or []
    if task_type == "quality_review":
        output, worker_id, worker_name = _quality_review(prompt), "local-validator", "NEXUS Quality Review Employee"
    elif task_type == "data_analysis":
        output, worker_id, worker_name = _data_analysis_output(prompt.strip(), files), "local-tools", "NEXUS Local Tools Employee"
    elif task_type == "file_analysis":
        if not files:
            output = "File-analysis employee received no uploaded file. No file-specific conclusions were generated."
        else:
            output = "Local file analysis employee completed inspection.\n\n" + "\n\n".join(
                _tabular_analysis(item) if str(item.get("extension", "")).lower() in {".csv", ".xlsx", ".xlsm"} else f"{item.get('filename', 'file')}: {len(str(item.get('content', '')))} extracted characters"
                for item in files
            )
        worker_id, worker_name = "local-tools", "NEXUS Local Tools Employee"
    else:
        raise RuntimeError(f"Local worker does not support task type '{task_type}'.")
    latency = (time.perf_counter() - started) * 1000
    return {"text": output, "worker_id": worker_id, "worker_name": worker_name, "telemetry": _telemetry(worker_id, worker_name, latency)}
