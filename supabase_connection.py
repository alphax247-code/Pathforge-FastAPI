"""
Optimized Supabase connection with connection pooling and keep-alive.
This module provides a persistent requests session for faster Supabase API calls.
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Create a global session with connection pooling
_session = None

def get_supabase_session():
    """
    Get or create a persistent requests session with connection pooling.
    This dramatically reduces latency by reusing TCP connections.
    """
    global _session

    if _session is None:
        _session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,  # Total number of retries
            backoff_factor=0.1,  # Wait 0.1s, 0.2s, 0.4s between retries
            status_forcelist=[429, 500, 502, 503, 504],  # Retry on these HTTP codes
            allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
        )

        # Create adapter with connection pooling
        adapter = HTTPAdapter(
            pool_connections=10,  # Number of connection pools
            pool_maxsize=20,  # Maximum connections in pool
            max_retries=retry_strategy,
            pool_block=False  # Don't block if pool is full
        )

        # Mount adapter for both HTTP and HTTPS
        _session.mount("http://", adapter)
        _session.mount("https://", adapter)

        # Enable keep-alive
        _session.headers.update({
            'Connection': 'keep-alive',
            'Keep-Alive': 'timeout=30, max=100'
        })

    return _session

def close_supabase_session():
    """Close the persistent session (call on app shutdown)."""
    global _session
    if _session:
        _session.close()
        _session = None
