from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import requests

import config
import storage
from handlers import Handlers


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("main")


class MaxApiClient:
    def __init__(self, token: str) -> None:
        self.token = token
        self.session = requests.Session()

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, json_body: Any = None) -> Any:
        url = f"{config.API_BASE_URL}{path}"
        query = dict(params or {})
        query["access_token"] = self.token
        if config.API_VERSION:
            query["v"] = config.API_VERSION
        resp = self.session.request(method=method, url=url, params=query, json=json_body, timeout=60)
        resp.raise_for_status()
        if not resp.content:
            return None
        return resp.json()

    def get_updates(self, marker: Optional[int]) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "timeout": config.LONGPOLL_TIMEOUT_SEC,
            "limit": config.LONGPOLL_LIMIT,
        }
        if marker is not None:
            params["marker"] = marker
        return self._request("GET", "/updates", params=params)

    def send_message(self, user_id: Optional[int] = None, chat_id: Optional[int] = None, text: str = "", attachments: Optional[List[Dict[str, Any]]] = None) -> None:
        params: Dict[str, Any] = {}
        if user_id is not None:
            params["user_id"] = int(user_id)
        if chat_id is not None:
            params["chat_id"] = int(chat_id)
        body: Dict[str, Any] = {"text": text}
        if attachments is not None:
            body["attachments"] = attachments
        self._request("POST", "/messages", params=params, json_body=body)

    def answer_callback(self, callback_id: str, notification: Optional[str] = None) -> None:
        body: Dict[str, Any] = {}
        if notification is not None:
            body["notification"] = notification
        self._request("POST", "/answers", params={"callback_id": callback_id}, json_body=body)


def _extract_message_text(update: Dict[str, Any]) -> str:
    msg = update.get("message") or {}
    body = msg.get("body") or {}
    text = body.get("text") or ""
    return str(text)


def _extract_sender_user_id(update: Dict[str, Any]) -> Optional[int]:
    msg = update.get("message") or {}
    sender = msg.get("sender") or {}
    user_id = sender.get("user_id")
    return int(user_id) if isinstance(user_id, int) else None


def _extract_chat_id(update: Dict[str, Any]) -> Optional[int]:
    msg = update.get("message") or {}
    recipient = msg.get("recipient") or {}
    chat_id = recipient.get("chat_id")
    return int(chat_id) if isinstance(chat_id, int) else None


def run() -> None:
    if not config.TOKEN:
        raise RuntimeError('Заполните TOKEN в config.py')
    if not config.ADMIN_ID:
        raise RuntimeError('Заполните ADMIN_ID в config.py')

    api = MaxApiClient(config.TOKEN)
    handlers = Handlers(api=api)
    marker = storage.get_marker(config.MARKER_PATH)

    logger.info("bot started")
    while True:
        try:
            data = api.get_updates(marker=marker)
            updates = data.get("updates") or []
            next_marker = data.get("marker")
            if isinstance(next_marker, int):
                marker = next_marker
                storage.set_marker(config.MARKER_PATH, marker)

            for update in updates:
                update_type = update.get("update_type")
                if update_type == "message_created":
                    user_id = _extract_sender_user_id(update)
                    if user_id is None:
                        continue
                    text = _extract_message_text(update)
                    handlers.handle_text(user_id=user_id, text=text)
                    continue

                if update_type == "message_callback":
                    cb = update.get("callback") or {}
                    payload = cb.get("payload") or ""
                    cb_id = cb.get("callback_id")
                    user = cb.get("user") or {}
                    user_id = user.get("user_id")
                    if isinstance(user_id, int) and isinstance(payload, str):
                        handlers.handle_callback(user_id=user_id, payload=payload, callback_id=str(cb_id) if cb_id else None)
                    continue

                if update_type == "bot_started":
                    user = update.get("user") or {}
                    user_id = user.get("user_id")
                    if isinstance(user_id, int):
                        handlers.reset_user(user_id)
                        handlers.send_main_menu(user_id)
                    continue

        except requests.HTTPError:
            logger.exception("http error")
            time.sleep(2)
        except requests.RequestException:
            logger.exception("request error")
            time.sleep(2)
        except KeyboardInterrupt:
            raise
        except Exception:
            logger.exception("unexpected error")
            time.sleep(2)


if __name__ == "__main__":
    run()

