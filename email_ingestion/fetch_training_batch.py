
import json
from pathlib import Path
from typing import Any, Dict
import logging

from .config import GraphConfig
from .graph_client import GraphEmailClient

logger = logging.getLogger(__name__)

OUT_PATH = Path("data/train/raw_emails.jsonl")

def simplify_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    body = msg.get("body", {}) or {}
    content = body.get("content", "") or ""
    content_type = body.get("contentType", "html")

    return {
        "id": msg.get("id"),
        "subject": msg.get("subject"),
        "from": (msg.get("from") or {}).get("emailAddress", {}),
        "to": [r.get("emailAddress", {}) for r in msg.get("toRecipients", [])],
        "cc": [r.get("emailAddress", {}) for r in msg.get("ccRecipients", [])],
        "receivedDateTime": msg.get("receivedDateTime"),
        "body": {
            "contentType": content_type,
            "content": content,
        },
        "bodyPreview": msg.get("bodyPreview"),
    }

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    cfg = GraphConfig()
    client = GraphEmailClient(cfg)

    logger.info(
        "Fetching training emails from mailbox=%s, folder='%s', max=%d",
        cfg.user_id,
        cfg.mail_folder_display_name,
        cfg.max_training_emails,
    )

    msgs = client.fetch_messages_from_folder(max_count=cfg.max_training_emails)
    logger.info("Total messages fetched: %d", len(msgs))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("a", encoding="utf-8") as f:
        for msg in msgs:
            simple = simplify_message(msg)
            f.write(json.dumps(simple, ensure_ascii=False) + "\n")

    logger.info("Training emails written to %s", OUT_PATH)

if __name__ == "__main__":
    main()
