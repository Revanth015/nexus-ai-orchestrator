from __future__ import annotations

import re
import statistics
import time
from collections import Counter
from datetime import datetime, timezone


def _telemetry(worker_id: str, worker_name: str, latency_ms: float, *, requests: int = 1) -> dict[str, object]:
    return {
        "provider": "local",
        "worker_id": worker_id,
        "model": "deterministic-local-v1",
        "configured": True,
        "execution_ready": True,
        "free_only": True,
        "free_model_verified": True,
        "quota_status": "not_applicable",
        "quota_exact": None,
        "quota_estimate": None,
        "observed_requests": requests,
        "successful_requests": requests,
        "failed_requests": 0,
        "last_success_at": datetime.now(timezone.utc).isoformat(),
        "last_failure_at": None,
        "last_latency_ms": round(latency_ms, 2),
        "failure_class": None,
        "last_error": None,
        "note": "Local deterministic execution; no external AI quota is consumed.",
    }


def _file_summary(file_context: list[dict[str, object]]) -> str:
    if not file_context:
        return "No uploaded files were supplied."
    lines = []
    for item in file_context:
        content = str(item.get("content", ""))
        lines.append(
            f"File: {item.get('filename', item.get('file_id', 'unknown'))}\n"
            f"Type: {item.get('extension', 'unknown')}\n"
            f"Extracted characters: {len(content)}\n"
            f"Preview:\n{content[:4000]}"
        )
    return "\n\n".join(lines)


def _split_rows(content: str) -> list[tuple[str | None, list[str]]]:
    """Parse the normalized file-store representation into sheet/row pairs."""
    rows: list[tuple[str | None, list[str]]] = []
    current_sheet: str | None = None
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("[truncated"):
            continue
        sheet_match = re.fullmatch(r"\[SHEET:\s*(.*?)\]", line)
        if sheet_match:
            current_sheet = sheet_match.group(1).strip() or "Sheet"
            continue
        if line.startswith("[PAGE "):
            current_sheet = line.strip("[]")
            continue
        rows.append((current_sheet, [part.strip() for part in raw.split(" | ")]))
    return rows


def _is_number(value: str) -> bool:
    cleaned = value.strip().replace(",", "")
    if not cleaned:
        return False
    return bool(re.fullmatch(r"[-+]?\d+(?:\.\d+)?", cleaned))


def _numeric(value: str) -> float:
    return float(value.strip().replace(",", ""))


def _tabular_analysis(item: dict[str, object]) -> str:
    """Produce deterministic column-level analysis from CSV/XLSX extracted rows."""
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

    report: list[str] = [f"File: {filename}", f"Type: {extension or 'unknown'}"]
    total_rows = 0
    total_columns = 0

    for sheet_name in order:
        raw_rows = grouped[sheet_name]
        if not raw_rows:
            continue
        header = raw_rows[0]
        # Ignore completely blank headers while retaining column positions.
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
            missing = len(values) - len(non_empty)
            missing_cells += missing
            numeric_values = [_numeric(value) for value in non_empty if _is_number(value)]
            numeric_ratio = (len(numeric_values) / len(non_empty)) if non_empty else 0

            if numeric_values and numeric_ratio >= 0.8:
                numeric_columns += 1
                average = statistics.mean(numeric_values)
                minimum = min(numeric_values)
                maximum = max(numeric_values)
                report.append(
                    f"- {column}: numeric; non-empty={len(non_empty)}/{len(values)}; "
                    f"avg={average:.2f}; min={minimum:.2f}; max={maximum:.2f}"
                )
            else:
                distinct = len(set(non_empty))
                detail = f"categorical/text; non-empty={len(non_empty)}/{len(values)}; unique={distinct}"
                if non_empty and distinct <= 10:
                    common = Counter(non_empty).most_common(3)
                    detail += "; top=" + ", ".join(f"{value} ({count})" for value, count in common)
                report.append(f"- {column}: {detail}")

        report.append(f"Missing cells: {missing_cells}; numeric columns: {numeric_columns}")

    report.extend([
        "",
        "Dataset overview:",
        f"- Sheets/tables: {len(order)}",
        f"- Data rows: {total_rows}",
        f"- Maximum columns in a table: {total_columns}",
        "- Analysis method: deterministic column profiling; no semantic business conclusions are invented.",
    ])
    return "\n".join(report)


