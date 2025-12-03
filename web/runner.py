from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass
class CommandResult:
    argv: list[str]
    stdout: str
    stderr: str
    returncode: int
    error: str | None = None

    @property
    def command_line(self) -> str:
        return shlex.join(self.argv)


class RustStripeRunner:
    """Helper that shells out to the Rust CLI so the web UI can reuse it."""

    def __init__(
        self,
        rust_dir: str | Path,
        *,
        binary_hint: str | Path | None = None,
        timeout: int = 300,
    ) -> None:
        self.rust_dir = Path(rust_dir).resolve()
        self.manifest_path = self.rust_dir / "Cargo.toml"
        self.timeout = timeout
        self.binary_path = self._resolve_binary(binary_hint)

    def _resolve_binary(self, binary_hint: str | Path | None) -> Path | None:
        """Prefer an existing compiled binary, but fall back to cargo run."""
        candidates: list[Path] = []
        env_path = os.environ.get("STRIPE_TESTBED_BIN")
        if env_path:
            candidates.append(Path(env_path).expanduser())
        if binary_hint:
            candidates.append(Path(binary_hint).expanduser())
        candidates.extend(
            [
                self.rust_dir / "target" / "release" / "stripe-testbed",
                self.rust_dir / "target" / "debug" / "stripe-testbed",
            ]
        )
        for path in candidates:
            if path.is_file():
                return path
        return None

    def run(
        self,
        command: str,
        *,
        extra_args: Sequence[str] | None = None,
        config_path: str | Path | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        args: list[str] = []
        if config_path:
            args.extend(["--config", str(config_path)])
        args.append(command)
        if extra_args:
            args.extend(extra_args)

        if self.binary_path:
            full_cmd = [str(self.binary_path), *args]
        else:
            full_cmd = [
                "cargo",
                "run",
                "--quiet",
                "--manifest-path",
                str(self.manifest_path),
                "--",
                *args,
            ]

        cmd_env = os.environ.copy()
        if env:
            cmd_env.update(env)

        try:
            completed = subprocess.run(
                full_cmd,
                cwd=self.rust_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=cmd_env,
            )
            return CommandResult(
                argv=full_cmd,
                stdout=completed.stdout,
                stderr=completed.stderr,
                returncode=completed.returncode,
            )
        except FileNotFoundError as exc:
            return CommandResult(
                argv=full_cmd,
                stdout="",
                stderr="",
                returncode=127,
                error=f"Unable to execute command: {exc}",
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                argv=full_cmd,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                returncode=-1,
                error=f"Command timed out after {self.timeout} seconds",
            )


