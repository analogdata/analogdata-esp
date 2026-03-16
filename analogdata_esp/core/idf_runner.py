"""
Core helper for running idf.py commands with the correct environment.

Sets up IDF_PATH, PATH (venv + toolchains), and other required env vars
so commands work without the user having to source export.sh first.
"""

from __future__ import annotations

import os            # os.environ, os.pathsep for PATH manipulation
import subprocess    # Popen for streaming, run() for interactive commands
import sys           # sys.platform for Windows/Linux/macOS detection
from pathlib import Path
from typing import Iterator, Optional

from analogdata_esp.core.config import detect_idf, IDFConfig

# ─────────────────────────────────────────────────────────────────────────────
# Environment builder
# ─────────────────────────────────────────────────────────────────────────────

# Same two tools roots as in config.py — checked in order; first non-empty wins
_TOOLS_ROOTS = [
    Path.home() / ".espressif" / "tools",
    Path.home() / ".espressifforwindsurf" / "tools",
]


def build_idf_env(cfg: Optional[IDFConfig] = None) -> dict:
    """Return an env dict suitable for running idf.py without sourcing export.sh.

    Mirrors what `source $IDF_PATH/export.sh` does:
      - Sets IDF_PATH so idf.py knows where the framework lives.
      - Sets IDF_TOOLS_PATH so idf.py knows where its tools are.
      - Sets IDF_PYTHON_ENV_PATH so idf.py uses its own virtualenv.
      - Prepends the virtualenv bin/ AND all toolchain bin/ dirs to PATH
        so gcc, objcopy, esptool etc. are all found automatically.

    Args:
        cfg: IDFConfig to use. None → call detect_idf() automatically.

    Returns:
        A copy of os.environ with the extra IDF-specific entries merged in.
        If cfg.is_valid is False, returns os.environ unchanged (best-effort).
    """
    cfg = cfg or detect_idf()
    env = os.environ.copy()   # start from a copy so we don't mutate the real environment

    if not cfg.is_valid:
        # Can't set up a proper environment — let idf.py fail with its own error message
        return env

    # Tell idf.py where the ESP-IDF source tree is
    env["IDF_PATH"] = str(cfg.idf_path)

    # Find which tools root directory actually has content
    tools_root = None
    for root in _TOOLS_ROOTS:
        if root.exists() and any(root.iterdir()):   # non-empty directory
            tools_root = root
            break

    if tools_root:
        # IDF_TOOLS_PATH is the parent of tools/ — i.e. ~/.espressif
        idf_tools_path = tools_root.parent
        env["IDF_TOOLS_PATH"] = str(idf_tools_path)

        # IDF_PYTHON_ENV_PATH points to the Python virtualenv that idf.py should use.
        # This is typically: ~/.espressif/python_env/idf5.5_py3.11_env/
        python_env_path: Optional[Path] = None
        if cfg.python_path and cfg.python_path.exists():
            # cfg.python_path = .../python_env/idf5.x_pyY.Z_env/bin/python3
            # Go up two levels: bin/ → idf5.x_pyY.Z_env/ → the virtualenv root
            candidate = cfg.python_path.parent.parent
            # A valid virtualenv contains pyvenv.cfg OR a bin/ directory
            if (candidate / "pyvenv.cfg").exists() or (candidate / "bin").is_dir():
                python_env_path = candidate
        if python_env_path is None:
            # Glob fallback: find the newest env under ~/.espressif/python_env/
            py_env_root = idf_tools_path / "python_env"
            if py_env_root.is_dir():
                for e in sorted(py_env_root.iterdir(), reverse=True):
                    if e.is_dir():
                        python_env_path = e
                        break
        if python_env_path:
            env["IDF_PYTHON_ENV_PATH"] = str(python_env_path)

    # Build the list of directories to prepend to PATH
    extra_paths = []

    # 1. Python venv bin/ — ensures `python` resolves to the IDF venv python
    if cfg.python_path and cfg.python_path.exists():
        extra_paths.append(str(cfg.python_path.parent))   # cfg.python_path is .../bin/python3

    # 2. All toolchain bin/ directories (xtensa, riscv32, openocd, etc.)
    #    Structure: <tools_root>/<tool-name>/<version>/<tool-name>/bin/
    #    We add only the newest version of each tool.
    if tools_root:
        for tool_dir in sorted(tools_root.iterdir()):
            if not tool_dir.is_dir():
                continue
            # Walk version dirs in reverse sorted order → newest version first
            for version_dir in sorted(tool_dir.iterdir(), reverse=True):
                if not version_dir.is_dir():
                    continue
                bin_dir = version_dir / tool_dir.name / "bin"
                if bin_dir.is_dir():
                    extra_paths.append(str(bin_dir))
                    break   # stop after adding the newest version

    if extra_paths:
        # Prepend to PATH so our tools take precedence over any system versions
        env["PATH"] = os.pathsep.join(extra_paths) + os.pathsep + env.get("PATH", "")

    return env


def idf_py_cmd(cfg: IDFConfig) -> list[str]:
    """Return the command list for running idf.py: [python, idf.py].

    We always invoke idf.py via Python explicitly rather than as a bare
    script, because idf.py has a shebang pointing to the system python
    which may not have ESP-IDF's dependencies installed.

    Args:
        cfg: IDFConfig with idf_path and python_path set.

    Returns:
        E.g. ["/home/user/.espressif/python_env/.../python3",
               "/home/user/esp/esp-idf/tools/idf.py"]
    """
    idf_py = str(cfg.idf_path / "tools" / "idf.py")
    # Use the venv Python if it exists; fall back to the Python running this process
    python = str(cfg.python_path) if (cfg.python_path and cfg.python_path.exists()) else sys.executable
    return [python, idf_py]


