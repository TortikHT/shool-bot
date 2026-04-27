from __future__ import annotations

from typing import Any, Dict, List


def _inline_keyboard(button_rows: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    return [
        {
            "type": "inline_keyboard",
            "payload": {"buttons": button_rows},
        }
    ]


def main_menu_attachments() -> List[Dict[str, Any]]:
    return _inline_keyboard(
        [
            [{"type": "callback", "text": " Подать заявку в 1 класс", "payload": "menu_apply"}],
            [{"type": "callback", "text": "ℹ️ О школе", "payload": "menu_about"}],
            [{"type": "callback", "text": " Контакты", "payload": "menu_contacts"}],
        ]
    )


def confirm_attachments() -> List[Dict[str, Any]]:
    return _inline_keyboard(
        [
            [{"type": "callback", "text": "Подтвердить", "payload": "app_confirm_yes"}],
            [{"type": "callback", "text": "Изменить данные", "payload": "app_confirm_edit"}],
            [{"type": "callback", "text": "Отменить", "payload": "app_confirm_cancel"}],
        ]
    )


def admin_clear_attachments() -> List[Dict[str, Any]]:
    return _inline_keyboard(
        [
            [{"type": "callback", "text": "Да, очистить", "payload": "admin_clear_yes"}],
            [{"type": "callback", "text": "Отмена", "payload": "admin_clear_no"}],
        ]
    )

