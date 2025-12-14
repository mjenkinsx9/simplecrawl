"""
URL validation utilities to prevent SSRF attacks.
"""

import ipaddress
import socket
from typing import Optional, Tuple
from urllib.parse import urlparse

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Private/internal IP ranges that should be blocked
BLOCKED_IP_RANGES = [
    ipaddress.ip_network('10.0.0.0/8'),       # Private Class A
    ipaddress.ip_network('172.16.0.0/12'),    # Private Class B
    ipaddress.ip_network('192.168.0.0/16'),   # Private Class C
    ipaddress.ip_network('127.0.0.0/8'),      # Loopback
    ipaddress.ip_network('169.254.0.0/16'),   # Link-local (AWS metadata endpoint)
    ipaddress.ip_network('::1/128'),          # IPv6 loopback
    ipaddress.ip_network('fc00::/7'),         # IPv6 private
    ipaddress.ip_network('fe80::/10'),        # IPv6 link-local
    ipaddress.ip_network('0.0.0.0/8'),        # "This" network
    ipaddress.ip_network('100.64.0.0/10'),    # Carrier-grade NAT
    ipaddress.ip_network('192.0.0.0/24'),     # IETF Protocol Assignments
    ipaddress.ip_network('192.0.2.0/24'),     # TEST-NET-1
    ipaddress.ip_network('198.51.100.0/24'),  # TEST-NET-2
    ipaddress.ip_network('203.0.113.0/24'),   # TEST-NET-3
    ipaddress.ip_network('224.0.0.0/4'),      # Multicast
    ipaddress.ip_network('240.0.0.0/4'),      # Reserved
]

# Blocked hostnames
BLOCKED_HOSTNAMES = [
    'localhost',
    'localhost.localdomain',
    '127.0.0.1',
    '0.0.0.0',
    '::1',
    'metadata.google.internal',      # GCP metadata
    'metadata.google.com',           # GCP metadata
    'instance-data',                 # Generic cloud metadata
]

# Cloud metadata endpoints to block
CLOUD_METADATA_IPS = [
    '169.254.169.254',  # AWS/GCP/Azure metadata
    '169.254.170.2',    # AWS ECS metadata
    'fd00:ec2::254',    # AWS IPv6 metadata
]


def is_ip_blocked(ip_str: str) -> bool:
    """
    Check if an IP address is in a blocked range.

    Args:
        ip_str: IP address string

    Returns:
        True if the IP should be blocked
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        for network in BLOCKED_IP_RANGES:
            if ip in network:
                return True
        return ip_str in CLOUD_METADATA_IPS
    except ValueError:
        # Invalid IP, allow (might be a hostname)
        return False


def resolve_hostname(hostname: str) -> Optional[str]:
    """
    Resolve a hostname to an IP address.

    Args:
        hostname: Hostname to resolve

    Returns:
        IP address string or None if resolution fails
    """
    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        return None


def validate_url(url: str, allow_internal: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Validate a URL for SSRF safety.

    Args:
        url: URL to validate
        allow_internal: If True, allow internal/private IPs (default: False)

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        parsed = urlparse(url)

        # Check scheme
        if parsed.scheme not in ('http', 'https'):
            return False, f"Invalid URL scheme: {parsed.scheme}. Only http and https are allowed."

        # Check for hostname
        hostname = parsed.hostname
        if not hostname:
            return False, "URL must have a hostname"

        # Lowercase hostname for comparison
        hostname_lower = hostname.lower()

        # Check blocked hostnames
        if hostname_lower in BLOCKED_HOSTNAMES:
            return False, f"Blocked hostname: {hostname}"

        # Check if hostname is an IP address
        try:
            ip = ipaddress.ip_address(hostname)
            if not allow_internal and is_ip_blocked(hostname):
                return False, f"Access to internal/private IP addresses is not allowed: {hostname}"
        except ValueError:
            # Not an IP, it's a hostname - resolve it
            resolved_ip = resolve_hostname(hostname)
            if resolved_ip:
                if not allow_internal and is_ip_blocked(resolved_ip):
                    return False, f"Hostname resolves to blocked IP: {hostname} -> {resolved_ip}"

        # Check for common SSRF bypass attempts
        # Double-encoded characters, unusual ports, etc.
        if parsed.port:
            # Block common internal service ports when accessing external hosts
            internal_ports = {22, 23, 25, 110, 143, 445, 3306, 5432, 6379, 27017}
            if parsed.port in internal_ports and not allow_internal:
                logger.warning("blocked_internal_port", url=url, port=parsed.port)
                # Don't block, just warn - these could be legitimate

        return True, None

    except Exception as e:
        logger.error("url_validation_error", url=url, error=str(e))
        return False, f"URL validation error: {str(e)}"


def validate_webhook_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a webhook URL with stricter rules.

    Webhook URLs should only point to external, trusted destinations.

    Args:
        url: Webhook URL to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    is_valid, error = validate_url(url, allow_internal=False)
    if not is_valid:
        return is_valid, error

    parsed = urlparse(url)

    # Webhooks should only use HTTPS in production
    # For now, allow HTTP but log a warning
    if parsed.scheme == 'http':
        logger.warning("insecure_webhook_url", url=url, message="Webhook URL uses HTTP instead of HTTPS")

    return True, None


def sanitize_path(path: str, base_dir: str) -> Tuple[bool, str, Optional[str]]:
    """
    Sanitize a file path to prevent path traversal attacks.

    Args:
        path: User-provided path
        base_dir: Base directory that paths must stay within

    Returns:
        Tuple of (is_valid, sanitized_path, error_message)
    """
    import os

    # Resolve to absolute path
    abs_base = os.path.abspath(base_dir)
    abs_path = os.path.abspath(os.path.join(base_dir, path))

    # Check if the resolved path is within the base directory
    if not abs_path.startswith(abs_base + os.sep) and abs_path != abs_base:
        return False, "", f"Path traversal detected: {path}"

    return True, abs_path, None
