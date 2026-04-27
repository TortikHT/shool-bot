from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import config
import keyboards
import storage
from states import ApplicationDraft, Step, UserState

logger = logging.getLogger(__name__)


def _normalize_text(text: Optional[str]) -> str:
    return (text or "").strip()


def parse_birthdate(value: str) -> Tuple[Optional[date], Optional[str]]:
    raw = _normalize_text(value)
    try:
        dt = datetime.strptime(raw, "%d.%m.%Y").date()
        return dt, None
    except Exception:
        return None, "Введите дату рождения в формате ДД.ММ.ГГГГ (например, 05.09.2018)."


def _years_between(birth: date, today: date) -> int:
    years = today.year - birth.year
    if (today.month, today.day) < (birth.month, birth.day):
        years -= 1
    return years


def validate_first_grade_age(birth: date) -> Tuple[bool, str]:
    today = date.today()
    age = _years_between(birth, today)
    if age < config.MIN_FIRST_GRADE_AGE_YEARS or age > config.MAX_FIRST_GRADE_AGE_YEARS:
        return (
            False,
            f"Возраст ребёнка сейчас: {age} лет. Для поступления в 1 класс принимаются дети от {config.MIN_FIRST_GRADE_AGE_YEARS} до {config.MAX_FIRST_GRADE_AGE_YEARS} лет.",
        )
    return True, ""


_PHONE_RE = re.compile(r"^\+?[\d\s\-\(\)]+$")


def normalize_ru_phone(value: str) -> Tuple[Optional[str], Optional[str]]:
    raw = _normalize_text(value)
    if not raw:
        return None, "Введите номер телефона."
    if not _PHONE_RE.match(raw):
        return None, "Введите телефон в российском формате (например, +7 999 123-45-67 или 8 999 1234567)."
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if digits.startswith("7") and len(digits) == 11:
        return f"+{digits}", None
    return None, "Телефон должен содержать 11 цифр (например, +7XXXXXXXXXX)."


def _format_application_preview(draft: ApplicationDraft) -> str:
    email = draft.parent_email or "не указан"
    return (
        "Проверьте данные заявки:\n\n"
        f"Класс: {draft.admission_class}\n"
        f"ФИО ребёнка: {draft.child_full_name}\n"
        f"Дата рождения: {draft.child_birthdate}\n"
        f"Адрес проживания: {draft.child_address}\n"
        f"Детский сад: {draft.kindergarten}\n"
        f"ФИО родителя: {draft.parent_full_name}\n"
        f"Телефон: {draft.parent_phone}\n"
        f"Email: {email}\n"
    )


def _admin_only(user_id: int) -> bool:
    return int(user_id) == int(config.ADMIN_ID)


