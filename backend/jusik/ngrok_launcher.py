"""Validate and discover the password-protected ngrok tunnel used by start.sh."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

API_URL = "http://127.0.0.1:4040/api/tunnels"
TARGET_HOSTS = frozenset({"127.0.0.1", "localhost"})
PUBLIC_SUFFIXES = (".ngrok-free.app", ".ngrok-free.dev", ".ngrok.app", ".ngrok.io")
HOST_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")


class LauncherError(Exception):
    """An error safe to describe without including configuration contents."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(  # type: ignore[override]
        self,
        req: Request,
        fp: object,
        code: int,
        msg: str,
        headers: Mapping[str, str],
        newurl: str,
    ) -> None:
        return None


def validate_policy(path: Path) -> None:
    """Require one exact JSON basic-auth rule and private file permissions."""
    try:
        file_stat = path.lstat()
    except OSError as exc:
        raise LauncherError("ngrok 인증 정책 파일을 찾을 수 없습니다.") from exc

    if not stat.S_ISREG(file_stat.st_mode) or path.is_symlink():
        raise LauncherError("ngrok 인증 정책은 일반 파일이어야 합니다.")
    if file_stat.st_uid != os.getuid() or stat.S_IMODE(file_stat.st_mode) != 0o600:
        raise LauncherError("ngrok 인증 정책 파일의 소유자와 권한(600)을 확인하세요.")
    if file_stat.st_size > 16_384:
        raise LauncherError("ngrok 인증 정책 파일 형식이 올바르지 않습니다.")

    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LauncherError(
            "ngrok 인증 정책은 README의 JSON 형식이어야 합니다."
        ) from exc

    if not isinstance(policy, dict) or set(policy) != {"on_http_request"}:
        raise LauncherError(
            "ngrok 인증 정책은 README의 단일 basic-auth 규칙이어야 합니다."
        )
    rules = policy["on_http_request"]
    if not isinstance(rules, list) or len(rules) != 1:
        raise LauncherError(
            "ngrok 인증 정책은 README의 단일 basic-auth 규칙이어야 합니다."
        )
    rule = rules[0]
    if not isinstance(rule, dict) or set(rule) != {"actions"}:
        raise LauncherError("ngrok 인증 정책에 조건 없는 basic-auth 규칙이 필요합니다.")
    actions = rule["actions"]
    if not isinstance(actions, list) or len(actions) != 1:
        raise LauncherError("ngrok 인증 정책에 basic-auth 동작 하나가 필요합니다.")
    action = actions[0]
    if not isinstance(action, dict) or set(action) != {"type", "config"}:
        raise LauncherError("ngrok 인증 정책의 basic-auth 설정을 확인하세요.")
    if action["type"] != "basic-auth":
        raise LauncherError("ngrok 인증 정책의 basic-auth 설정을 확인하세요.")
    config = action["config"]
    if not isinstance(config, dict) or set(config) != {"credentials", "enforce"}:
        raise LauncherError("ngrok 인증 정책의 basic-auth 설정을 확인하세요.")
    credentials = config["credentials"]
    if (
        config["enforce"] is not True
        or not isinstance(credentials, list)
        or len(credentials) != 1
    ):
        raise LauncherError("ngrok 인증 정책의 basic-auth 강제 적용을 확인하세요.")
    credential = credentials[0]
    if not isinstance(credential, str) or not _valid_credential(credential):
        raise LauncherError(
            "ngrok 인증 정책에 사용자 이름과 비밀번호 한 쌍이 필요합니다."
        )


def _valid_credential(credential: str) -> bool:
    if any(ord(character) < 32 for character in credential):
        return False
    username, separator, password = credential.partition(":")
    return (
        separator == ":"
        and 1 <= len(username) <= 64
        and 8 <= len(password) <= 128
        and "${" not in credential
        and "REPLACE_WITH" not in password.upper()
    )


