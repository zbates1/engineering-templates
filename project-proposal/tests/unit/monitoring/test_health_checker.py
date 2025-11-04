"""
Unit tests for the health checking module.
Tests dependency validation, resource monitoring, environment checks, and overall health assessment.
"""

import pytest
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import os
import platform

from src.monitoring.health_checker import (
    HealthChecker,
    HealthStatus,
    ResourceStatus,
    EnvironmentStatus,
    DependencyStatus,
    DependencyInfo,
    ResourceInfo,
    EnvironmentInfo,
    HealthCheckResult
)


class TestHealthChecker:
    """Test cases for the HealthChecker class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.health_checker = HealthChecker()
    
    def test_initialization(self):
        """Test health checker initialization."""
        assert isinstance(self.health_checker, HealthChecker)
        assert self.health_checker.log_dir == Path("logs")
        assert self.health_checker.temp_dir == Path("temp")
        assert self.health_checker.output_dir == Path("output")
    
    def test_initialization_with_custom_paths(self):
        """Test health checker initialization with custom paths."""
        log_dir = Path("custom_logs")
        temp_dir = Path("custom_temp")
        output_dir = Path("custom_output")
        
        checker = HealthChecker(log_dir, temp_dir, output_dir)
        assert checker.log_dir == log_dir
        assert checker.temp_dir == temp_dir
        assert checker.output_dir == output_dir
    
    @patch('shutil.which')
    @patch('subprocess.run')
    def test_check_pandoc_available(self, mock_run, mock_which):
        """Test successful Pandoc dependency check."""
        mock_which.return_value = "/usr/bin/pandoc"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="pandoc 2.14.0.3\nCompiled with pandoc-types 1.22"
        )
        
        result = self.health_checker._check_pandoc()
        
        assert result.name == "pandoc"
        assert result.status == DependencyStatus.AVAILABLE
        assert result.version == "2.14.0.3"
        assert result.path == "/usr/bin/pandoc"
        assert result.required_version == "2.0.0"
    
    @patch('shutil.which')
    def test_check_pandoc_missing(self, mock_which):
        """Test Pandoc missing dependency check."""
        mock_which.return_value = None
        
        result = self.health_checker._check_pandoc()
        
        assert result.name == "pandoc"
        assert result.status == DependencyStatus.MISSING
        assert result.error_message == "Pandoc not found in PATH"
    
    @patch('shutil.which')
    @patch('subprocess.run')
    def test_check_pandoc_not_executable(self, mock_run, mock_which):
        """Test Pandoc not executable."""
        mock_which.return_value = "/usr/bin/pandoc"
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Permission denied"
        )
        
        result = self.health_checker._check_pandoc()
        
        assert result.name == "pandoc"
        assert result.status == DependencyStatus.NOT_EXECUTABLE
        assert "Permission denied" in result.error_message
    
    @patch('shutil.which')
    @patch('subprocess.run')
    def test_check_pandoc_version_incompatible(self, mock_run, mock_which):
        """Test Pandoc version incompatible."""
        mock_which.return_value = "/usr/bin/pandoc"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="pandoc 1.19.2\nCompiled with pandoc-types 1.17"
        )
        
        result = self.health_checker._check_pandoc()
        
        assert result.name == "pandoc"
        assert result.status == DependencyStatus.VERSION_INCOMPATIBLE
        assert result.version == "1.19.2"
    
    @patch('shutil.which')
    @patch('subprocess.run')
    def test_check_pandoc_timeout(self, mock_run, mock_which):
        """Test Pandoc version check timeout."""
        mock_which.return_value = "/usr/bin/pandoc"
        mock_run.side_effect = subprocess.TimeoutExpired("pandoc", 10)
        
        result = self.health_checker._check_pandoc()
        
        assert result.name == "pandoc"
        assert result.status == DependencyStatus.NOT_EXECUTABLE
        assert "timed out" in result.error_message
    
    @patch('shutil.which')
    @patch('subprocess.run')
    def test_check_xelatex_available(self, mock_run, mock_which):
        """Test successful XeLaTeX dependency check."""
        mock_which.return_value = "/usr/bin/xelatex"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="XeTeX 3.141592653-2.6-0.999993 (TeX Live 2021)\nkpathsea version 6.3.3\n"
        )
        
        result = self.health_checker._check_xelatex()
        
        assert result.name == "xelatex"
        assert result.status == DependencyStatus.AVAILABLE
        assert result.version == "2021"
        assert result.path == "/usr/bin/xelatex"
    
    @patch('shutil.which')
    def test_check_xelatex_missing(self, mock_which):
        """Test XeLaTeX missing dependency check."""
        mock_which.return_value = None
        
        result = self.health_checker._check_xelatex()
        
        assert result.name == "xelatex"
        assert result.status == DependencyStatus.MISSING
        assert result.error_message == "XeLaTeX not found in PATH"
    
    @patch('shutil.which')
    @patch('subprocess.run')
    def test_check_xelatex_version_incompatible(self, mock_run, mock_which):
        """Test XeLaTeX version incompatible."""
        mock_which.return_value = "/usr/bin/xelatex"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="XeTeX 3.141592653-2.6-0.999993 (TeX Live 2016)\nkpathsea version 6.2.3\n"
        )
        
        result = self.health_checker._check_xelatex()
        
        assert result.name == "xelatex"
        assert result.status == DependencyStatus.VERSION_INCOMPATIBLE
        assert result.version == "2016"
    
    def test_check_dependencies(self):
        """Test checking all dependencies."""
        with patch.object(self.health_checker, '_check_pandoc') as mock_pandoc, \
             patch.object(self.health_checker, '_check_xelatex') as mock_xelatex:
            
            mock_pandoc.return_value = DependencyInfo(
                name="pandoc",
                status=DependencyStatus.AVAILABLE,
                version="2.14.0"
            )
            mock_xelatex.return_value = DependencyInfo(
                name="xelatex", 
                status=DependencyStatus.AVAILABLE,
                version="2021"
            )
            
            result = self.health_checker.check_dependencies()
            
            assert "pandoc" in result
            assert "xelatex" in result
            assert result["pandoc"].status == DependencyStatus.AVAILABLE
            assert result["xelatex"].status == DependencyStatus.AVAILABLE
    
    @patch('platform.system')
    def test_get_memory_info_windows(self, mock_system):
        """Test memory info retrieval on Windows."""
        mock_system.return_value = "Windows"
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Node,FreePhysicalMemory,TotalVisibleMemorySize\n,4194304,8388608"
            )
            
            memory_percent, memory_available_gb = self.health_checker._get_memory_info()
            
            assert isinstance(memory_percent, float)
            assert isinstance(memory_available_gb, float)
            assert 0 <= memory_percent <= 100
            assert memory_available_gb > 0
    
    @patch('platform.system')
    def test_get_memory_info_linux(self, mock_system):
        """Test memory info retrieval on Linux."""
        mock_system.return_value = "Linux"
        
        meminfo_content = """MemTotal:       8192000 kB
