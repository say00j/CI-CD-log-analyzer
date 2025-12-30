"""
preprocess.py

Simple heuristic-based log preprocessing utilities for the AI Log Analyzer.

Functions:
- extract_relevant_lines(text, max_lines=500)
    Returns a reduced text containing lines that likely indicate errors, stack traces,
    or other failure indicators. If nothing is matched, returns the last `max_lines`
    lines as a fallback.

- summarize_metadata(text)
    Quick metadata extractor returning counts (lines, error lines) and detected
    keywords (e.g., Python traceback, Java exception, exit codes).
"""

import re
from typing import Dict, Any, List

# Patterns that commonly indicate errors / failures in CI logs
ERROR_KEYWORDS_RE = re.compile(
    r'\b(ERROR|FAIL|FAILED|EXCEPTION|EXCEPTION:|TRACEBACK|TRACEBACK \(most recent call last\)|Stacktrace|panic|segfault|exit code|fatal)\b',
    re.I
)

# Common stack trace starters (Python, Java, Node, Go)
STACK_STARTERS = [
    r'Traceback \(most recent call last\):',  # python
    r'Exception in thread',                   # java
    r'at [\w.$]+\(.*\)',                      # java/node "at ..." lines
    r'File ".*", line \d+',                   # python file line
    r'panic: ',                               # go panic
]

STACK_STARTERS_RE = re.compile('|'.join(re.escape(s) for s in STACK_STARTERS), re.I)


def extract_relevant_lines(text: str, max_lines: int = 500, context_lines: int = 2) -> str:
    """
    Extracts lines that are most likely relevant (errors, stack traces, exceptions).
    Keeps a small amount of context lines around matches.

    Args:
        text: full log text
        max_lines: max number of lines to return in fallback mode
        context_lines: number of surrounding lines to include around a matched line

    Returns:
        reduced text composed of matched segments (joined by "\n---\n" delimiters).
    """
    if not text:
        return ""

    lines = text.splitlines()
    n = len(lines)
    matched_indices = set()

    # 1) Mark lines with obvious error keywords
    for i, line in enumerate(lines):
        if ERROR_KEYWORDS_RE.search(line):
            for j in range(max(0, i - context_lines), min(n, i + context_lines + 1)):
                matched_indices.add(j)

    # 2) Mark lines where stack traces / stack starters appear
    for i, line in enumerate(lines):
        if STACK_STARTERS_RE.search(line):
            # collect subsequent indented or "at " lines as part of the stack block
            for j in range(i, min(n, i + 200)):  # limit growth
                ln = lines[j]
                matched_indices.add(j)
                # heuristics for end of trace: blank line or non-indented & not "at "
                if not (ln.startswith(" ") or ln.startswith("\t") or ln.strip().startswith("at ") or ln.strip().startswith("File ")):
                    # Keep scanning to collect a few lines of context, but stop growth will be bounded by the loop limit
                    pass

    # 3) If we found nothing, fallback: return last `max_lines` lines
    if not matched_indices:
        start = max(0, n - max_lines)
        return "\n".join(lines[start:])

    # 4) Build contiguous blocks from matched indices and include a small window
    sorted_idx = sorted(matched_indices)
    blocks: List[str] = []
    block_start = sorted_idx[0]
    block_end = sorted_idx[0]

    for idx in sorted_idx[1:]:
        if idx <= block_end + 1:
            block_end = idx
        else:
            # flush current block
            blocks.append("\n".join(lines[block_start:block_end+1]))
            block_start = idx
            block_end = idx
    blocks.append("\n".join(lines[block_start:block_end+1]))

    # 5) If the combined content is too long, trim each block proportionally or keep first/last blocks
    combined = "\n\n---\n\n".join(blocks)
    # If too large, fall back to last max_lines lines
    max_chars = 200_000  # generous upper bound for practical logs
    if len(combined) > max_chars:
        start = max(0, n - max_lines)
        return "\n".join(lines[start:])

    return combined


def summarize_metadata(text: str) -> Dict[str, Any]:
    """
    Return quick metadata about the log useful for prompts or UI:
    - total_lines
    - error_line_count
    - contains_traceback (bool)
    - detected_keywords (list)
    """
    if not text:
        return {"total_lines": 0, "error_line_count": 0, "contains_traceback": False, "detected_keywords": []}

    lines = text.splitlines()
    total = len(lines)
    error_count = 0
    detected = set()
    contains_traceback = False

    for line in lines:
        if ERROR_KEYWORDS_RE.search(line):
            error_count += 1
            # capture a normalized keyword for metadata tagging
            m = ERROR_KEYWORDS_RE.search(line)
            if m:
                detected.add(m.group(0).upper())

        # Robust detection: if the line contains the word "traceback" (case-insensitive),
        # mark contains_traceback True. This is simpler and less brittle than relying solely on complex regex.
        if "traceback" in line.lower() or STACK_STARTERS_RE.search(line):
            contains_traceback = True

    return {
        "total_lines": total,
        "error_line_count": error_count,
        "contains_traceback": contains_traceback,
        "detected_keywords": sorted(list(detected))[:10]
    }