# ─────────────────────────────────────────────────────────────────────────────
# Serial port detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_serial_ports() -> list[str]:
    """Return connected ESP32 serial ports, sorted most-likely first.

    Different platforms expose serial ports differently:
      - macOS: /dev/tty.usbserial-* (CP2102, CH340), /dev/tty.SLAB_USBtoUART*
      - Linux: /dev/ttyUSB* (USB-UART), /dev/ttyACM* (CDC)
      - Windows: COM ports via pyserial (if installed)

    Returns:
        List of port device strings, e.g. ["/dev/tty.usbserial-0001"].
        Empty list if nothing is connected or detected.
    """
    candidates: list[str] = []

    if sys.platform == "darwin":
        dev = Path("/dev")
        # Common USB-UART bridge chips found on ESP32 dev boards:
        #   CP2102/CP2104 → tty.usbserial-*
        #   CH340/CH341   → tty.usbserial-* or tty.wch*
        #   SLAB          → tty.SLAB_USBtoUART*
        #   USB CDC       → tty.usbmodem*
        for pat in ("tty.usbserial-*", "tty.SLAB_USBtoUART*", "tty.wch*", "tty.usbmodem*"):
            candidates.extend(str(p) for p in sorted(dev.glob(pat)))

    elif sys.platform.startswith("linux"):
        dev = Path("/dev")
        # USB-UART adapters → ttyUSB*, USB CDC → ttyACM*, hardware UART → ttyS*
        for pat in ("ttyUSB*", "ttyACM*", "ttyS*"):
            candidates.extend(str(p) for p in sorted(dev.glob(pat)))

    elif sys.platform == "win32":
        # Windows doesn't use /dev — use pyserial's port lister if available
        try:
            import serial.tools.list_ports  # type: ignore
            candidates = [p.device for p in serial.tools.list_ports.comports()]
        except ImportError:
            pass   # pyserial not installed — return empty list

    return candidates


def pick_port(port_override: Optional[str] = None) -> Optional[str]:
    """Return the port to use for flash/monitor.

    If the user specified --port, use that exactly.
    Otherwise, auto-detect: return the first port from detect_serial_ports().

    Args:
        port_override: Explicit port string from --port flag, or None.

    Returns:
        Port string to use, or None if nothing found.
    """
    if port_override:
        return port_override   # always trust explicit user input
    ports = detect_serial_ports()
    return ports[0] if ports else None   # first detected port, or None


# ─────────────────────────────────────────────────────────────────────────────
# Runners
# ─────────────────────────────────────────────────────────────────────────────

def run_idf_streaming(
    args: list[str],
    cwd: Path,
    cfg: Optional[IDFConfig] = None,
) -> Iterator[str]:
    """Run `idf.py <args>` and yield output lines as they arrive (streaming).

    Used for `build` so the user sees compiler output in real-time instead
    of waiting for the full build to finish before seeing any output.

    Combines stdout and stderr into a single stream (stderr=STDOUT) so
    error messages appear in context with the build output that preceded them.

    If the process exits non-zero, a final "[exit code N]" line is yielded
    so the caller can detect failure by checking for that prefix.

    Args:
        args: idf.py sub-commands and flags, e.g. ["build", "-j8"].
        cwd:  Project directory (must contain CMakeLists.txt).
        cfg:  IDFConfig to use. None → auto-detect.

    Yields:
        Lines of output (whitespace stripped) as they arrive from idf.py.
    """
    cfg = cfg or detect_idf()
    env = build_idf_env(cfg)         # environment with IDF_PATH, PATH etc.
    cmd = idf_py_cmd(cfg) + args     # [python, idf.py, "build", ...]

    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,      # capture stdout so we can yield it line by line
        stderr=subprocess.STDOUT,    # merge stderr into stdout stream
        text=True,                   # decode bytes to str automatically
        bufsize=1,                   # line-buffered: yield each line as it's written
    )
    assert proc.stdout is not None   # always true after Popen with PIPE, satisfies type checker
    for line in proc.stdout:
        yield line.rstrip()   # strip trailing newline; keep leading indent
    proc.wait()               # wait for process to finish fully before signalling done
    if proc.returncode != 0:
        # Signal failure to the caller without raising an exception
        yield f"\n[exit code {proc.returncode}]"


def run_idf_interactive(
    args: list[str],
    cwd: Path,
    cfg: Optional[IDFConfig] = None,
) -> int:
    """Run `idf.py <args>` interactively — inherits the real terminal.

    Used for `flash`, `monitor`, `menuconfig`, and `flash monitor` where
    the user needs to interact with the program directly:
      - flash: shows esptool progress bars which require a real terminal
      - monitor: needs keyboard input (Ctrl+] to exit)
      - menuconfig: ncurses full-screen UI

    Unlike run_idf_streaming(), stdout/stderr are NOT captured — they go
    directly to the user's terminal so the full interactive experience works.

    Args:
        args: idf.py sub-commands and flags.
        cwd:  Project directory.
        cfg:  IDFConfig to use. None → auto-detect.

    Returns:
        Exit code from idf.py (0 = success, non-zero = error, 130 = Ctrl+C).
    """
    cfg = cfg or detect_idf()
    env = build_idf_env(cfg)
    cmd = idf_py_cmd(cfg) + args

    # subprocess.run() with no stdout/stderr redirect inherits the parent's terminal
    result = subprocess.run(cmd, cwd=str(cwd), env=env)
    return result.returncode