MemFree:        2048000 kB
MemAvailable:   4096000 kB
Buffers:         512000 kB
Cached:         1024000 kB"""
        
        with patch('builtins.open', mock_open(read_data=meminfo_content)):
            memory_percent, memory_available_gb = self.health_checker._get_memory_info()
            
            assert isinstance(memory_percent, float)
            assert isinstance(memory_available_gb, float)
            assert 0 <= memory_percent <= 100
            assert memory_available_gb > 0
    
    @patch('platform.system')
    def test_get_memory_info_fallback(self, mock_system):
        """Test memory info fallback when commands fail."""
        mock_system.return_value = "Windows"
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception("Command failed")
            
            memory_percent, memory_available_gb = self.health_checker._get_memory_info()
            
            assert memory_percent == 50.0
            assert memory_available_gb == 4.0
    
    @patch('platform.system')
    def test_get_disk_info_windows(self, mock_system):
        """Test disk info retrieval on Windows."""
        mock_system.return_value = "Windows"
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Directory of C:\\test\n\n15 File(s)    1,073,741,824 bytes\n               5,368,709,120 bytes free"
            )
            
            disk_free_gb, disk_percent = self.health_checker._get_disk_info('.')
            
            assert isinstance(disk_free_gb, float)
            assert isinstance(disk_percent, float)
            assert disk_free_gb > 0
            assert 0 <= disk_percent <= 100
    
    @patch('platform.system')
    def test_get_disk_info_linux(self, mock_system):
        """Test disk info retrieval on Linux."""
        mock_system.return_value = "Linux"
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Filesystem     1B-blocks       Used  Available Use% Mounted on\n/dev/sda1    10737418240 8589934592 2147483648  80% /"
            )
            
            disk_free_gb, disk_percent = self.health_checker._get_disk_info('.')
            
            assert isinstance(disk_free_gb, float)
            assert isinstance(disk_percent, float)
            assert disk_free_gb > 0
            assert 0 <= disk_percent <= 100
    
    @patch('platform.system')
    def test_get_disk_info_fallback(self, mock_system):
        """Test disk info fallback when commands fail."""
        mock_system.return_value = "Linux"
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception("Command failed")
            
            disk_free_gb, disk_percent = self.health_checker._get_disk_info('.')
            
            assert disk_free_gb == 10.0
            assert disk_percent == 70.0
    
    def test_check_system_resources_sufficient(self):
        """Test system resource check with sufficient resources."""
        with patch.object(self.health_checker, '_get_memory_info') as mock_mem, \
             patch.object(self.health_checker, '_get_disk_info') as mock_disk:
            
            mock_mem.return_value = (50.0, 8.0)  # 50% memory used, 8GB available
            mock_disk.return_value = (50.0, 60.0)  # 50GB free, 60% used
            
            result = self.health_checker.check_system_resources()
            
            assert result.status == ResourceStatus.SUFFICIENT
            assert result.memory_percent == 50.0
            assert result.memory_available_gb == 8.0
            assert result.disk_free_gb == 50.0
            assert result.disk_percent == 60.0
            assert len(result.warnings) == 0
    
    def test_check_system_resources_low_memory(self):
        """Test system resource check with low memory."""
        with patch.object(self.health_checker, '_get_memory_info') as mock_mem, \
             patch.object(self.health_checker, '_get_disk_info') as mock_disk:
            
            mock_mem.return_value = (85.0, 2.0)  # 85% memory used, 2GB available
            mock_disk.return_value = (50.0, 60.0)  # 50GB free, 60% used
            
            result = self.health_checker.check_system_resources()
            
            assert result.status == ResourceStatus.LOW
            assert len(result.warnings) == 1
            assert "High memory usage" in result.warnings[0]
    
    def test_check_system_resources_critical_memory(self):
        """Test system resource check with critical memory usage."""
        with patch.object(self.health_checker, '_get_memory_info') as mock_mem, \
             patch.object(self.health_checker, '_get_disk_info') as mock_disk:
            
            mock_mem.return_value = (95.0, 0.5)  # 95% memory used, 0.5GB available
            mock_disk.return_value = (50.0, 60.0)  # 50GB free, 60% used
            
            result = self.health_checker.check_system_resources()
            
            assert result.status == ResourceStatus.CRITICAL
            assert len(result.warnings) == 1
            assert "Critical memory usage" in result.warnings[0]
    
    def test_check_system_resources_low_disk(self):
        """Test system resource check with low disk space."""
        with patch.object(self.health_checker, '_get_memory_info') as mock_mem, \
             patch.object(self.health_checker, '_get_disk_info') as mock_disk:
            
            mock_mem.return_value = (50.0, 8.0)  # 50% memory used, 8GB available
            mock_disk.return_value = (5.0, 90.0)  # 5GB free, 90% used
            
            result = self.health_checker.check_system_resources()
            
            assert result.status == ResourceStatus.LOW
            assert len(result.warnings) == 1
            assert "Low disk space" in result.warnings[0]
    
    def test_check_system_resources_critical_disk(self):
        """Test system resource check with critical disk space."""
        with patch.object(self.health_checker, '_get_memory_info') as mock_mem, \
             patch.object(self.health_checker, '_get_disk_info') as mock_disk:
            
            mock_mem.return_value = (50.0, 8.0)  # 50% memory used, 8GB available
            mock_disk.return_value = (0.5, 98.0)  # 0.5GB free, 98% used
            
            result = self.health_checker.check_system_resources()
            
            assert result.status == ResourceStatus.CRITICAL
            assert len(result.warnings) == 1
            assert "Critical disk space" in result.warnings[0]
    
    def test_check_system_resources_exception(self):
        """Test system resource check when exception occurs."""
        with patch.object(self.health_checker, '_get_memory_info') as mock_mem:
            mock_mem.side_effect = Exception("Test error")
            
            result = self.health_checker.check_system_resources()
            
            assert result.status == ResourceStatus.UNKNOWN
            assert len(result.warnings) == 1
            assert "Failed to check system resources" in result.warnings[0]
    
    def test_check_directory_writable_success(self):
        """Test successful directory writability check."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            result = self.health_checker._check_directory_writable(temp_path, "test")
            assert result is True
    
    def test_check_directory_writable_failure(self):
        """Test failed directory writability check."""
        # Use a non-existent parent directory that can't be created
        if platform.system() == "Windows":
            invalid_path = Path("Z:\\nonexistent\\path")
        else:
            invalid_path = Path("/root/protected/path")
        
        result = self.health_checker._check_directory_writable(invalid_path, "test")
        assert result is False
    
    @patch('sys.version_info', (3, 9, 7))
    @patch('platform.system')
    @patch('platform.release')
    @patch('sys.base_prefix', '/usr')
    @patch('sys.prefix', '/usr/venv')
    def test_validate_environment_valid(self, mock_release, mock_system):
        """Test environment validation with valid environment."""
        mock_system.return_value = "Linux"
        mock_release.return_value = "5.4.0"
        
        with patch.object(self.health_checker, '_check_directory_writable') as mock_check:
            mock_check.return_value = True
            
            result = self.health_checker.validate_environment()
            
            assert result.status == EnvironmentStatus.VALID
            assert result.python_version == "3.9.7"
            assert result.platform_info == "Linux 5.4.0"
            assert result.log_directory_writable is True
            assert result.temp_directory_writable is True
            assert result.output_permissions is True
            assert len(result.issues) == 0  # No issues when in venv
    
    def test_validate_environment_permission_issues(self):
        """Test environment validation with permission issues."""
        with patch.object(self.health_checker, '_check_directory_writable') as mock_check:
            mock_check.return_value = False
            
            result = self.health_checker.validate_environment()
            
            assert result.status == EnvironmentStatus.INVALID
            assert len(result.issues) >= 3  # Three directory permission issues
            assert any("Cannot write to log directory" in issue for issue in result.issues)
            assert any("Cannot write to temp directory" in issue for issue in result.issues)
            assert any("Cannot write to output directory" in issue for issue in result.issues)
    
    def test_version_meets_requirement_semantic(self):
        """Test semantic version comparison."""
        assert self.health_checker._version_meets_requirement("2.14.0", "2.0.0") is True
        assert self.health_checker._version_meets_requirement("1.9.2", "2.0.0") is False
        assert self.health_checker._version_meets_requirement("2.0.0", "2.0.0") is True
    
    def test_version_meets_requirement_year(self):
        """Test year-based version comparison."""
        assert self.health_checker._version_meets_requirement("2021", "2017") is True
        assert self.health_checker._version_meets_requirement("2016", "2017") is False
        assert self.health_checker._version_meets_requirement("2017", "2017") is True
    
    def test_version_meets_requirement_unknown(self):
        """Test version comparison with unknown versions."""
        assert self.health_checker._version_meets_requirement("unknown", "2.0.0") is True
        assert self.health_checker._version_meets_requirement("2.0.0", "unknown") is True
        assert self.health_checker._version_meets_requirement("unknown", "unknown") is True
    
    def test_determine_overall_status_healthy(self):
        """Test determining overall status when system is healthy."""
        dependencies = {
            "pandoc": DependencyInfo("pandoc", DependencyStatus.AVAILABLE),
            "xelatex": DependencyInfo("xelatex", DependencyStatus.AVAILABLE)
        }
        resources = ResourceInfo(0.0, 50.0, 8.0, 50.0, 60.0, ResourceStatus.SUFFICIENT, [])
        environment = EnvironmentInfo("3.9.7", "Linux", Path.cwd(), True, True, True, 
                                    EnvironmentStatus.VALID, [])
        
        status = self.health_checker._determine_overall_status(dependencies, resources, environment)
        assert status == HealthStatus.HEALTHY
    
    def test_determine_overall_status_critical_resources(self):
        """Test determining overall status with critical resources."""
        dependencies = {
            "pandoc": DependencyInfo("pandoc", DependencyStatus.AVAILABLE),
            "xelatex": DependencyInfo("xelatex", DependencyStatus.AVAILABLE)
        }
        resources = ResourceInfo(0.0, 95.0, 0.5, 0.5, 98.0, ResourceStatus.CRITICAL, ["Critical"])
        environment = EnvironmentInfo("3.9.7", "Linux", Path.cwd(), True, True, True,
                                    EnvironmentStatus.VALID, [])
        
        status = self.health_checker._determine_overall_status(dependencies, resources, environment)
        assert status == HealthStatus.CRITICAL
    
    def test_determine_overall_status_missing_dependencies(self):
        """Test determining overall status with missing dependencies."""
        dependencies = {
            "pandoc": DependencyInfo("pandoc", DependencyStatus.MISSING),
            "xelatex": DependencyInfo("xelatex", DependencyStatus.AVAILABLE)
        }
        resources = ResourceInfo(0.0, 50.0, 8.0, 50.0, 60.0, ResourceStatus.SUFFICIENT, [])
        environment = EnvironmentInfo("3.9.7", "Linux", Path.cwd(), True, True, True,
                                    EnvironmentStatus.VALID, [])
        
        status = self.health_checker._determine_overall_status(dependencies, resources, environment)
        assert status == HealthStatus.CRITICAL
    
    def test_determine_overall_status_warning(self):
        """Test determining overall status with warnings."""
        dependencies = {
            "pandoc": DependencyInfo("pandoc", DependencyStatus.VERSION_INCOMPATIBLE),
            "xelatex": DependencyInfo("xelatex", DependencyStatus.AVAILABLE)
        }
        resources = ResourceInfo(0.0, 50.0, 8.0, 50.0, 60.0, ResourceStatus.SUFFICIENT, [])
        environment = EnvironmentInfo("3.9.7", "Linux", Path.cwd(), True, True, True,
                                    EnvironmentStatus.VALID, [])
        
        status = self.health_checker._determine_overall_status(dependencies, resources, environment)
        assert status == HealthStatus.WARNING
    
    def test_generate_summary_healthy(self):
        """Test summary generation for healthy system."""
        dependencies = {
            "pandoc": DependencyInfo("pandoc", DependencyStatus.AVAILABLE, version="2.14.0"),
            "xelatex": DependencyInfo("xelatex", DependencyStatus.AVAILABLE, version="2021")
        }
        resources = ResourceInfo(0.0, 50.0, 8.0, 50.0, 60.0, ResourceStatus.SUFFICIENT, [])
        environment = EnvironmentInfo("3.9.7", "Linux 5.4.0", Path.cwd(), True, True, True,
                                    EnvironmentStatus.VALID, [])
        
        summary = self.health_checker._generate_summary(
            HealthStatus.HEALTHY, dependencies, resources, environment)
        
        assert "✅ Overall Status: HEALTHY" in summary
        assert "✅ Pandoc (v2.14.0)" in summary
        assert "✅ Xelatex (v2021)" in summary
        assert "✅ Resources: sufficient" in summary
        assert "Memory: 50.0% used" in summary
        assert "Disk: 60.0% used" in summary
        assert "✅ Environment: valid" in summary
        assert "Python: 3.9.7 on Linux 5.4.0" in summary
    
    def test_generate_recommendations_healthy(self):
        """Test recommendations generation for healthy system."""
        dependencies = {
            "pandoc": DependencyInfo("pandoc", DependencyStatus.AVAILABLE),
            "xelatex": DependencyInfo("xelatex", DependencyStatus.AVAILABLE)
        }
        resources = ResourceInfo(0.0, 50.0, 8.0, 50.0, 60.0, ResourceStatus.SUFFICIENT, [])
        environment = EnvironmentInfo("3.9.7", "Linux", Path.cwd(), True, True, True,
                                    EnvironmentStatus.VALID, [])
        
        recommendations = self.health_checker._generate_recommendations(
            dependencies, resources, environment)
        
        assert len(recommendations) == 1
        assert "System is healthy and ready for processing" in recommendations[0]
    
    def test_generate_recommendations_issues(self):
        """Test recommendations generation with issues."""
        dependencies = {
            "pandoc": DependencyInfo("pandoc", DependencyStatus.MISSING),
            "xelatex": DependencyInfo("xelatex", DependencyStatus.VERSION_INCOMPATIBLE,
                                   required_version="2017")
        }
        resources = ResourceInfo(0.0, 95.0, 0.5, 0.5, 98.0, ResourceStatus.CRITICAL, [])
        environment = EnvironmentInfo("3.9.7", "Linux", Path.cwd(), False, True, True,
                                    EnvironmentStatus.INVALID, ["Cannot write to log directory"])
        
        recommendations = self.health_checker._generate_recommendations(
            dependencies, resources, environment)
        
        assert len(recommendations) >= 4
        assert any("Install Pandoc" in rec for rec in recommendations)
        assert any("Update xelatex" in rec for rec in recommendations)
        assert any("Free up memory" in rec for rec in recommendations)
        assert any("Fix directory permissions" in rec for rec in recommendations)
    
    def test_perform_full_health_check(self):
        """Test performing a complete health check."""
        with patch.object(self.health_checker, 'check_dependencies') as mock_deps, \
             patch.object(self.health_checker, 'check_system_resources') as mock_resources, \
             patch.object(self.health_checker, 'validate_environment') as mock_env:
            
            # Mock all subsystem checks
            mock_deps.return_value = {
                "pandoc": DependencyInfo("pandoc", DependencyStatus.AVAILABLE),
                "xelatex": DependencyInfo("xelatex", DependencyStatus.AVAILABLE)
            }
            mock_resources.return_value = ResourceInfo(
                0.0, 50.0, 8.0, 50.0, 60.0, ResourceStatus.SUFFICIENT, [])
            mock_env.return_value = EnvironmentInfo(
                "3.9.7", "Linux", Path.cwd(), True, True, True, EnvironmentStatus.VALID, [])
            
            result = self.health_checker.perform_full_health_check()
            
            assert isinstance(result, HealthCheckResult)
            assert result.overall_status == HealthStatus.HEALTHY
            assert "pandoc" in result.dependencies
            assert "xelatex" in result.dependencies
            assert result.resources.status == ResourceStatus.SUFFICIENT
            assert result.environment.status == EnvironmentStatus.VALID
            assert isinstance(result.summary, str)
            assert isinstance(result.recommendations, list)
            assert len(result.recommendations) >= 1