def _data_analysis_output(prompt: str, files: list[dict[str, object]]) -> str:
    if not files:
        numbers = [float(value) for value in re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?", prompt)]
        if not numbers:
            return (
                "Deterministic local analysis completed.\n"
                "No uploaded dataset was supplied and no numeric dataset was detected in the prompt.\n"
                "Provide a CSV/XLSX file for column-level profiling."
            )
        average = sum(numbers) / len(numbers)
        return (
            "Deterministic local analysis completed.\n"
            f"Numeric values detected: {len(numbers)}\n"
            f"Average: {average:.2f}\n"
            f"Minimum: {min(numbers):.2f}\n"
            f"Maximum: {max(numbers):.2f}"
        )

    sections: list[str] = [
        "Deterministic local dataset analysis completed.",
        f"Files analyzed: {len(files)}",
        "",
    ]
    for item in files:
        extension = str(item.get("extension", "")).lower()
        if extension in {".csv", ".xlsx", ".xlsm"}:
            sections.append(_tabular_analysis(item))
        else:
            content = str(item.get("content", ""))
            sections.append(
                f"File: {item.get('filename', 'file')}\n"
                f"Type: {extension or 'unknown'}\n"
                f"Extracted characters: {len(content)}\n"
                "This file type is available as extracted text; use file_analysis for detailed document inspection."
            )
        sections.append("\n" + "-" * 40 + "\n")
    sections.append("No external AI was used; all reported statistics are calculated from the supplied file contents.")
    return "\n".join(sections)


def execute_local_task(
    task_type: str,
    prompt: str,
    *,
    file_context: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Execute deterministic tasks locally, optionally using extracted uploaded files."""
    started = time.perf_counter()
    files = file_context or []

    if task_type == "quality_review":
        text = prompt.strip()
        checks: list[str] = []
        checks.append("sufficient_content" if len(text) >= 120 else "content_too_short")
        checks.append("task_context_present" if "Mission objective:" in text and "Current task:" in text else "task_context_missing")
        checks.append("upstream_artifact_present" if "Previous task outputs:" in text else "upstream_artifact_missing")
        checks.append("uploaded_file_present" if files else "uploaded_file_not_supplied")
        passed = all(item.endswith("present") or item == "sufficient_content" for item in checks)
        decision = "PASS" if passed else "REWORK"
        output = "Deterministic quality gate completed.\n" f"Checks: {', '.join(checks)}.\n" f"{decision}"
        worker_id = "local-validator"
        worker_name = "NEXUS Local Validator"

    elif task_type == "data_analysis":
        output = _data_analysis_output(prompt.strip(), files)
        worker_id = "local-tools"
        worker_name = "NEXUS Local Tools"

    elif task_type == "file_analysis":
        text = prompt.strip()
        if not files:
            output = (
                "Local file-analysis worker received no uploaded file.\n"
                f"Execution context characters: {len(text)}\n"
                "No file-specific conclusions were generated."
            )
        else:
            output = (
                "Local file analysis completed.\n"
                f"Files inspected: {len(files)}\n\n"
                + "\n\n".join(
                    _tabular_analysis(item)
                    if str(item.get("extension", "")).lower() in {".csv", ".xlsx", ".xlsm"}
                    else f"{item.get('filename', 'file')}: {len(str(item.get('content', '')))} extracted characters"
                    for item in files
                )
            )
        worker_id = "local-tools"
        worker_name = "NEXUS Local Tools"

    else:
        raise RuntimeError(f"Local worker does not support task type '{task_type}'.")

    latency_ms = (time.perf_counter() - started) * 1000
    return {
        "text": output,
        "worker_id": worker_id,
        "worker_name": worker_name,
        "telemetry": _telemetry(worker_id, worker_name, latency_ms),
    }
