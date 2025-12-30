"""DNS registration with custom Tailscale DNS server."""

import logging
import httpx

from .config import settings

logger = logging.getLogger(__name__)


async def register_dns() -> bool:
    """
    Register this service with the custom DNS API server.

    POST to {dns_api_url}/add-record/ with:
    {
        "name": {dns_service_name},
        "port": {port},
        "service_name": "lmserver",
        "target_device": {dns_target_device}
    }

    Returns True if registration succeeded, False otherwise.
    """
    if not settings.dns_register_on_startup:
        logger.info("DNS registration disabled, skipping")
        return True

    payload = {
        "name": settings.dns_service_name,
        "port": settings.port,
        "service_name": "lmserver",
        "target_device": settings.dns_target_device,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.dns_api_url}/add-record/",
                json=payload,
            )
            response.raise_for_status()
            full_domain = f"{settings.dns_service_name}.{settings.dns_domain_base}"
            logger.info(
                f"Registered with DNS: {full_domain} -> :{settings.port}"
            )
            return True
    except httpx.HTTPStatusError as e:
        logger.error(f"DNS registration failed with status {e.response.status_code}: {e.response.text}")
        return False
    except httpx.RequestError as e:
        logger.warning(f"DNS registration failed (network error): {e}")
        logger.warning("Service will continue without DNS registration")
        return False


async def deregister_dns() -> bool:
    """
    Deregister this service from DNS (if the API supports it).

    This is a placeholder - implement if your DNS API has a delete endpoint.
    """
    logger.info("DNS deregistration not implemented (service shutdown)")
    return True

