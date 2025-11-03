"""
Simple synchronous rate limiter.
Limits the number of operations per second.
"""

import time
from typing import Optional


class RateLimiter:
    """
    Simple synchronous rate limiter using token bucket algorithm.
    """
    
    def __init__(self, rate: float = 6.0):
        """
        Initialize rate limiter.
        
        Args:
            rate: Requests per second (default 6.0)
        """
        self.rate = rate
        self.min_interval = 1.0 / rate if rate > 0 else 0
        self.last_call_time: Optional[float] = None
    
    def wait_if_needed(self):
        """
        Block if necessary to maintain rate limit.
        """
        if self.min_interval == 0:
            return
        
        now = time.time()
        
        if self.last_call_time is not None:
            elapsed = now - self.last_call_time
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)
        
        self.last_call_time = time.time()

