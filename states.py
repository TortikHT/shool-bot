from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class Step(str, Enum):
    NONE = "none"
    CHILD_FULL_NAME = "child_full_name"
    CHILD_BIRTHDATE = "child_birthdate"
    CHILD_ADDRESS = "child_address"
    KINDERGARTEN = "kindergarten"
    PARENT_FULL_NAME = "parent_full_name"
    PARENT_PHONE = "parent_phone"
    PARENT_EMAIL = "parent_email"
    CONFIRM = "confirm"
    ADMIN_CLEAR_CONFIRM = "admin_clear_confirm"


@dataclass
class ApplicationDraft:
    child_full_name: Optional[str] = None
    child_birthdate: Optional[str] = None
    child_address: Optional[str] = None
    kindergarten: Optional[str] = None
    parent_full_name: Optional[str] = None
    parent_phone: Optional[str] = None
    parent_email: Optional[str] = None
    admission_class: str = "1 класс"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UserState:
    step: Step = Step.NONE
    draft: ApplicationDraft = field(default_factory=ApplicationDraft)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["step"] = self.step.value
        return data

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "UserState":
        step_raw = str(data.get("step", Step.NONE.value))
        step = Step(step_raw) if step_raw in Step._value2member_map_ else Step.NONE
        draft_data = data.get("draft") or {}
        draft_keys = set(ApplicationDraft().__dict__.keys())
        draft = ApplicationDraft(**{k: draft_data.get(k) for k in draft_keys})
        return UserState(step=step, draft=draft)
