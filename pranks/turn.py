"""Twilio Network Traversal Service token generation.

Runs server-side only. Never expose TWILIO_AUTH_TOKEN or API_SECRET to the browser.
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def get_ice_servers(ttl=3600):
    """Return a list of iceServers dicts for RTCPeerConnection.

    Uses Twilio NTS token (API Key + Secret recommended, falls back to Auth Token).
    Returns [] on any failure so the call can still attempt STUN-only.
    """
    try:
        from twilio.rest import Client
    except ImportError:
        logger.warning("twilio package not installed; returning empty iceServers")
        return []

    account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
    api_key = getattr(settings, "TWILIO_API_KEY", "")
    api_secret = getattr(settings, "TWILIO_API_SECRET", "")
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")

    if not account_sid:
        logger.warning("TWILIO_ACCOUNT_SID not set; returning empty iceServers")
        return []

    try:
        if api_key and api_secret:
            client = Client(api_key, api_secret, account_sid)
        elif auth_token:
            client = Client(account_sid, auth_token)
        else:
            logger.warning("No Twilio credentials configured")
            return []

        token = client.tokens.create(ttl=ttl)
        servers = []
        for s in token.ice_servers:
            entry = {"urls": s.get("urls")}
            if s.get("username"):
                entry["username"] = s["username"]
            if s.get("credential"):
                entry["credential"] = s["credential"]
            servers.append(entry)
        return servers
    except Exception as exc:
        logger.exception("Twilio TURN token generation failed: %s", exc)
        return []