class TestDependencyInfo:
    """Test cases for DependencyInfo dataclass."""
    
    def test_dependency_info_creation(self):
        """Test creating DependencyInfo objects."""
        dep_info = DependencyInfo(
            name="pandoc",
            status=DependencyStatus.AVAILABLE,
            version="2.14.0",
            path="/usr/bin/pandoc",
            required_version="2.0.0"
        )
        
        assert dep_info.name == "pandoc"
        assert dep_info.status == DependencyStatus.AVAILABLE
        assert dep_info.version == "2.14.0"
        assert dep_info.path == "/usr/bin/pandoc"
        assert dep_info.required_version == "2.0.0"
        assert dep_info.error_message is None


class TestResourceInfo:
    """Test cases for ResourceInfo dataclass."""
    
    def test_resource_info_creation(self):
        """Test creating ResourceInfo objects."""
        resource_info = ResourceInfo(
            cpu_percent=45.5,
            memory_percent=60.0,
            memory_available_gb=8.5,
            disk_free_gb=100.0,
            disk_percent=75.0,
            status=ResourceStatus.SUFFICIENT,
            warnings=["Test warning"]
        )
        
        assert resource_info.cpu_percent == 45.5
        assert resource_info.memory_percent == 60.0
        assert resource_info.memory_available_gb == 8.5
        assert resource_info.disk_free_gb == 100.0
        assert resource_info.disk_percent == 75.0
        assert resource_info.status == ResourceStatus.SUFFICIENT
        assert resource_info.warnings == ["Test warning"]


class TestEnvironmentInfo:
    """Test cases for EnvironmentInfo dataclass."""
    
    def test_environment_info_creation(self):
        """Test creating EnvironmentInfo objects."""
        env_info = EnvironmentInfo(
            python_version="3.9.7",
            platform_info="Linux 5.4.0",
            current_directory=Path("/test"),
            log_directory_writable=True,
            temp_directory_writable=True,
            output_permissions=True,
            status=EnvironmentStatus.VALID,
            issues=[]
        )
        
        assert env_info.python_version == "3.9.7"
        assert env_info.platform_info == "Linux 5.4.0"
        assert env_info.current_directory == Path("/test")
        assert env_info.log_directory_writable is True
        assert env_info.temp_directory_writable is True
        assert env_info.output_permissions is True
        assert env_info.status == EnvironmentStatus.VALID
        assert env_info.issues == []