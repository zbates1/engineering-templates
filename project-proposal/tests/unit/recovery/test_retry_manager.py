"""
Comprehensive unit tests for retry_manager.py.
Tests all retry policies, configurations, error handling, and edge cases.
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, patch, call
import logging

from src.recovery.retry_manager import (
    RetryManager,
    RetryConfig,
    RetryPolicy,
    OperationResult,
    RetryExhaustedError
)


class TestRetryConfig:
    """Test RetryConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.backoff_multiplier == 2.0
        assert config.jitter_max == 0.1
        assert config.policy == RetryPolicy.EXPONENTIAL_BACKOFF
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=30.0,
            backoff_multiplier=3.0,
            jitter_max=0.2,
            policy=RetryPolicy.LINEAR_BACKOFF
        )
        assert config.max_attempts == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.backoff_multiplier == 3.0
        assert config.jitter_max == 0.2
        assert config.policy == RetryPolicy.LINEAR_BACKOFF


class TestOperationResult:
    """Test OperationResult dataclass."""
    
    def test_success_result(self):
        """Test successful operation result."""
        result = OperationResult(
            success=True,
            result="test_result",
            attempts=2,
            total_time=1.5
        )
        assert result.success is True
        assert result.result == "test_result"
        assert result.error is None
        assert result.attempts == 2
        assert result.total_time == 1.5
    
    def test_failure_result(self):
        """Test failed operation result."""
        error = ValueError("test error")
        result = OperationResult(
            success=False,
            error=error,
            attempts=3,
            total_time=5.2
        )
        assert result.success is False
        assert result.result is None
        assert result.error == error
        assert result.attempts == 3
        assert result.total_time == 5.2


class TestRetryExhaustedError:
    """Test RetryExhaustedError exception."""
    
    def test_retry_exhausted_error(self):
        """Test RetryExhaustedError creation and attributes."""
        original_error = ValueError("original error")
        error = RetryExhaustedError(3, original_error)
        
        assert error.attempts == 3
        assert error.last_error == original_error
        assert "Retry exhausted after 3 attempts" in str(error)
        assert "original error" in str(error)


