"""
Start every MCP server declared with a `module` in mcp_servers.yaml.

    python -m backend.tool_servers

Each server runs in its own process. The launcher waits until all local
servers are accepting connections before creating a readiness file.

Ctrl+C / SIGTERM stops all servers.
"""

from __future__ import annotations

import socket
import signal
import subprocess
import sys
import time
from pathlib import Path

from backend.agentic.tools.mcp import load_mcp_config
from backend.utils import get_logger, setup_logging

log = get_logger("tool_servers")

READY_TIMEOUT = 10.0
READY_FILE = Path("tmp/mcp_servers.ready")


def wait_for_port(
    host: str,
    port: int,
    timeout: float = READY_TIMEOUT,
) -> bool:
    """Wait until a TCP port accepts connections."""
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)

    return False


def main() -> None:
    setup_logging()

    config = load_mcp_config()
    procs: list[tuple[str, dict, subprocess.Popen]] = []

    # Remove stale readiness file from a previous run.
    READY_FILE.unlink(missing_ok=True)

    for name, cfg in config.items():
        module = cfg.get("module")
        if not module:
            continue

        host = str(cfg.get("host", "127.0.0.1"))
        port = int(cfg.get("port", 8001))

        cmd = [
            sys.executable,
            "-m",
            module,
            "--host",
            host,
            "--port",
            str(port),
        ]

        log.info(
            "Starting MCP server %s on %s:%s",
            name,
            host,
            port,
        )

        proc = subprocess.Popen(cmd)
        procs.append((name, cfg, proc))

    if not procs:
        log.info("No local MCP server to start.")
        READY_FILE.touch()
        return

    def stop(*_, exit_code: int = 0) -> None:
        READY_FILE.unlink(missing_ok=True)

        for _, _, proc in procs:
            if proc.poll() is None:
                proc.terminate()

        for _, _, proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

        sys.exit(exit_code)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    # Wait for every MCP server to become reachable.
    for name, cfg, proc in procs:
        host = str(cfg.get("host", "127.0.0.1"))
        port = int(cfg.get("port", 8001))

        log.info(
            "Waiting for MCP server %s on %s:%s...",
            name,
            host,
            port,
        )

        if proc.poll() is not None:
            log.error(
                "MCP server %s exited with code %s before becoming ready.",
                name,
                proc.returncode,
            )
            stop(exit_code=1)

        if not wait_for_port(host, port):
            log.error(
                "MCP server %s did not become ready within %.1f seconds.",
                name,
                READY_TIMEOUT,
            )
            stop(exit_code=1)

        if proc.poll() is not None:
            log.error(
                "MCP server %s exited with code %s after becoming ready.",
                name,
                proc.returncode,
            )
            stop(exit_code=1)

        log.info("MCP server %s is ready.", name)

    # All MCP servers are ready.
    READY_FILE.parent.mkdir(parents=True, exist_ok=True)
    READY_FILE.touch()

    log.info("All MCP servers are ready.")

    # Keep supervising the child processes.
    while True:
        for name, _, proc in procs:
            if proc.poll() is not None:
                log.error(
                    "MCP server %s exited with code %s.",
                    name,
                    proc.returncode,
                )
                stop(exit_code=1)

        time.sleep(1)


if __name__ == "__main__":
    main()