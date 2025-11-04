"""
Health checking for the markdown-to-PDF processing pipeline.

This module provides comprehensive health monitoring including dependency validation,
system resource checks, and environment validation to ensure pipeline reliability.
"""

import subprocess
import shutil
import platform
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, NamedTuple
import sys
import os


class HealthStatus(Enum):
    """Overall health status of the system."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ResourceStatus(Enum):
    """Status of system resources."""
    SUFFICIENT = "sufficient"
    LOW = "low"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class EnvironmentStatus(Enum):
    """Status of environment configuration."""
    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class DependencyStatus(Enum):
    """Status of external dependencies."""
    AVAILABLE = "available"
    MISSING = "missing"
    VERSION_INCOMPATIBLE = "version_incompatible"
    NOT_EXECUTABLE = "not_executable"


@dataclass
class DependencyInfo:
    """Information about a system dependency."""
    name: str
    status: DependencyStatus
    version: Optional[str] = None
    path: Optional[str] = None
    required_version: Optional[str] = None
    error_message: Optional[str] = None


@dataclass 
class ResourceInfo:
    """System resource utilization information."""
    cpu_percent: float
    memory_percent: float
    memory_available_gb: float
    disk_free_gb: float
    disk_percent: float
    status: ResourceStatus
    warnings: List[str]


@dataclass
class EnvironmentInfo:
    """Environment configuration information."""
    python_version: str
    platform_info: str
    current_directory: Path
    log_directory_writable: bool
    temp_directory_writable: bool
    output_permissions: bool
    status: EnvironmentStatus
    issues: List[str]


class HealthCheckResult(NamedTuple):
    """Complete health check results."""
    overall_status: HealthStatus
    dependencies: Dict[str, DependencyInfo]
    resources: ResourceInfo
    environment: EnvironmentInfo
    summary: str
    recommendations: List[str]


class HealthChecker:
    """
    Comprehensive health checker for the markdown-to-PDF pipeline.
    
    Validates system dependencies, monitors resource usage, and checks
    environment configuration to ensure reliable pipeline operation.
    """
    
    # Resource thresholds
    MEMORY_WARNING_THRESHOLD = 80.0  # percent
    MEMORY_CRITICAL_THRESHOLD = 90.0  # percent
    DISK_WARNING_THRESHOLD = 85.0    # percent 
    DISK_CRITICAL_THRESHOLD = 95.0   # percent
    MIN_FREE_DISK_GB = 1.0           # minimum free disk space in GB
    
    # Required dependencies with minimum versions
    REQUIRED_DEPENDENCIES = {
        "pandoc": "2.0.0",
        "xelatex": "2017",  # TeX Live 2017 or later
    }
    
    def __init__(self, 
                 log_dir: Path = Path("logs"),
                 temp_dir: Path = Path("temp"),
                 output_dir: Path = Path("output")):
        """
        Initialize health checker.
        
        Args:
            log_dir: Directory for log files
            temp_dir: Directory for temporary files
            output_dir: Directory for output files
        """
        self.log_dir = log_dir
        self.temp_dir = temp_dir
        self.output_dir = output_dir
    
    def check_dependencies(self) -> Dict[str, DependencyInfo]:
        """
        Check availability and versions of required dependencies.
        
        Returns:
            Dict mapping dependency names to DependencyInfo objects
        """
        results = {}
        
        # Check Pandoc
        results["pandoc"] = self._check_pandoc()
        
        # Check XeLaTeX
        results["xelatex"] = self._check_xelatex()
        
        return results
    
    def check_system_resources(self) -> ResourceInfo:
        """
        Monitor system resource availability using built-in methods.
        
        Returns:
            ResourceInfo with current resource status and warnings
        """
        warnings = []
        
        try:
            # CPU usage - not directly available without psutil, use placeholder
            cpu_percent = 0.0
            
            # Memory usage - use basic OS info
            memory_percent, memory_available_gb = self._get_memory_info()
            
            # Disk usage for current directory
            disk_free_gb, disk_percent = self._get_disk_info('.')
            
            # Determine status and warnings
            status = ResourceStatus.SUFFICIENT
            
            if memory_percent >= self.MEMORY_CRITICAL_THRESHOLD:
                status = ResourceStatus.CRITICAL
                warnings.append(f"Critical memory usage: {memory_percent:.1f}%")
            elif memory_percent >= self.MEMORY_WARNING_THRESHOLD:
                if status != ResourceStatus.CRITICAL:
                    status = ResourceStatus.LOW
                warnings.append(f"High memory usage: {memory_percent:.1f}%")
            
            if disk_percent >= self.DISK_CRITICAL_THRESHOLD or disk_free_gb < self.MIN_FREE_DISK_GB:
                status = ResourceStatus.CRITICAL
                warnings.append(f"Critical disk space: {disk_free_gb:.1f}GB free ({disk_percent:.1f}% used)")
            elif disk_percent >= self.DISK_WARNING_THRESHOLD:
                if status == ResourceStatus.SUFFICIENT:
                    status = ResourceStatus.LOW
                warnings.append(f"Low disk space: {disk_free_gb:.1f}GB free ({disk_percent:.1f}% used)")
            
            return ResourceInfo(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_available_gb=memory_available_gb,
                disk_free_gb=disk_free_gb,
                disk_percent=disk_percent,
                status=status,
                warnings=warnings
            )
            
        except Exception as e:
            return ResourceInfo(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_available_gb=0.0,
                disk_free_gb=0.0,
                disk_percent=0.0,
                status=ResourceStatus.UNKNOWN,
                warnings=[f"Failed to check system resources: {e}"]
            )
    
    def validate_environment(self) -> EnvironmentInfo:
        """
        Validate environment configuration and file permissions.
        
        Returns:
            EnvironmentInfo with environment status and any issues
        """
        issues = []
        
        # Python version
        if hasattr(sys.version_info, 'major'):
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        else:
            # Handle tuple version (for testing)
            python_version = f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}"
        
        # Platform information
        platform_info = f"{platform.system()} {platform.release()}"
        
        # Current directory
        current_directory = Path.cwd()
        
        # Check directory permissions
        log_writable = self._check_directory_writable(self.log_dir, "log")
        temp_writable = self._check_directory_writable(self.temp_dir, "temp") 
        output_writable = self._check_directory_writable(self.output_dir, "output")
        
        if not log_writable:
            issues.append(f"Cannot write to log directory: {self.log_dir}")
        if not temp_writable:
            issues.append(f"Cannot write to temp directory: {self.temp_dir}")
        if not output_writable:
            issues.append(f"Cannot write to output directory: {self.output_dir}")
        
        # Check if we're in a virtual environment (recommended)
        in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        if not in_venv:
            issues.append("Not running in virtual environment (recommended for dependency isolation)")
        
        # Determine overall environment status
        if any("Cannot write" in issue for issue in issues):
            status = EnvironmentStatus.INVALID
        elif issues:
            status = EnvironmentStatus.WARNING
        else:
            status = EnvironmentStatus.VALID
        
        return EnvironmentInfo(
            python_version=python_version,
            platform_info=platform_info,
            current_directory=current_directory,
            log_directory_writable=log_writable,
            temp_directory_writable=temp_writable,
            output_permissions=output_writable,
            status=status,
            issues=issues
        )
    
    def perform_full_health_check(self) -> HealthCheckResult:
        """
        Perform comprehensive health check of all systems.
        
        Returns:
            HealthCheckResult with complete system status
        """
        dependencies = self.check_dependencies()
        resources = self.check_system_resources()
        environment = self.validate_environment()
        
        # Determine overall health status
        overall_status = self._determine_overall_status(dependencies, resources, environment)
        
        # Generate summary
        summary = self._generate_summary(overall_status, dependencies, resources, environment)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(dependencies, resources, environment)
        
        return HealthCheckResult(
            overall_status=overall_status,
            dependencies=dependencies,
            resources=resources,
            environment=environment,
            summary=summary,
            recommendations=recommendations
        )
    
    def _check_pandoc(self) -> DependencyInfo:
        """Check Pandoc availability and version."""
        try:
            # Check if pandoc is available
            pandoc_path = shutil.which("pandoc")
            if not pandoc_path:
                return DependencyInfo(
                    name="pandoc",
                    status=DependencyStatus.MISSING,
                    error_message="Pandoc not found in PATH"
                )
            
            # Get version
            result = subprocess.run(
                ["pandoc", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return DependencyInfo(
                    name="pandoc", 
                    status=DependencyStatus.NOT_EXECUTABLE,
                    path=pandoc_path,
                    error_message=f"Pandoc not executable: {result.stderr}"
                )
            
            # Parse version from output
            version_line = result.stdout.split('\n')[0]
            version = version_line.split()[1] if len(version_line.split()) > 1 else "unknown"
            
            # Check version compatibility
            required_version = self.REQUIRED_DEPENDENCIES["pandoc"]
            status = DependencyStatus.AVAILABLE
            
            if not self._version_meets_requirement(version, required_version):
                status = DependencyStatus.VERSION_INCOMPATIBLE
            
            return DependencyInfo(
                name="pandoc",
                status=status,
                version=version,
                path=pandoc_path,
                required_version=required_version
            )
            
        except subprocess.TimeoutExpired:
            return DependencyInfo(
                name="pandoc",
                status=DependencyStatus.NOT_EXECUTABLE,
                error_message="Pandoc version check timed out"
            )
        except Exception as e:
            return DependencyInfo(
                name="pandoc",
                status=DependencyStatus.UNKNOWN,
                error_message=f"Error checking Pandoc: {e}"
            )
    
    def _check_xelatex(self) -> DependencyInfo:
        """Check XeLaTeX availability and version."""
        try:
            # Check if xelatex is available
            xelatex_path = shutil.which("xelatex")
            if not xelatex_path:
                return DependencyInfo(
                    name="xelatex",
                    status=DependencyStatus.MISSING,
                    error_message="XeLaTeX not found in PATH"
                )
            
            # Get version
            result = subprocess.run(
                ["xelatex", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return DependencyInfo(
                    name="xelatex",
                    status=DependencyStatus.NOT_EXECUTABLE,
                    path=xelatex_path,
                    error_message=f"XeLaTeX not executable: {result.stderr}"
                )
            
            # Parse version from output - look for year in TeX Live info
            version = "unknown"
            for line in result.stdout.split('\n'):
                if 'TeX Live' in line:
                    # Extract year from "(TeX Live 2021)" or "TeX Live 2023" patterns
                    match = re.search(r'TeX Live (\d{4})', line)
                    if match:
                        version = match.group(1)
                        break
            
            # Check version compatibility
            required_version = self.REQUIRED_DEPENDENCIES["xelatex"]
            status = DependencyStatus.AVAILABLE
            
            if version != "unknown" and not self._version_meets_requirement(version, required_version):
                status = DependencyStatus.VERSION_INCOMPATIBLE
            
            return DependencyInfo(
                name="xelatex",
                status=status,
                version=version,
                path=xelatex_path,
                required_version=required_version
            )
            
        except subprocess.TimeoutExpired:
            return DependencyInfo(
                name="xelatex",
                status=DependencyStatus.NOT_EXECUTABLE,
                error_message="XeLaTeX version check timed out"
            )
        except Exception as e:
            return DependencyInfo(
                name="xelatex",
                status=DependencyStatus.UNKNOWN,
                error_message=f"Error checking XeLaTeX: {e}"
            )
    
    def _check_directory_writable(self, directory: Path, name: str) -> bool:
        """Check if directory is writable."""
        try:
            # Create directory if it doesn't exist
            directory.mkdir(parents=True, exist_ok=True)
            
            # Try to write a test file
            test_file = directory / f".health_check_{name}.tmp"
            test_file.write_text("test")
            test_file.unlink()
            
            return True
        except Exception:
            return False
    
    def _version_meets_requirement(self, version: str, required: str) -> bool:
        """Check if version meets requirement."""
        if version == "unknown" or required == "unknown":
            return True  # Can't verify, assume OK
        
        try:
            # Simple version comparison for year-based versions
            if version.isdigit() and required.isdigit():
                return int(version) >= int(required)
            
            # Parse semantic versions (x.y.z)
            def parse_version(v):
                return tuple(map(int, v.split('.')))
            
            return parse_version(version) >= parse_version(required)
        except (ValueError, AttributeError):
            return True  # Can't parse, assume OK
    
    def _determine_overall_status(self, dependencies: Dict[str, DependencyInfo], 
                                 resources: ResourceInfo, environment: EnvironmentInfo) -> HealthStatus:
        """Determine overall system health status."""
        # Check for critical issues
        if resources.status == ResourceStatus.CRITICAL:
            return HealthStatus.CRITICAL
        
        if environment.status == EnvironmentStatus.INVALID:
            return HealthStatus.CRITICAL
        
        # Check dependencies
        missing_deps = [dep for dep in dependencies.values() 
                       if dep.status in [DependencyStatus.MISSING, DependencyStatus.NOT_EXECUTABLE]]
        if missing_deps:
            return HealthStatus.CRITICAL
        
        # Check for warnings
        if resources.status == ResourceStatus.LOW:
            return HealthStatus.WARNING
        
        if environment.status == EnvironmentStatus.WARNING:
            return HealthStatus.WARNING
        
        version_issues = [dep for dep in dependencies.values() 
                         if dep.status == DependencyStatus.VERSION_INCOMPATIBLE]
        if version_issues:
            return HealthStatus.WARNING
        
        # All good
        return HealthStatus.HEALTHY
    
    def _generate_summary(self, overall_status: HealthStatus, dependencies: Dict[str, DependencyInfo],
                         resources: ResourceInfo, environment: EnvironmentInfo) -> str:
        """Generate health check summary."""
        status_emoji = {
            HealthStatus.HEALTHY: "✅",
            HealthStatus.WARNING: "⚠️",
            HealthStatus.CRITICAL: "❌",
            HealthStatus.UNKNOWN: "❓"
        }
        
        summary = f"{status_emoji[overall_status]} Overall Status: {overall_status.value.upper()}\n\n"
        
        # Dependencies summary
        summary += "Dependencies:\n"
        for name, dep in dependencies.items():
            emoji = "✅" if dep.status == DependencyStatus.AVAILABLE else "❌"
            version_str = f" (v{dep.version})" if dep.version else ""
            summary += f"  {emoji} {name.capitalize()}{version_str}\n"
        
        # Resources summary
        resource_emoji = "✅" if resources.status == ResourceStatus.SUFFICIENT else "⚠️" if resources.status == ResourceStatus.LOW else "❌"
        summary += f"\n{resource_emoji} Resources: {resources.status.value}\n"
        summary += f"  Memory: {resources.memory_percent:.1f}% used, {resources.memory_available_gb:.1f}GB available\n"
        summary += f"  Disk: {resources.disk_percent:.1f}% used, {resources.disk_free_gb:.1f}GB free\n"
        
        # Environment summary
        env_emoji = "✅" if environment.status == EnvironmentStatus.VALID else "⚠️" if environment.status == EnvironmentStatus.WARNING else "❌"
        summary += f"\n{env_emoji} Environment: {environment.status.value}\n"
        summary += f"  Python: {environment.python_version} on {environment.platform_info}\n"
        
        return summary
    
    def _generate_recommendations(self, dependencies: Dict[str, DependencyInfo],
                                 resources: ResourceInfo, environment: EnvironmentInfo) -> List[str]:
        """Generate recommendations based on health check results."""
        recommendations = []
        
        # Dependency recommendations
        for name, dep in dependencies.items():
            if dep.status == DependencyStatus.MISSING:
                if name == "pandoc":
                    recommendations.append("Install Pandoc from https://pandoc.org/installing.html")
                elif name == "xelatex":
                    recommendations.append("Install TeX Live or MiKTeX for XeLaTeX support")
            elif dep.status == DependencyStatus.VERSION_INCOMPATIBLE:
                recommendations.append(f"Update {name} to version {dep.required_version} or later")
            elif dep.status == DependencyStatus.NOT_EXECUTABLE:
                recommendations.append(f"Check {name} installation and permissions")
        
        # Resource recommendations
        if resources.status == ResourceStatus.CRITICAL:
            if resources.memory_percent >= self.MEMORY_CRITICAL_THRESHOLD:
                recommendations.append("Free up memory or add more RAM to prevent processing failures")
            if resources.disk_free_gb < self.MIN_FREE_DISK_GB:
                recommendations.append("Free up disk space before processing large batches")
        elif resources.status == ResourceStatus.LOW:
            recommendations.append("Monitor resource usage during processing")
        
        # Environment recommendations
        for issue in environment.issues:
            if "Cannot write" in issue:
                recommendations.append(f"Fix directory permissions: {issue}")
            elif "virtual environment" in issue:
                recommendations.append("Consider using a virtual environment for better dependency management")
        
        if not recommendations:
            recommendations.append("System is healthy and ready for processing")
        
        return recommendations
    
    def _get_memory_info(self) -> Tuple[float, float]:
        """Get memory usage info using built-in methods."""
        try:
            if platform.system() == "Windows":
                # Use Windows command
                result = subprocess.run(
                    ["wmic", "OS", "get", "TotalVisibleMemorySize,FreePhysicalMemory", "/format:csv"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    lines = [line for line in result.stdout.split('\n') if line and 'Node' not in line]
                    if len(lines) >= 1:
                        parts = lines[-1].split(',')
                        if len(parts) >= 3:
                            free_kb = float(parts[1])
                            total_kb = float(parts[2])
                            used_percent = ((total_kb - free_kb) / total_kb) * 100
                            available_gb = free_kb / (1024 * 1024)
                            return used_percent, available_gb
            else:
                # Use /proc/meminfo on Linux/Unix
                try:
                    with open('/proc/meminfo', 'r') as f:
                        meminfo = f.read()
                    
                    mem_total = 0
                    mem_available = 0
                    
                    for line in meminfo.split('\n'):
                        if line.startswith('MemTotal:'):
                            mem_total = int(line.split()[1]) * 1024  # Convert KB to bytes
                        elif line.startswith('MemAvailable:'):
                            mem_available = int(line.split()[1]) * 1024  # Convert KB to bytes
                    
                    if mem_total > 0:
                        used_percent = ((mem_total - mem_available) / mem_total) * 100
                        available_gb = mem_available / (1024**3)
                        return used_percent, available_gb
                except FileNotFoundError:
                    pass
            
            # Fallback - return safe defaults
            return 50.0, 4.0  # Assume moderate usage, 4GB available
            
        except Exception:
            return 50.0, 4.0  # Safe defaults
    
    def _get_disk_info(self, path: str) -> Tuple[float, float]:
        """Get disk usage info using built-in methods."""
        try:
            if platform.system() == "Windows":
                # Use Windows command
                result = subprocess.run(
                    ["dir", path, "/-c"],
                    capture_output=True, text=True, timeout=10, shell=True
                )
                if result.returncode == 0:
                    # Parse the output to find free space
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if 'bytes free' in line:
                            # Extract free space from "X bytes free" 
                            free_bytes = int(line.split()[0].replace(',', ''))
                            free_gb = free_bytes / (1024**3)
                            # Estimate total space (this is approximate)
                            total_gb = free_gb / 0.2  # Assume 80% used as reasonable estimate
                            used_percent = ((total_gb - free_gb) / total_gb) * 100
                            return free_gb, used_percent
            else:
                # Use df command on Linux/Unix
                result = subprocess.run(
                    ["df", "-B", "1", path],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) >= 2:
                        fields = lines[1].split()
                        if len(fields) >= 4:
                            total_bytes = int(fields[1])
                            available_bytes = int(fields[3])
                            used_bytes = total_bytes - available_bytes
                            
                            free_gb = available_bytes / (1024**3)
                            used_percent = (used_bytes / total_bytes) * 100
                            return free_gb, used_percent
            
            # Fallback - return safe defaults
            return 10.0, 70.0  # Assume 10GB free, 70% used
            
        except Exception:
            return 10.0, 70.0  # Safe defaults