class TestRetryManager:
    """Test RetryManager class."""
    
    def test_default_initialization(self):
        """Test RetryManager with default configuration."""
        manager = RetryManager()
        assert manager.config.max_attempts == 3
        assert manager.config.policy == RetryPolicy.EXPONENTIAL_BACKOFF
    
    def test_custom_config_initialization(self):
        """Test RetryManager with custom configuration."""
        config = RetryConfig(max_attempts=5, policy=RetryPolicy.LINEAR_BACKOFF)
        manager = RetryManager(config)
        assert manager.config.max_attempts == 5
        assert manager.config.policy == RetryPolicy.LINEAR_BACKOFF
    
    def test_configure_retry_policy(self):
        """Test configuring retry policy."""
        manager = RetryManager()
        manager.configure_retry_policy(5, 'linear_backoff')
        
        assert manager.config.max_attempts == 5
        assert manager.config.policy == RetryPolicy.LINEAR_BACKOFF
    
    def test_configure_retry_policy_invalid(self):
        """Test configuring invalid retry policy."""
        manager = RetryManager()
        
        with pytest.raises(ValueError, match="Unknown backoff policy"):
            manager.configure_retry_policy(3, 'invalid_policy')
    
    def test_get_retry_delay_fixed(self):
        """Test fixed delay calculation."""
        config = RetryConfig(policy=RetryPolicy.FIXED_DELAY, base_delay=2.0)
        manager = RetryManager(config)
        
        assert manager.get_retry_delay(1) == 2.0
        assert manager.get_retry_delay(2) == 2.0
        assert manager.get_retry_delay(5) == 2.0
    
    def test_get_retry_delay_linear(self):
        """Test linear backoff delay calculation."""
        config = RetryConfig(policy=RetryPolicy.LINEAR_BACKOFF, base_delay=1.0)
        manager = RetryManager(config)
        
        assert manager.get_retry_delay(1) == 1.0
        assert manager.get_retry_delay(2) == 2.0
        assert manager.get_retry_delay(3) == 3.0
    
    def test_get_retry_delay_exponential(self):
        """Test exponential backoff delay calculation."""
        config = RetryConfig(
            policy=RetryPolicy.EXPONENTIAL_BACKOFF,
            base_delay=1.0,
            backoff_multiplier=2.0
        )
        manager = RetryManager(config)
        
        assert manager.get_retry_delay(1) == 1.0
        assert manager.get_retry_delay(2) == 2.0
        assert manager.get_retry_delay(3) == 4.0
        assert manager.get_retry_delay(4) == 8.0
    
    def test_get_retry_delay_exponential_jitter(self):
        """Test exponential backoff with jitter."""
        config = RetryConfig(
            policy=RetryPolicy.EXPONENTIAL_JITTER,
            base_delay=1.0,
            backoff_multiplier=2.0,
            jitter_max=0.1
        )
        manager = RetryManager(config)
        
        # Test multiple times due to randomness
        delays = [manager.get_retry_delay(2) for _ in range(10)]
        
        # Base exponential delay for attempt 2 is 2.0
        # With 10% jitter, should be between 1.8 and 2.2
        for delay in delays:
            assert 1.8 <= delay <= 2.2
            assert delay >= 0  # Ensure non-negative
    
    def test_get_retry_delay_max_limit(self):
        """Test that delay respects max_delay limit."""
        config = RetryConfig(
            policy=RetryPolicy.EXPONENTIAL_BACKOFF,
            base_delay=1.0,
            max_delay=5.0,
            backoff_multiplier=2.0
        )
        manager = RetryManager(config)
        
        # Should cap at max_delay
        assert manager.get_retry_delay(10) == 5.0
    
    def test_get_retry_delay_zero_attempt(self):
        """Test delay calculation for zero or negative attempts."""
        manager = RetryManager()
        
        assert manager.get_retry_delay(0) == 0.0
        assert manager.get_retry_delay(-1) == 0.0


class TestRetryExecution:
    """Test retry execution functionality."""
    
    def test_execute_with_retry_success_first_attempt(self):
        """Test successful operation on first attempt."""
        manager = RetryManager()
        
        def operation():
            return "success"
        
        result = manager.execute_with_retry(operation)
        
        assert result.success is True
        assert result.result == "success"
        assert result.error is None
        assert result.attempts == 1
        assert result.total_time > 0
    
    def test_execute_with_retry_success_after_failures(self):
        """Test successful operation after some failures."""
        manager = RetryManager()
        call_count = 0
        
        def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temporary failure")
            return "success"
        
        with patch('time.sleep'):  # Speed up test
            result = manager.execute_with_retry(operation)
        
        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 3
        assert call_count == 3
    
    def test_execute_with_retry_all_attempts_fail(self):
        """Test operation that fails all attempts."""
        config = RetryConfig(max_attempts=3)
        manager = RetryManager(config)
        call_count = 0
        
        def operation():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"failure {call_count}")
        
        with patch('time.sleep'):  # Speed up test
            result = manager.execute_with_retry(operation)
        
        assert result.success is False
        assert result.result is None
        assert isinstance(result.error, ValueError)
        assert "failure 3" in str(result.error)
        assert result.attempts == 3
        assert call_count == 3
    
    @patch('time.sleep')
    def test_execute_with_retry_delay_calls(self, mock_sleep):
        """Test that delays are applied between attempts."""
        config = RetryConfig(
            max_attempts=3,
            policy=RetryPolicy.FIXED_DELAY,
            base_delay=1.0
        )
        manager = RetryManager(config)
        
        def operation():
            raise ValueError("always fails")
        
        result = manager.execute_with_retry(operation)
        
        # Should have 2 sleep calls (between 3 attempts)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_has_calls([call(1.0), call(1.0)])
    
    def test_execute_with_retry_no_delay_after_final_attempt(self):
        """Test no delay after final attempt."""
        config = RetryConfig(max_attempts=2)
        manager = RetryManager(config)
        
        def operation():
            raise ValueError("always fails")
        
        with patch('time.sleep') as mock_sleep:
            start_time = time.perf_counter()
            result = manager.execute_with_retry(operation)
            end_time = time.perf_counter()
        
        # Should have only 1 sleep call (between attempts 1 and 2)
        assert mock_sleep.call_count == 1
        # Total execution should be quick since no sleep after final failure
        assert end_time - start_time < 0.1


