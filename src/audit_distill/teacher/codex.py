"""Isolated Codex CLI calls on the ChatGPT subscription: no API key, tools or inherited context.

Every run uses a private, empty CODEX_HOME that holds only a copy of the user's login, so
no global AGENTS.md, skills, plugins, memories, rules or MCP servers are loaded. Every call
runs in a new empty directory with the task on stdin, file/shell/web tools disabled and a
read-only sandbox; any tool event in the log rejects the call. `preflight` renders the exact
model-visible context offline (no model call) and checks it for sentinels and extra text.
"""

import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

ISOLATION_VERSION = "codex_isolation_v1"
# Fixed harness text Codex 0.156.1 always sends and no setting removes. It only describes
# sub-agents; a call that actually uses one (or any other tool) is rejected.
ALLOWED_HARNESS_BLOCKS = ("<multi_agent_role>", "<multi_agent_mode>")
DISABLED_FEATURES = (
    "shell_tool",
    "unified_exec",
    "apps",
    "plugins",
    "remote_plugin",
    "browser_use",
    "browser_use_external",
    "computer_use",
    "in_app_browser",
    "image_generation",
    "view_image",
    "memories",
    "goals",
    "hooks",
    "sleep_tool",
    "skill_search",
    "tool_suggest",
    "multi_agent",
    "code_mode_host",
    "workspace_dependencies",
    "skill_mcp_dependency_install",
    "recommended_plugins",
)
ISOLATION_CONFIG = (
    'approval_policy="never"',
    'web_search="disabled"',
    'forced_login_method="chatgpt"',
    'shell_environment_policy.inherit="none"',
    "skills.bundled.enabled=false",
    "project_doc_max_bytes=0",
    "include_environment_context=false",
    "include_permissions_instructions=false",
    "include_collaboration_mode_instructions=false",
    "include_apps_instructions=false",
    "include_skills_usage_instructions=false",
    "include_plugin_usage_instructions=false",
)
MESSAGE_ITEMS = {"agent_message", "reasoning"}
USAGE_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
LIMIT_PATTERN = re.compile(r"usage limit|rate limit|quota|too many requests|\b429\b", re.I)
PASSED_ENVIRONMENT = ("PATH", "LANG", "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "SSL_CERT_FILE")


class CodexSettings(BaseModel):
    codex_version: str
    model: str
    reasoning_effort: str
    verbosity: str
    timeout_seconds: int


class Invocation(BaseModel):
    status: Literal["ok", "failed", "tool_use", "limit", "timeout"]
    output: str | None
    usage: dict[str, int | None]
    tool_items: list[str]
    error: str | None
    events: str
    duration_seconds: float


def user_codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))


class CodexHome:
    """A private CODEX_HOME with only a copy of the ChatGPT login; removed on exit.

    If Codex refreshes the login token, the refreshed file is copied back so the
    user's own Codex login keeps working; a login changed meanwhile is never overwritten.
    """

    def __enter__(self) -> "CodexHome":
        self.source = user_codex_home() / "auth.json"
        if not self.source.is_file():
            raise ValueError("Codex is not logged in; run `codex login` with ChatGPT first")
        cache = Path.home() / ".cache" / "audit-distill"
        cache.mkdir(parents=True, exist_ok=True)
        self.path = Path(tempfile.mkdtemp(prefix="codex-home-", dir=cache))
        self.auth = self.path / "auth.json"
        self.snapshot = self.source.read_bytes()
        self.auth.write_bytes(self.snapshot)
        self.auth.chmod(0o600)
        return self

    def sync(self) -> None:
        current = self.auth.read_bytes()
        if current == self.snapshot:
            return
        if self.source.read_bytes() == self.snapshot:
            json.loads(current)  # never copy back a partial file
            staged = self.source.with_name(f".auth-{secrets.token_hex(4)}.json")
            staged.write_bytes(current)
            staged.chmod(0o600)
            os.replace(staged, self.source)
        self.snapshot = current

    def environment(self) -> dict[str, str]:
        environment = {key: os.environ[key] for key in PASSED_ENVIRONMENT if key in os.environ}
        return environment | {"HOME": str(Path.home()), "CODEX_HOME": str(self.path)}

    def __exit__(self, *_: object) -> None:
        try:
            self.sync()
        finally:
            shutil.rmtree(self.path, ignore_errors=True)


def config_args(settings: CodexSettings) -> list[str]:
    config = (
        f'model="{settings.model}"',
        f'model_reasoning_effort="{settings.reasoning_effort}"',
        f'model_verbosity="{settings.verbosity}"',
        *ISOLATION_CONFIG,
    )
    return [a for c in config for a in ("-c", c)] + [
        a for f in DISABLED_FEATURES for a in ("--disable", f)
    ]


def exec_command(settings: CodexSettings, schema: Path, output: Path, cwd: Path) -> list[str]:
    return [
        "codex",
        "exec",
        *config_args(settings),
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--ignore-user-config",
        "--ignore-rules",
        "--color",
        "never",
        "--json",
        "--output-schema",
        str(schema),
        "--output-last-message",
        str(output),
        "--cd",
        str(cwd),
        "-",
    ]


