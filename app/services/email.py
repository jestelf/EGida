from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterable

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "email"
_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_PATH),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_email(template: str, **context: Any) -> str:
    template_obj = _env.get_template(template)
    return template_obj.render(**context)


def build_email_package(subject: str, html_body: str, text_body: str) -> Dict[str, str]:
    return {"subject": subject, "html": html_body, "text": text_body}


def log_email(email: Dict[str, str]) -> None:
    logger.info("Email prepared: %s", {k: v for k, v in email.items() if k != "html"})


def prepare_invite_email(
    *,
    project_name: str,
    organization_name: str,
    inviter_email: str,
    invitee_email: str,
    invite_link: str,
    role: str,
    group_names: Iterable[str],
    expires_at: str,
) -> Dict[str, str]:
    context = {
        "project_name": project_name,
        "organization_name": organization_name,
        "inviter_email": inviter_email,
        "invitee_email": invitee_email,
        "invite_link": invite_link,
        "role": role,
        "group_names": list(group_names),
        "expires_at": expires_at,
    }
    html_body = render_email("invite.html", **context)
    text_body = render_email("invite.txt", **context)
    subject = f"{project_name}: приглашение в {organization_name}"
    return build_email_package(subject, html_body, text_body)


def prepare_password_reset_email(
    *,
    project_name: str,
    user_email: str,
    reset_link: str,
    expires_at: str,
) -> Dict[str, str]:
    context = {
        "project_name": project_name,
        "user_email": user_email,
        "reset_link": reset_link,
        "expires_at": expires_at,
    }
    html_body = render_email("password_reset.html", **context)
    text_body = render_email("password_reset.txt", **context)
    subject = f"{project_name}: восстановление пароля"
    return build_email_package(subject, html_body, text_body)
