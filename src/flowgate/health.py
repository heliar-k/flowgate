from __future__ import annotations

import os
import shutil
import socket
from pathlib import Path
from typing import Any, Literal, TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


class HttpHealthResult(TypedDict):
    ok: bool
    status_code: int | None
    error: str | None


HealthStatus = Literal["healthy", "degraded", "unhealthy"]


class HealthCheckResult(TypedDict):
    """Result of a health check operation."""

    status: HealthStatus
    message: str
    details: dict[str, Any]


def check_http_health(url: str, *, timeout: float = 1.0) -> HttpHealthResult:
    try:
        with urlopen(url, timeout=timeout) as response:  # nosec B310
            return {
                "ok": 200 <= response.status < 300,
                "status_code": response.status,
                "error": None,
            }
    except HTTPError as exc:
        return {"ok": False, "status_code": exc.code, "error": None}
    except (TimeoutError, URLError, OSError) as exc:
        return {"ok": False, "status_code": None, "error": type(exc).__name__}


def check_health_url(url: str, *, timeout: float = 1.0) -> bool:
    # Backward-compatible helper kept for existing call sites/tests.
    return check_http_health(url, timeout=timeout)["ok"]


def check_disk_space(
    path: str | Path, threshold_percent: int = 20
) -> HealthCheckResult:
    """Check available disk space for a given path.

    Args:
        path: Directory path to check
        threshold_percent: Minimum free space percentage (default: 20%)

    Returns:
        HealthCheckResult with status and disk space details
    """
    try:
        path_obj = Path(path).resolve()
        if not path_obj.exists():
            return {
                "status": "unhealthy",
                "message": f"Path does not exist: {path_obj}",
                "details": {"path": str(path_obj), "exists": False},
            }

        stat = shutil.disk_usage(path_obj)
        total_gb = stat.total / (1024**3)
        used_gb = stat.used / (1024**3)
        free_gb = stat.free / (1024**3)
        free_percent = (stat.free / stat.total) * 100 if stat.total > 0 else 0

        details = {
            "path": str(path_obj),
            "total_gb": round(total_gb, 2),
            "used_gb": round(used_gb, 2),
            "free_gb": round(free_gb, 2),
            "free_percent": round(free_percent, 1),
            "threshold_percent": threshold_percent,
        }

        if free_percent < threshold_percent:
            return {
                "status": "degraded",
                "message": f"Low disk space: {free_percent:.1f}% free (threshold: {threshold_percent}%)",
                "details": details,
            }

        return {
            "status": "healthy",
            "message": f"Disk space OK: {free_percent:.1f}% free",
            "details": details,
        }

    except (OSError, IOError) as exc:
        return {
            "status": "unhealthy",
            "message": f"Failed to check disk space: {exc}",
            "details": {"path": str(path), "error": str(exc)},
        }


def check_memory_usage() -> HealthCheckResult:
    """Check system memory usage.

    Returns:
        HealthCheckResult with memory usage details
    """
    try:
        # Try to use psutil if available
        try:
            import psutil  # type: ignore

            mem = psutil.virtual_memory()
            total_gb = mem.total / (1024**3)
            used_gb = mem.used / (1024**3)
            available_gb = mem.available / (1024**3)
            percent_used = mem.percent

            details = {
                "total_gb": round(total_gb, 2),
                "used_gb": round(used_gb, 2),
                "available_gb": round(available_gb, 2),
                "percent_used": round(percent_used, 1),
            }

            if percent_used > 90:
                return {
                    "status": "degraded",
                    "message": f"High memory usage: {percent_used:.1f}%",
                    "details": details,
                }

            return {
                "status": "healthy",
                "message": f"Memory usage OK: {percent_used:.1f}%",
                "details": details,
            }

        except ImportError:
            # Fallback: read /proc/meminfo on Linux
            if Path("/proc/meminfo").exists():
                with Path("/proc/meminfo").open() as f:
                    lines = f.readlines()
                mem_info = {}
                for line in lines:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip().split()[0]
                        mem_info[key] = int(value)

                total_kb = mem_info.get("MemTotal", 0)
                available_kb = mem_info.get("MemAvailable", mem_info.get("MemFree", 0))
                used_kb = total_kb - available_kb

                total_gb = total_kb / (1024**2)
                used_gb = used_kb / (1024**2)
                available_gb = available_kb / (1024**2)
                percent_used = (used_kb / total_kb * 100) if total_kb > 0 else 0

                details = {
                    "total_gb": round(total_gb, 2),
                    "used_gb": round(used_gb, 2),
                    "available_gb": round(available_gb, 2),
                    "percent_used": round(percent_used, 1),
                }

                if percent_used > 90:
                    return {
                        "status": "degraded",
                        "message": f"High memory usage: {percent_used:.1f}%",
                        "details": details,
                    }

                return {
                    "status": "healthy",
                    "message": f"Memory usage OK: {percent_used:.1f}%",
                    "details": details,
                }

            # No memory info available
            return {
                "status": "healthy",
                "message": "Memory check not available on this platform",
                "details": {"available": False},
            }

    except Exception as exc:  # noqa: BLE001
        return {
            "status": "unhealthy",
            "message": f"Failed to check memory: {exc}",
            "details": {"error": str(exc)},
        }


