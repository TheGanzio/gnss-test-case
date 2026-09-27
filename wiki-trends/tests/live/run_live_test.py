#!/usr/bin/env python3
"""Live verification harness: drives this skill with a real small/cheap
model (default: claude-haiku-4-5) through the Anthropic API, using a single
`bash` tool scoped to the skill directory, and writes the full transcript to
a markdown file for evidence.

This is NOT part of the skill itself and is NOT a runtime dependency of
SKILL.md — it's a one-off verification tool for development. See
../../TESTING.md for how to read the results and for a saved transcript.

Usage:
    ANTHROPIC_API_KEY=... python3 run_live_test.py "<question in Ukrainian>"
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic

SKILL_DIR = Path(__file__).resolve().parent.parent.parent
MODEL = os.environ.get("LIVE_TEST_MODEL", "claude-haiku-4-5-20251001")
MAX_TURNS = 10
BASH_TIMEOUT_S = 60

SYSTEM_PROMPT = f"""\
You are an AI agent with access to one tool: `bash`, which runs shell
commands with cwd={SKILL_DIR} (a Python virtualenv is already active as
`.venv`). You have access to the "wiki-trends" Agent Skill installed in
this directory. Its SKILL.md instructions:

---SKILL.md START---
{(SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")}
---SKILL.md END---

Follow SKILL.md exactly: call `python3 -m scripts.cli ...` via the bash
tool to do the real work, read the JSON it prints, and then answer the
user's question in your own words based on that JSON. Do not fabricate
numbers. Always mention the confidence label and its reason, and mention
if any requested language had no matching article. Answer in Ukrainian,
in 4-8 sentences, since the user asked in Ukrainian.
"""

TOOLS = [
    {
        "name": "bash",
        "description": "Run a shell command in the skill directory and return its stdout/stderr/exit code.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    }
]


def run_bash(command: str) -> str:
    full_cmd = f"source {SKILL_DIR}/.venv/bin/activate && {command}"
    try:
        proc = subprocess.run(
            full_cmd, shell=True, cwd=SKILL_DIR, capture_output=True, text=True,
            timeout=BASH_TIMEOUT_S, executable="/bin/bash",
        )
        out = proc.stdout[-4000:]
        err = proc.stderr[-2000:]
        return f"exit_code={proc.returncode}\nstdout:\n{out}\nstderr:\n{err}"
    except subprocess.TimeoutExpired:
        return f"error: command timed out after {BASH_TIMEOUT_S}s"


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else (
        "Ми думаємо додати курс з астрономії до освітнього застосунку. "
        "Чи зростає інтерес до цієї теми в україномовній Wikipedia, і "
        "наскільки цьому зростанню можна довіряти?"
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": question}]

    log_lines = [
        f"# Live verification run",
        f"",
        f"- Model: `{MODEL}`",
        f"- Timestamp (UTC): {datetime.now(timezone.utc).isoformat()}",
        f"- User question: {question}",
        f"",
        f"## Transcript",
        f"",
        f"**User:** {question}",
        f"",
    ]

    total_usage = {"input_tokens": 0, "output_tokens": 0}

    for turn in range(MAX_TURNS):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        total_usage["input_tokens"] += resp.usage.input_tokens
        total_usage["output_tokens"] += resp.usage.output_tokens

        assistant_content = []
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                log_lines.append(f"**Assistant (turn {turn}):** {block.text}\n")
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                log_lines.append(
                    f"**Assistant tool call (turn {turn}):** `{block.input.get('command')}`\n"
                )
                assistant_content.append({
                    "type": "tool_use", "id": block.id, "name": block.name, "input": block.input,
                })
                tool_calls.append(block)

        messages.append({"role": "assistant", "content": assistant_content})

        if resp.stop_reason != "tool_use":
            break

        tool_results = []
        for call in tool_calls:
            result = run_bash(call.input["command"])
            log_lines.append(f"**Tool result (turn {turn}):**\n```\n{result[:3000]}\n```\n")
            tool_results.append({
                "type": "tool_result", "tool_use_id": call.id, "content": result,
            })
        messages.append({"role": "user", "content": tool_results})

    log_lines.append(f"\n## Token usage\n\n- input_tokens: {total_usage['input_tokens']}\n- output_tokens: {total_usage['output_tokens']}\n")

    out_path = SKILL_DIR / "tests" / "live" / "transcript.md"
    out_path.write_text("\n".join(log_lines), encoding="utf-8")
    print(f"Wrote transcript to {out_path}")
    print(f"Token usage: {total_usage}")


if __name__ == "__main__":
    main()
