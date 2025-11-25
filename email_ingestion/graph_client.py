
import requests
from typing import Dict, Any, List, Optional
from .config import GraphConfig
import logging

logger = logging.getLogger(__name__)

TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

class GraphEmailClient:
    def __init__(self, cfg: Optional[GraphConfig] = None) -> None:
        self.cfg = cfg or GraphConfig()
        self._access_token: Optional[str] = None

    def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token

        data = {
            "client_id": self.cfg.client_id,
            "client_secret": self.cfg.client_secret,
            "grant_type": "client_credentials",
            "scope": "https://graph.microsoft.com/.default",
        }
        token_url = TOKEN_URL_TEMPLATE.format(tenant_id=self.cfg.tenant_id)
        logger.info("Requesting access token from Microsoft identity platform")
        resp = requests.post(token_url, data=data, timeout=20)
        resp.raise_for_status()
        js = resp.json()
        self._access_token = js["access_token"]
        logger.debug("Access token acquired successfully")
        return self._access_token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Accept": "application/json",
        }

    WELL_KNOWN_FOLDERS = {
        "inbox": "Inbox",
        "sentitems": "SentItems",
        "drafts": "Drafts",
        "deleteditems": "DeletedItems",
    }

    def _resolve_folder_id(self, display_name: str) -> str:
        dn = (display_name or "").strip()
        if not dn:
            raise ValueError("Folder display name is empty")

        lower = dn.lower()
        if lower in self.WELL_KNOWN_FOLDERS:
            return self.WELL_KNOWN_FOLDERS[lower]

        # Önce Inbox altındaki alt klasörlerde ara
        url = f"{GRAPH_BASE}/users/{self.cfg.user_id}/mailFolders/inbox/childFolders"
        params = {"$top": 100}
        while True:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=20)
            resp.raise_for_status()
            js = resp.json()
            for f in js.get("value", []):
                if (f.get("displayName") or "").strip().lower() == lower:
                    folder_id = f.get("id")
                    logger.info("Resolved folder '%s' under Inbox -> id=%s", dn, folder_id)
                    return folder_id
            next_link = js.get("@odata.nextLink")
            if not next_link:
                break
            url = next_link
            params = {}

        # Tüm mailFolders içinde ara
        url = f"{GRAPH_BASE}/users/{self.cfg.user_id}/mailFolders"
        params = {"$top": 100}
        while True:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=20)
            resp.raise_for_status()
            js = resp.json()
            for f in js.get("value", []):
                if (f.get("displayName") or "").strip().lower() == lower:
                    folder_id = f.get("id")
                    logger.info("Resolved folder '%s' in all folders -> id=%s", dn, folder_id)
                    return folder_id
            next_link = js.get("@odata.nextLink")
            if not next_link:
                break
            url = next_link
            params = {}

        raise RuntimeError(f"Folder with displayName='{dn}' not found in mailbox {self.cfg.user_id}")

    def fetch_messages_from_folder(self, max_count: int = 500) -> List[Dict[str, Any]]:
        folder_id = self._resolve_folder_id(self.cfg.mail_folder_display_name)

        messages: List[Dict[str, Any]] = []
        url = f"{GRAPH_BASE}/users/{self.cfg.user_id}/mailFolders/{folder_id}/messages"
        params = {
            "$top": 50,
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,bodyPreview,body,from,toRecipients,ccRecipients,receivedDateTime",
        }

        logger.info(
            "Fetching messages from folder '%s' (id=%s) for user=%s, max_count=%s",
            self.cfg.mail_folder_display_name,
            folder_id,
            self.cfg.user_id,
            max_count,
        )

        while True:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=20)
            resp.raise_for_status()
            js = resp.json()
            value = js.get("value", [])
            messages.extend(value)
            logger.debug("Fetched %d messages in current page, total so far: %d", len(value), len(messages))

            if len(messages) >= max_count:
                messages = messages[:max_count]
                logger.info("Reached max_count=%d, stopping pagination", max_count)
                break

            next_link = js.get("@odata.nextLink")
            if not next_link:
                logger.info("No @odata.nextLink, finished pagination")
                break
            url = next_link
            params = {}

        logger.info("Total messages fetched from '%s': %d", self.cfg.mail_folder_display_name, len(messages))
        return messages