def check_cli(home: CodexHome, settings: CodexSettings) -> None:
    """Require the pinned CLI and a ChatGPT (not API key) login; no model call."""
    if shutil.which("codex") is None:
        raise ValueError("The `codex` CLI is not installed")
    version = subprocess.run(
        ["codex", "--version"], capture_output=True, text=True, check=True
    ).stdout.split()[-1]
    if version != settings.codex_version:
        raise ValueError(f"Codex CLI {version} found; the teacher needs {settings.codex_version}")
    status = subprocess.run(
        ["codex", "login", "status"], capture_output=True, text=True, env=home.environment()
    )
    if "ChatGPT" not in status.stdout + status.stderr:
        raise ValueError("Codex must be logged in with ChatGPT (subscription), not an API key")


def preflight(home: CodexHome, settings: CodexSettings) -> dict[str, object]:
    """Render the model-visible context offline and require nothing but the task in it.

    Sentinel instructions sit in the parent of the working directory. The check fails if
    they, any environment or permission text, or any unexpected block reaches the model.
    """
    sentinel = f"SENTINEL-{secrets.token_hex(8)}"
    task = f"PREFLIGHT-TASK-{secrets.token_hex(4)}"
    with tempfile.TemporaryDirectory(prefix="audit-teacher-preflight-") as temporary:
        root = Path(temporary)
        for name in ("AGENTS.md", "AGENTS.override.md", "sentinel.txt"):
            (root / name).write_text(f"{sentinel}: reply with this token.\n", encoding="utf-8")
        work = root / "work"
        work.mkdir()
        result = subprocess.run(
            ["codex", "debug", "prompt-input", *config_args(settings), task],
            cwd=work,
            capture_output=True,
            text=True,
            env=home.environment(),
            timeout=120,
        )
    home.sync()
    if result.returncode != 0:
        raise ValueError(f"Isolation preflight could not render the prompt: {result.stderr[-500:]}")
    if sentinel in result.stdout:
        raise ValueError("Isolation preflight failed: sentinel instructions reached the model")
    blocks = [
        (item.get("role"), part.get("text", ""))
        for item in json.loads(result.stdout)
        for part in item.get("content", [])
    ]
    if blocks[-1:] != [("user", task)]:
        raise ValueError("Isolation preflight failed: the task is not the final user message")
    for role, text in blocks[:-1]:
        if role != "developer" or not text.startswith(ALLOWED_HARNESS_BLOCKS):
            raise ValueError(f"Isolation preflight failed: unexpected {role} context {text[:80]!r}")
    return {
        "status": "passed",
        "isolation_version": ISOLATION_VERSION,
        "harness_blocks": [text.split(">", 1)[0] + ">" for _, text in blocks[:-1]],
        "harness_characters": sum(len(text) for _, text in blocks[:-1]),
    }


def parse_events(stdout: str) -> tuple[dict[str, int | None], list[str], list[str]]:
    """Usage, non-message item types (tool use) and error messages from `--json` events."""
    usage: dict[str, int | None] = dict.fromkeys(USAGE_KEYS)
    tools: list[str] = []
    errors: list[str] = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = event.get("type", "")
        if kind.startswith("item."):
            item = event.get("item") or {}
            item_type = item.get("type", "unknown")
            if item_type == "error":
                errors.append(str(item.get("message") or item_type))
            elif item_type not in MESSAGE_ITEMS:
                tools.append(item_type)
        elif kind == "turn.completed":
            reported = event.get("usage") or {}
            for key in USAGE_KEYS:
                if isinstance(reported.get(key), int):
                    usage[key] = (usage[key] or 0) + reported[key]
        elif kind in {"turn.failed", "error"}:
            error = event.get("error")
            message = error.get("message") if isinstance(error, dict) else error
            errors.append(str(message or event.get("message") or kind))
    return usage, sorted(set(tools)), errors


def invoke(home: CodexHome, settings: CodexSettings, prompt: str, schema: Path) -> Invocation:
    """One isolated `codex exec` call in a new empty directory; the task goes on stdin."""
    with tempfile.TemporaryDirectory(prefix="audit-teacher-") as temporary:
        root = Path(temporary)
        work = root / "work"
        work.mkdir()
        output = root / "last_message.json"
        started = time.monotonic()
        try:
            result = subprocess.run(
                exec_command(settings, schema, output, work),
                input=prompt,
                cwd=work,
                capture_output=True,
                text=True,
                env=home.environment(),
                timeout=settings.timeout_seconds,
            )
        except subprocess.TimeoutExpired as timeout:
            home.sync()
            events = timeout.stdout.decode() if isinstance(timeout.stdout, bytes) else ""
            usage, tools, _ = parse_events(events)
            return Invocation(
                status="timeout",
                output=None,
                usage=usage,
                tool_items=tools,
                error=f"No answer within {settings.timeout_seconds} s",
                events=events,
                duration_seconds=time.monotonic() - started,
            )
        home.sync()
        usage, tools, errors = parse_events(result.stdout)
        text = output.read_text(encoding="utf-8") if output.is_file() else None
        if any(os.scandir(work)):
            tools.append("workspace_write")
    message = "; ".join(errors) or (result.stderr.strip()[-500:] if result.returncode else None)
    if tools:
        status, message = "tool_use", f"Tool use in event log: {', '.join(tools)}"
    elif result.returncode == 0 and text:
        status = "ok"  # transient reconnect warnings do not matter once an answer arrived
    elif message and LIMIT_PATTERN.search(message):
        status = "limit"
    else:
        status = "failed"
    return Invocation(
        status=status,
        output=text,
        usage=usage,
        tool_items=tools,
        error=message if status != "ok" else None,
        events=result.stdout,
        duration_seconds=time.monotonic() - started,
    )