class TestAsyncRetryExecution:
    """Test async retry execution functionality."""
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_async_success(self):
        """Test successful async operation."""
        manager = RetryManager()
        
        async def operation():
            return "async_success"
        
        result = await manager.execute_with_retry_async(operation)
        
        assert result.success is True
        assert result.result == "async_success"
        assert result.attempts == 1
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_async_with_failures(self):
        """Test async operation with retries."""
        manager = RetryManager()
        call_count = 0
        
        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temporary failure")
            return "async_success"
        
        with patch('asyncio.sleep'):  # Speed up test
            result = await manager.execute_with_retry_async(operation)
        
        assert result.success is True
        assert result.result == "async_success"
        assert result.attempts == 3
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_async_all_fail(self):
        """Test async operation that always fails."""
        config = RetryConfig(max_attempts=2)
        manager = RetryManager(config)
        
        async def operation():
            raise ValueError("async failure")
        
        with patch('asyncio.sleep'):
            result = await manager.execute_with_retry_async(operation)
        
        assert result.success is False
        assert isinstance(result.error, ValueError)
        assert result.attempts == 2


class TestRetryDecorator:
    """Test retry decorator functionality."""
    
    def test_retry_decorator_success(self):
        """Test decorator with successful function."""
        manager = RetryManager()
        
        @manager.retry_on_failure()
        def test_function():
            return "decorated_success"
        
        result = test_function()
        assert result == "decorated_success"
    
    def test_retry_decorator_with_retries(self):
        """Test decorator with function that needs retries."""
        manager = RetryManager()
        call_count = 0
        
        @manager.retry_on_failure()
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temporary failure")
            return "eventual_success"
        
        with patch('time.sleep'):
            result = test_function()
        
        assert result == "eventual_success"
        assert call_count == 3
    
    def test_retry_decorator_exhausted(self):
        """Test decorator when retries are exhausted."""
        config = RetryConfig(max_attempts=2)
        manager = RetryManager(config)
        
        @manager.retry_on_failure()
        def test_function():
            raise ValueError("always fails")
        
        with patch('time.sleep'):
            with pytest.raises(RetryExhaustedError) as exc_info:
                test_function()
        
        assert exc_info.value.attempts == 2
        assert isinstance(exc_info.value.last_error, ValueError)
    
    def test_retry_decorator_with_overrides(self):
        """Test decorator with parameter overrides."""
        manager = RetryManager()
        call_count = 0
        
        @manager.retry_on_failure(max_attempts=5, backoff='fixed_delay')
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise ConnectionError("temporary failure")
            return "success_with_overrides"
        
        with patch('time.sleep'):
            result = test_function()
        
        assert result == "success_with_overrides"
        assert call_count == 4


