"""
Retry manager for handling operation failures with exponential backoff.

This module provides retry logic with configurable policies for handling
transient failures in the markdown-to-PDF processing pipeline.
"""

import asyncio
import time
import random
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Any, Optional, Union, TypeVar, Generic
import logging
import functools


class RetryPolicy(Enum):
    """Supported retry policies."""
    FIXED_DELAY = "fixed_delay"
    LINEAR_BACKOFF = "linear_backoff" 
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    EXPONENTIAL_JITTER = "exponential_jitter"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter_max: float = 0.1
    policy: RetryPolicy = RetryPolicy.EXPONENTIAL_BACKOFF


class RetryExhaustedError(Exception):
    """Raised when retry attempts are exhausted."""
    
    def __init__(self, attempts: int, last_error: Exception):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"Retry exhausted after {attempts} attempts. Last error: {last_error}")


@dataclass
class OperationResult:
    """Result of a retry operation."""
    success: bool
    result: Any = None
    error: Optional[Exception] = None
    attempts: int = 0
    total_time: float = 0.0


T = TypeVar('T')


class RetryManager:
    """
    Manages retry logic with exponential backoff for operations.
    
    Provides configurable retry policies with support for different backoff
    strategies, jitter, and maximum delay limits.
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialize retry manager with configuration.
        
        Args:
            config: RetryConfig instance, defaults to exponential backoff
        """
        self.config = config or RetryConfig()
        self.logger = logging.getLogger(__name__)
    
    def configure_retry_policy(self, max_attempts: int, backoff: str) -> None:
        """
        Configure retry parameters.
        
        Args:
            max_attempts: Maximum number of retry attempts
            backoff: Backoff policy name (exponential_backoff, linear_backoff, etc.)
        """
        self.config.max_attempts = max_attempts
        
        # Map string backoff names to enum values
        policy_map = {
            'exponential_backoff': RetryPolicy.EXPONENTIAL_BACKOFF,
            'linear_backoff': RetryPolicy.LINEAR_BACKOFF,
            'fixed_delay': RetryPolicy.FIXED_DELAY,
            'exponential_jitter': RetryPolicy.EXPONENTIAL_JITTER
        }
        
        if backoff in policy_map:
            self.config.policy = policy_map[backoff]
        else:
            raise ValueError(f"Unknown backoff policy: {backoff}")
    
    def get_retry_delay(self, attempt: int) -> float:
        """
        Calculate backoff delay for a given attempt number.
        
        Args:
            attempt: Current attempt number (1-based)
            
        Returns:
            Delay in seconds before next retry
        """
        if attempt <= 0:
            return 0.0
            
        base_delay = self.config.base_delay
        max_delay = self.config.max_delay
        multiplier = self.config.backoff_multiplier
        
        if self.config.policy == RetryPolicy.FIXED_DELAY:
            delay = base_delay
            
        elif self.config.policy == RetryPolicy.LINEAR_BACKOFF:
            delay = base_delay * attempt
            
        elif self.config.policy == RetryPolicy.EXPONENTIAL_BACKOFF:
            delay = base_delay * (multiplier ** (attempt - 1))
            
        elif self.config.policy == RetryPolicy.EXPONENTIAL_JITTER:
            base_exponential = base_delay * (multiplier ** (attempt - 1))
            jitter = random.uniform(-self.config.jitter_max, self.config.jitter_max)
            delay = base_exponential * (1 + jitter)
            delay = max(0.0, delay)  # Ensure non-negative
            
        else:
            delay = base_delay
        
        return min(delay, max_delay)
    
    def execute_with_retry(self, operation: Callable[[], T]) -> OperationResult:
        """
        Execute an operation with retry logic.
        
        Args:
            operation: Callable that returns a result or raises an exception
            
        Returns:
            OperationResult with success status, result, and execution details
        """
        start_time = time.perf_counter()
        attempts = 0
        last_error = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            attempts = attempt
            
            try:
                self.logger.debug(f"Executing operation, attempt {attempt}/{self.config.max_attempts}")
                result = operation()
                
                total_time = time.perf_counter() - start_time
                self.logger.info(f"Operation succeeded on attempt {attempt} after {total_time:.2f}s")
                
                return OperationResult(
                    success=True,
                    result=result,
                    attempts=attempts,
                    total_time=total_time
                )
                
            except Exception as e:
                last_error = e
                self.logger.warning(f"Attempt {attempt} failed: {e}")
                
                # Don't delay after final attempt
                if attempt < self.config.max_attempts:
                    delay = self.get_retry_delay(attempt)
                    self.logger.debug(f"Retrying in {delay:.2f} seconds")
                    time.sleep(delay)
        
        total_time = time.perf_counter() - start_time
        self.logger.error(f"Operation failed after {attempts} attempts in {total_time:.2f}s")
        
        return OperationResult(
            success=False,
            error=last_error,
            attempts=attempts,
            total_time=total_time
        )
    
    async def execute_with_retry_async(self, operation: Callable[[], T]) -> OperationResult:
        """
        Execute an async operation with retry logic.
        
        Args:
            operation: Async callable that returns a result or raises an exception
            
        Returns:
            OperationResult with success status, result, and execution details
        """
        start_time = time.perf_counter()
        attempts = 0
        last_error = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            attempts = attempt
            
            try:
                self.logger.debug(f"Executing async operation, attempt {attempt}/{self.config.max_attempts}")
                result = await operation()
                
                total_time = time.perf_counter() - start_time
                self.logger.info(f"Async operation succeeded on attempt {attempt} after {total_time:.2f}s")
                
                return OperationResult(
                    success=True,
                    result=result,
                    attempts=attempts,
                    total_time=total_time
                )
                
            except Exception as e:
                last_error = e
                self.logger.warning(f"Async attempt {attempt} failed: {e}")
                
                # Don't delay after final attempt
                if attempt < self.config.max_attempts:
                    delay = self.get_retry_delay(attempt)
                    self.logger.debug(f"Async retrying in {delay:.2f} seconds")
                    await asyncio.sleep(delay)
        
        total_time = time.perf_counter() - start_time
        self.logger.error(f"Async operation failed after {attempts} attempts in {total_time:.2f}s")
        
        return OperationResult(
            success=False,
            error=last_error,
            attempts=attempts,
            total_time=total_time
        )
    
    def retry_on_failure(self, 
                        max_attempts: Optional[int] = None,
                        backoff: Optional[str] = None):
        """
        Decorator for adding retry behavior to functions.
        
        Args:
            max_attempts: Override default max attempts
            backoff: Override default backoff policy
            
        Returns:
            Decorated function with retry behavior
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> T:
                # Create temporary config if overrides provided
                temp_config = None
                if max_attempts is not None or backoff is not None:
                    temp_config = RetryConfig(
                        max_attempts=max_attempts or self.config.max_attempts,
                        base_delay=self.config.base_delay,
                        max_delay=self.config.max_delay,
                        backoff_multiplier=self.config.backoff_multiplier,
                        jitter_max=self.config.jitter_max
                    )
                    if backoff:
                        policy_map = {
                            'exponential_backoff': RetryPolicy.EXPONENTIAL_BACKOFF,
                            'linear_backoff': RetryPolicy.LINEAR_BACKOFF,
                            'fixed_delay': RetryPolicy.FIXED_DELAY,
                            'exponential_jitter': RetryPolicy.EXPONENTIAL_JITTER
                        }
                        temp_config.policy = policy_map.get(backoff, RetryPolicy.EXPONENTIAL_BACKOFF)
                
                # Use temporary retry manager if config overridden
                retry_manager = RetryManager(temp_config) if temp_config else self
                
                def operation() -> T:
                    return func(*args, **kwargs)
                
                result = retry_manager.execute_with_retry(operation)
                
                if result.success:
                    return result.result
                else:
                    raise RetryExhaustedError(result.attempts, result.error)
            
            return wrapper
        return decorator
    
    def is_retryable_error(self, error: Exception) -> bool:
        """
        Determine if an error should trigger a retry.
        
        Args:
            error: Exception that occurred
            
        Returns:
            True if the error is considered retryable
        """
        # Define retryable error types
        retryable_types = (
            ConnectionError,
            TimeoutError,
            OSError,  # Includes file system errors
        )
        
        # Check for specific retryable conditions
        if isinstance(error, retryable_types):
            return True
        
        # Check for subprocess errors that might be retryable
        if hasattr(error, 'returncode'):
            # Some exit codes indicate temporary issues
            retryable_exit_codes = [1, 2, 126, 127, 130]  # Common temporary failure codes
            return getattr(error, 'returncode', 0) in retryable_exit_codes
        
        # Check error message for retryable patterns
        error_message = str(error).lower()
        retryable_patterns = [
            'timeout',
            'connection',
            'temporary',
            'busy',
            'locked',
            'network',
            'unavailable'
        ]
        
        return any(pattern in error_message for pattern in retryable_patterns)