class Handlers:
    def __init__(self, api: "MaxApiClient") -> None:
        self.api = api
        self.user_states: Dict[str, UserState] = storage.load_user_states(config.USER_STATE_PATH)

    def _get_state(self, user_id: int) -> UserState:
        key = str(user_id)
        if key not in self.user_states:
            self.user_states[key] = UserState()
        return self.user_states[key]

    def _save_states(self) -> None:
        storage.save_user_states(config.USER_STATE_PATH, self.user_states)

    def reset_user(self, user_id: int) -> None:
        self.user_states[str(user_id)] = UserState()
        self._save_states()

    def send_main_menu(self, user_id: int) -> None:
        self.api.send_message(user_id=user_id, text=config.WELCOME_TEXT, attachments=keyboards.main_menu_attachments())

    def handle_command(self, user_id: int, chat_id: Optional[int], text: str) -> None:
        cmd = _normalize_text(text).split()[0].lower()
        logger.info("command user_id=%s cmd=%s", user_id, cmd)

        if cmd == "/start":
            self.reset_user(user_id)
            self.send_main_menu(user_id)
            return

        if cmd == "/cancel":
            self.reset_user(user_id)
            self.api.send_message(user_id=user_id, text="Подача заявки отменена.", attachments=keyboards.main_menu_attachments())
            return

        if cmd == "/skip":
            state = self._get_state(user_id)
            if state.step != Step.PARENT_EMAIL:
                self.api.send_message(user_id=user_id, text="Команда /skip доступна только на шаге ввода email.")
                return
            state.draft.parent_email = None
            state.step = Step.CONFIRM
            self._save_states()
            self.api.send_message(
                user_id=user_id,
                text=_format_application_preview(state.draft),
                attachments=keyboards.confirm_attachments(),
            )
            return

        if cmd == "/applications":
            if not _admin_only(user_id):
                self.api.send_message(user_id=user_id, text="Команда доступна только администратору.")
                return
            apps = storage.load_applications(config.APPLICATIONS_PATH)
            if not apps:
                self.api.send_message(user_id=user_id, text="Заявок пока нет.")
                return
            lines: List[str] = []
            for i, app in enumerate(apps, start=1):
                created = int(app.get("created_at", 0))
                created_str = datetime.fromtimestamp(created).strftime("%d.%m.%Y %H:%M") if created else "-"
                lines.append(
                    f"{i}) {created_str} | {app.get('admission_class','1 класс')} | "
                    f"{app.get('child_full_name','-')} | родитель: {app.get('parent_full_name','-')} | {app.get('parent_phone','-')}"
                )
            self.api.send_message(user_id=user_id, text="Список заявок:\n\n" + "\n".join(lines))
            return

        if cmd == "/clear":
            if not _admin_only(user_id):
                self.api.send_message(user_id=user_id, text="Команда доступна только администратору.")
                return
            state = self._get_state(user_id)
            state.step = Step.ADMIN_CLEAR_CONFIRM
            self._save_states()
            self.api.send_message(user_id=user_id, text="Точно очистить все заявки?", attachments=keyboards.admin_clear_attachments())
            return

        self.api.send_message(user_id=user_id, text="Неизвестная команда. Используйте /start.")

    def handle_callback(self, user_id: int, payload: str, callback_id: Optional[str] = None) -> None:
        logger.info("callback user_id=%s payload=%s", user_id, payload)
        if callback_id:
            try:
                self.api.answer_callback(callback_id=callback_id, notification="Готово")
            except Exception:
                logger.exception("answer_callback failed")

        if payload == "menu_apply":
            self.start_application(user_id)
            return

        if payload == "menu_about":
            self.api.send_message(
                user_id=user_id,
                text=f"{config.ABOUT_TEXT}\nАдрес: {config.CITY}, {config.ADDRESS}",
                attachments=keyboards.main_menu_attachments(),
            )
            return

        if payload == "menu_contacts":
            self.api.send_message(user_id=user_id, text=config.CONTACTS_TEXT, attachments=keyboards.main_menu_attachments())
            return

        if payload == "app_confirm_yes":
            self.finish_application(user_id)
            return

        if payload == "app_confirm_edit":
            self.start_application(user_id, restart=True)
            return

        if payload == "app_confirm_cancel":
            self.reset_user(user_id)
            self.api.send_message(user_id=user_id, text="Подача заявки отменена.", attachments=keyboards.main_menu_attachments())
            return

        if payload == "admin_clear_yes":
            if not _admin_only(user_id):
                self.api.send_message(user_id=user_id, text="Команда доступна только администратору.")
                return
            state = self._get_state(user_id)
            if state.step != Step.ADMIN_CLEAR_CONFIRM:
                self.api.send_message(user_id=user_id, text="Сначала используйте /clear.")
                return
            try:
                storage.clear_applications(config.APPLICATIONS_PATH)
                self.reset_user(user_id)
                self.api.send_message(user_id=user_id, text="Все заявки удалены.")
            except Exception:
                logger.exception("clear applications failed")
                self.api.send_message(user_id=user_id, text="Не удалось очистить заявки. Проверьте логи.")
            return

        if payload == "admin_clear_no":
            if _admin_only(user_id):
                self.reset_user(user_id)
                self.api.send_message(user_id=user_id, text="Отмена.")
            return

    def start_application(self, user_id: int, restart: bool = False) -> None:
        recent = storage.count_user_apps_in_window(config.APPLICATIONS_PATH, user_id, config.SPAM_WINDOW_SECONDS)
        if recent >= config.SPAM_MAX_APPLICATIONS_PER_24H:
            self.api.send_message(
                user_id=user_id,
                text="Похоже, вы уже отправили слишком много заявок за последние сутки. Попробуйте позже или свяжитесь со школой.",
                attachments=keyboards.main_menu_attachments(),
            )
            return

        state = self._get_state(user_id)
        state.step = Step.CHILD_FULL_NAME
        if restart:
            state.draft = ApplicationDraft(admission_class=config.ADMISSION_CLASS)
        else:
            if state.draft.admission_class != config.ADMISSION_CLASS:
                state.draft.admission_class = config.ADMISSION_CLASS
        self._save_states()
        self.api.send_message(user_id=user_id, text="Шаг 1/8. Введите ФИО ребёнка (полностью).")

    def handle_text(self, user_id: int, text: str) -> None:
        state = self._get_state(user_id)
        value = _normalize_text(text)

        if not value:
            self.api.send_message(user_id=user_id, text="Пожалуйста, отправьте текст.")
            return

        if value.startswith("/"):
            self.handle_command(user_id=user_id, chat_id=None, text=value)
            return

        if state.step == Step.NONE:
            self.api.send_message(user_id=user_id, text="Используйте /start.", attachments=keyboards.main_menu_attachments())
            return

        if state.step == Step.ADMIN_CLEAR_CONFIRM:
            self.api.send_message(user_id=user_id, text="Подтвердите действие кнопками.")
            return

        if state.step == Step.CHILD_FULL_NAME:
            state.draft.child_full_name = value
            state.step = Step.CHILD_BIRTHDATE
            self._save_states()
            self.api.send_message(user_id=user_id, text="Шаг 2/8. Введите дату рождения ребёнка (ДД.ММ.ГГГГ).")
            return

        if state.step == Step.CHILD_BIRTHDATE:
            birth, err = parse_birthdate(value)
            if err:
                self.api.send_message(user_id=user_id, text=err)
                return
            ok, msg = validate_first_grade_age(birth)
            if not ok:
                self.api.send_message(user_id=user_id, text=msg)
                return
            state.draft.child_birthdate = birth.strftime("%d.%m.%Y")
            state.step = Step.CHILD_ADDRESS
            self._save_states()
            self.api.send_message(user_id=user_id, text="Шаг 3/8. Введите адрес проживания ребёнка.")
            return

        if state.step == Step.CHILD_ADDRESS:
            state.draft.child_address = value
            state.step = Step.KINDERGARTEN
            self._save_states()
            self.api.send_message(user_id=user_id, text='Шаг 4/8. Из какого детского сада переходит? Если не посещал, напишите "не посещал".')
            return

        if state.step == Step.KINDERGARTEN:
            state.draft.kindergarten = value
            state.step = Step.PARENT_FULL_NAME
            self._save_states()
            self.api.send_message(user_id=user_id, text="Шаг 5/8. Введите ФИО родителя (законного представителя).")
            return

        if state.step == Step.PARENT_FULL_NAME:
            state.draft.parent_full_name = value
            state.step = Step.PARENT_PHONE
            self._save_states()
            self.api.send_message(user_id=user_id, text="Шаг 6/8. Введите телефон родителя (российский формат).")
            return

        if state.step == Step.PARENT_PHONE:
            phone, err = normalize_ru_phone(value)
            if err:
                self.api.send_message(user_id=user_id, text=err)
                return
            state.draft.parent_phone = phone
            state.step = Step.PARENT_EMAIL
            self._save_states()
            self.api.send_message(user_id=user_id, text="Шаг 7/8. Введите email (или пропустите командой /skip).")
            return

        if state.step == Step.PARENT_EMAIL:
            state.draft.parent_email = value
            state.step = Step.CONFIRM
            self._save_states()
            self.api.send_message(user_id=user_id, text=_format_application_preview(state.draft), attachments=keyboards.confirm_attachments())
            return

        if state.step == Step.CONFIRM:
            self.api.send_message(user_id=user_id, text="Подтвердите заявку кнопками ниже.", attachments=keyboards.confirm_attachments())
            return

    def finish_application(self, user_id: int) -> None:
        state = self._get_state(user_id)
        if state.step != Step.CONFIRM:
            self.api.send_message(user_id=user_id, text="Сначала заполните заявку.")
            return
        draft = state.draft
        required = [
            draft.child_full_name,
            draft.child_birthdate,
            draft.child_address,
            draft.kindergarten,
            draft.parent_full_name,
            draft.parent_phone,
        ]
        if any(not _normalize_text(v) for v in required):
            self.api.send_message(user_id=user_id, text="Не все обязательные поля заполнены. Начните заново через /start.")
            self.reset_user(user_id)
            return

        application: Dict[str, Any] = draft.to_dict()
        application["user_id"] = int(user_id)
        application["created_at"] = int(time.time())

        try:
            storage.save_application(config.APPLICATIONS_PATH, application)
        except Exception:
            logger.exception("save application failed")
            self.api.send_message(user_id=user_id, text="Не удалось сохранить заявку. Попробуйте позже.")
            return

        self.reset_user(user_id)
        self.api.send_message(user_id=user_id, text="Спасибо! Заявка принята. Мы свяжемся с вами при необходимости.", attachments=keyboards.main_menu_attachments())

        try:
            admin_text = "Новая заявка на поступление в 1 класс:\n\n" + _format_application_preview(draft)
            self.api.send_message(user_id=int(config.ADMIN_ID), text=admin_text)
        except Exception:
            logger.exception("notify admin failed")