class TestRetryableErrors:
    """Test retryable error classification."""
    
    def test_is_retryable_error_connection_errors(self):
        """Test that connection errors are retryable."""
        manager = RetryManager()
        
        assert manager.is_retryable_error(ConnectionError("network issue"))
        assert manager.is_retryable_error(TimeoutError("timeout"))
        assert manager.is_retryable_error(OSError("file system error"))
    
    def test_is_retryable_error_subprocess_codes(self):
        """Test retryable subprocess error codes."""
        manager = RetryManager()
        
        # Mock subprocess error with retryable exit code
        class MockSubprocessError(Exception):
            def __init__(self, returncode):
                self.returncode = returncode
        
        assert manager.is_retryable_error(MockSubprocessError(1))
        assert manager.is_retryable_error(MockSubprocessError(127))
        assert not manager.is_retryable_error(MockSubprocessError(255))
    
    def test_is_retryable_error_message_patterns(self):
        """Test retryable error message patterns."""
        manager = RetryManager()
        
        retryable_messages = [
            "Connection timeout occurred",
            "Network temporarily unavailable",
            "Resource is busy",
            "File is locked"
        ]
        
        for message in retryable_messages:
            assert manager.is_retryable_error(Exception(message))
    
    def test_is_not_retryable_error(self):
        """Test that some errors are not retryable."""
        manager = RetryManager()
        
        non_retryable_errors = [
            ValueError("invalid input"),
            TypeError("wrong type"),
            KeyError("missing key"),
            Exception("generic error")
        ]
        
        for error in non_retryable_errors:
            assert not manager.is_retryable_error(error)


class TestLogging:
    """Test logging behavior during retries."""
    
    def test_logging_during_retries(self, caplog):
        """Test that appropriate log messages are generated."""
        with caplog.at_level(logging.DEBUG):
            manager = RetryManager()
            call_count = 0
            
            def operation():
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise ConnectionError(f"failure {call_count}")
                return "success"
            
            with patch('time.sleep'):
                result = manager.execute_with_retry(operation)
        
        # Check log messages
        assert "Executing operation, attempt 1/3" in caplog.text
        assert "Executing operation, attempt 2/3" in caplog.text  
        assert "Executing operation, attempt 3/3" in caplog.text
        assert "Attempt 1 failed: failure 1" in caplog.text
        assert "Attempt 2 failed: failure 2" in caplog.text
        assert "Operation succeeded on attempt 3" in caplog.text


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_zero_max_attempts(self):
        """Test behavior with zero max attempts."""
        config = RetryConfig(max_attempts=0)
        manager = RetryManager(config)
        
        def operation():
            return "should not execute"
        
        # Should not execute at all
        result = manager.execute_with_retry(operation)
        assert result.success is False
        assert result.attempts == 0
    
    def test_negative_max_attempts(self):
        """Test behavior with negative max attempts."""
        config = RetryConfig(max_attempts=-1)
        manager = RetryManager(config)
        
        def operation():
            return "should not execute"
        
        # Should not execute at all
        result = manager.execute_with_retry(operation)
        assert result.success is False
        assert result.attempts == 0
    
    def test_operation_returns_none(self):
        """Test operation that returns None."""
        manager = RetryManager()
        
        def operation():
            return None
        
        result = manager.execute_with_retry(operation)
        assert result.success is True
        assert result.result is None
    
    def test_operation_with_args_and_kwargs(self):
        """Test decorator with function that has arguments."""
        manager = RetryManager()
        
        @manager.retry_on_failure()
        def test_function(arg1, arg2, kwarg1=None):
            return f"{arg1}-{arg2}-{kwarg1}"
        
        result = test_function("a", "b", kwarg1="c")
        assert result == "a-b-c"


# Integration test with realistic scenario
class TestRealisticScenario:
    """Test realistic retry scenarios."""
    
    def test_file_processing_with_retries(self):
        """Test a realistic file processing scenario."""
        config = RetryConfig(
            max_attempts=3,
            policy=RetryPolicy.EXPONENTIAL_BACKOFF,
            base_delay=0.1,
            max_delay=1.0
        )
        manager = RetryManager(config)
        
        attempts = 0
        
        def process_file():
            nonlocal attempts
            attempts += 1
            
            # Simulate different failure modes
            if attempts == 1:
                raise ConnectionError("Network temporarily unavailable")
            elif attempts == 2:
                raise TimeoutError("Processing timeout")
            else:
                return {"status": "processed", "pages": 10}
        
        with patch('time.sleep'):
            result = manager.execute_with_retry(process_file)
        
        assert result.success is True
        assert result.result == {"status": "processed", "pages": 10}
        assert result.attempts == 3
        assert attempts == 3