def _api_payload() -> object | None:
    try:
        with urlopen(API_URL, timeout=1.0) as response:  # noqa: S310 - fixed loopback URL
            return cast(object, json.load(response))
    except HTTPError as exc:
        raise LauncherError(
            "실행 중인 ngrok 관리 API 응답을 확인할 수 없습니다."
        ) from exc
    except URLError as exc:
        reason = exc.reason
        if isinstance(reason, (ConnectionError, TimeoutError, OSError)):
            return None
        raise LauncherError("실행 중인 ngrok 관리 API에 연결할 수 없습니다.") from exc
    except (UnicodeError, json.JSONDecodeError, OSError) as exc:
        raise LauncherError(
            "실행 중인 ngrok 관리 API 응답이 올바르지 않습니다."
        ) from exc


def _is_target(address: object) -> bool:
    if not isinstance(address, str):
        return False
    try:
        parsed = urlsplit(address)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "http"
        and parsed.hostname in TARGET_HOSTS
        and port == 3000
        and parsed.username is None
        and parsed.password is None
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    )


def _safe_public_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    hostname = parsed.hostname or ""
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or not HOST_PATTERN.fullmatch(hostname)
        or not hostname.endswith(PUBLIC_SUFFIXES)
    ):
        return None
    return f"https://{hostname}"


def tunnel_url(payload: object, *, allow_empty: bool = False) -> str | None:
    """Return the one safe HTTPS URL that forwards to the local frontend."""
    if not isinstance(payload, dict) or "tunnels" not in payload:
        raise LauncherError("실행 중인 ngrok 관리 API 응답이 올바르지 않습니다.")
    tunnels = payload["tunnels"]
    if not isinstance(tunnels, list):
        raise LauncherError("실행 중인 ngrok 관리 API 응답이 올바르지 않습니다.")
    if allow_empty and not tunnels:
        return None

    matches: list[str] = []
    for tunnel in tunnels:
        if not isinstance(tunnel, dict):
            raise LauncherError("실행 중인 ngrok 관리 API 응답이 올바르지 않습니다.")
        config = tunnel.get("config")
        if not isinstance(config, dict) or not _is_target(config.get("addr")):
            continue
        public_url = _safe_public_url(tunnel.get("public_url"))
        if public_url is not None:
            matches.append(public_url)

    unique_matches = sorted(set(matches))
    if len(unique_matches) != 1:
        raise LauncherError(
            "실행 중인 ngrok 터널이 로컬 프론트엔드와 안전하게 연결되지 않았습니다."
        )
    return unique_matches[0]


def _probe_auth(public_url: str) -> tuple[int, str | None]:
    request = Request(
        f"{public_url}/.well-known/jusik-auth-check",
        headers={"ngrok-skip-browser-warning": "true"},
    )
    opener = build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=5.0) as response:
            return response.status, response.headers.get("WWW-Authenticate")
    except HTTPError as exc:
        return exc.code, exc.headers.get("WWW-Authenticate")
    except (URLError, OSError) as exc:
        raise LauncherError(
            "ngrok 외부 주소의 인증 상태를 확인할 수 없습니다."
        ) from exc


def inspect_existing(
    api_loader: Callable[[], object | None] = _api_payload,
    auth_probe: Callable[[str], tuple[int, str | None]] = _probe_auth,
    *,
    allow_empty: bool = False,
) -> str | None:
    payload = api_loader()
    if payload is None:
        return None
    public_url = tunnel_url(payload, allow_empty=allow_empty)
    if public_url is None:
        return None
    status, challenge = auth_probe(public_url)
    if status != 401 or challenge is None or not challenge.lower().startswith("basic "):
        raise LauncherError("ngrok 외부 주소에 basic-auth가 강제 적용되지 않았습니다.")
    return public_url


def wait_for_tunnel(timeout: float) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        public_url = inspect_existing(allow_empty=True)
        if public_url is not None:
            return public_url
        time.sleep(0.2)
    raise LauncherError("ngrok 터널이 제한 시간 안에 시작되지 않았습니다.")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("command", choices=("policy", "inspect", "wait"))
    parser.add_argument("policy", type=Path)
    parser.add_argument("timeout", nargs="?", type=float, default=15.0)
    return parser


def main() -> int:
    try:
        arguments = _parser().parse_args()
        validate_policy(cast(Path, arguments.policy))
        command = cast(str, arguments.command)
        if command == "policy":
            return 0
        public_url = (
            inspect_existing()
            if command == "inspect"
            else wait_for_tunnel(arguments.timeout)
        )
        if public_url is None:
            return 3
        print(public_url)
        return 0
    except LauncherError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