def check_port_availability(host: str, port: int) -> HealthCheckResult:
    """Check if a port is available (not in use).

    Args:
        host: Host address to check
        port: Port number to check

    Returns:
        HealthCheckResult indicating if port is available
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        result = sock.connect_ex((host, port))
        sock.close()

        if result == 0:
            # Port is in use
            return {
                "status": "unhealthy",
                "message": f"Port {port} is already in use",
                "details": {"host": host, "port": port, "in_use": True},
            }

        # Port is available
        return {
            "status": "healthy",
            "message": f"Port {port} is available",
            "details": {"host": host, "port": port, "in_use": False},
        }

    except socket.error as exc:
        return {
            "status": "unhealthy",
            "message": f"Failed to check port {port}: {exc}",
            "details": {"host": host, "port": port, "error": str(exc)},
        }


def check_credentials(config: dict[str, Any]) -> HealthCheckResult:
    """Check that all credential files exist and are readable.

    Args:
        config: FlowGate configuration dictionary

    Returns:
        HealthCheckResult with credential validation status
    """
    credentials = config.get("credentials", {})
    if not isinstance(credentials, dict):
        return {
            "status": "healthy",
            "message": "No credentials configured",
            "details": {"configured": False},
        }

    upstream = credentials.get("upstream", {})
    if not isinstance(upstream, dict) or not upstream:
        return {
            "status": "healthy",
            "message": "No upstream credentials configured",
            "details": {"configured": False},
        }

    issues = []
    checked = 0

    for name, entry in upstream.items():
        if not isinstance(entry, dict):
            continue

        file_path = entry.get("file")
        if not isinstance(file_path, str) or not file_path.strip():
            continue

        checked += 1
        cred_path = Path(file_path)

        if not cred_path.exists():
            issues.append(f"{name}: file not found ({cred_path})")
            continue

        if not cred_path.is_file():
            issues.append(f"{name}: not a file ({cred_path})")
            continue

        try:
            content = cred_path.read_text(encoding="utf-8").strip()
            if not content:
                issues.append(f"{name}: file is empty ({cred_path})")
        except (OSError, IOError) as exc:
            issues.append(f"{name}: cannot read file ({exc})")

    details = {"checked": checked, "issues": len(issues), "issue_list": issues}

    if issues:
        return {
            "status": "unhealthy",
            "message": f"Credential issues found: {len(issues)} of {checked}",
            "details": details,
        }

    if checked == 0:
        return {
            "status": "healthy",
            "message": "No credentials to check",
            "details": details,
        }

    return {
        "status": "healthy",
        "message": f"All {checked} credentials valid",
        "details": details,
    }


def check_service_ports(config: dict[str, Any]) -> HealthCheckResult:
    """Check for port conflicts in service configuration.

    Args:
        config: FlowGate configuration dictionary

    Returns:
        HealthCheckResult indicating if there are port conflicts
    """
    services = config.get("services", {})
    if not isinstance(services, dict):
        return {
            "status": "healthy",
            "message": "No services configured",
            "details": {"configured": False},
        }

    port_map: dict[int, list[str]] = {}
    for name, service in services.items():
        if not isinstance(service, dict):
            continue

        port = service.get("port")
        if isinstance(port, int):
            if port not in port_map:
                port_map[port] = []
            port_map[port].append(name)

    conflicts = {port: names for port, names in port_map.items() if len(names) > 1}

    details = {
        "total_services": len(services),
        "ports_used": len(port_map),
        "conflicts": conflicts,
    }

    if conflicts:
        conflict_desc = ", ".join(
            f"port {port}: {', '.join(names)}" for port, names in conflicts.items()
        )
        return {
            "status": "unhealthy",
            "message": f"Port conflicts detected: {conflict_desc}",
            "details": details,
        }

    return {
        "status": "healthy",
        "message": f"No port conflicts ({len(port_map)} ports used)",
        "details": details,
    }


def comprehensive_health_check(
    config: dict[str, Any], *, verbose: bool = False
) -> dict[str, Any]:
    """Run all health checks and return comprehensive status.

    Args:
        config: FlowGate configuration dictionary
        verbose: Include detailed information in output

    Returns:
        Dictionary with overall status and individual check results
    """
    checks: dict[str, HealthCheckResult] = {}

    # Check disk space for runtime directory
    runtime_dir = config.get("paths", {}).get("runtime_dir", ".router")
    checks["disk_space"] = check_disk_space(runtime_dir)

    # Check memory usage
    checks["memory"] = check_memory_usage()

    # Check credentials
    checks["credentials"] = check_credentials(config)

    # Check for port conflicts
    checks["port_conflicts"] = check_service_ports(config)

    # Determine overall status
    statuses = [check["status"] for check in checks.values()]
    if any(s == "unhealthy" for s in statuses):
        overall_status: HealthStatus = "unhealthy"
    elif any(s == "degraded" for s in statuses):
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    # Count by status
    status_counts = {
        "healthy": sum(1 for s in statuses if s == "healthy"),
        "degraded": sum(1 for s in statuses if s == "degraded"),
        "unhealthy": sum(1 for s in statuses if s == "unhealthy"),
    }

    result = {
        "overall_status": overall_status,
        "status_counts": status_counts,
        "checks": checks,
    }

    if not verbose:
        # Remove detailed information in non-verbose mode
        for check in checks.values():
            check["details"] = {}

    return result
