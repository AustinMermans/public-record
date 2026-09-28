"""Public receipts must never contain private subprocess arguments."""
import subprocess


def safe_sec_error(error):
    if isinstance(error, subprocess.TimeoutExpired):
        return 'SEC request timed out'
    return 'SEC collection failed (' + type(error).__name__ + ')'
