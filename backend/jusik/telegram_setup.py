import argparse
import asyncio
import os
import re
import secrets
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import httpx
from pydantic import SecretStr

from jusik.config import ROOT, TELEGRAM_BOT_TOKEN
from jusik.telegram import send_text

TARGET_KEYS = (
    "TELEGRAM_ENABLED",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)
ASSIGNMENT = re.compile(
    r"^(?P<prefix>\s*(?:export\s+)?(?P<key>TELEGRAM_(?:ENABLED|BOT_TOKEN|CHAT_ID))\s*=\s*)"
    r"(?P<value>.*?)(?P<suffix>\s+(?:#.*)?)?(?P<newline>\r?\n)?$"
)
BOT_USERNAME = re.compile(r"^[A-Za-z0-9_]{5,32}$")
GENERIC_ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*\s*=\s*(.*)$")
TARGET_PREFIX = re.compile(
    r"^(?:TELEGRAM_ENABLED|TELEGRAM_BOT_TOKEN|TELEGRAM_CHAT_ID)(?:\s*=|\s|$)"
)


class SetupError(Exception):
    """A fixed, non-sensitive message safe to show in the setup CLI."""


@dataclass(frozen=True)
class EnvSnapshot:
    path: Path
    content: bytes
    stat: tuple[int, int, int, int]
    values: dict[str, str]


def _stat_signature(path: Path) -> tuple[int, int, int, int]:
    value = path.stat()
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def _parse_value(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in "\"'":
        return stripped[1:-1]
    return stripped


def _starts_multiline_quote(value: str) -> str | None:
    stripped = value.rstrip("\r\n").lstrip()
    if not stripped or stripped[0] not in "\"'":
        return None
    quote = stripped[0]
    escaped = False
    for character in stripped[1:]:
        if character == quote and not escaped:
            return None
        escaped = character == "\\" and not escaped
        if character != "\\":
            escaped = False
    return quote


def _closes_multiline_quote(line: str, quote: str) -> bool:
    escaped = False
    for character in line:
        if character == quote and not escaped:
            return True
        escaped = character == "\\" and not escaped
        if character != "\\":
            escaped = False
    return False


def read_env_snapshot(path: Path) -> EnvSnapshot:
    try:
        content = path.read_bytes()
        signature = _stat_signature(path)
        text = content.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SetupError("로컬 .env.prod 파일을 안전하게 읽을 수 없습니다.") from exc

    values: dict[str, str] = {}
    multiline_quote: str | None = None
    for line in text.splitlines(keepends=True):
        if multiline_quote is not None:
            if _closes_multiline_quote(line, multiline_quote):
                multiline_quote = None
            continue
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        match = ASSIGNMENT.fullmatch(line)
        if match is None:
            generic = GENERIC_ASSIGNMENT.match(line)
            if generic is not None:
                multiline_quote = _starts_multiline_quote(generic.group(1))
            if TARGET_PREFIX.match(stripped):
                raise SetupError(
                    "Telegram 설정 키 형식이 모호해 자동 수정할 수 없습니다."
                )
            continue
        if _starts_multiline_quote(match.group("value")) is not None:
            raise SetupError("Telegram 설정 키 형식이 모호해 자동 수정할 수 없습니다.")
        key = match.group("key")
        if key in values:
            raise SetupError("Telegram 설정 키가 중복되어 자동 수정할 수 없습니다.")
        values[key] = _parse_value(match.group("value"))
    return EnvSnapshot(path=path, content=content, stat=signature, values=values)


def _updated_content(snapshot: EnvSnapshot, token: str, chat_id: str) -> bytes:
    replacements = {
        "TELEGRAM_ENABLED": "true",
        "TELEGRAM_BOT_TOKEN": token,
        "TELEGRAM_CHAT_ID": chat_id,
    }
    text = snapshot.content.decode("utf-8")
    lines = text.splitlines(keepends=True)
    replaced: set[str] = set()
    output: list[str] = []
    multiline_quote: str | None = None
    for line in lines:
        if multiline_quote is not None:
            output.append(line)
            if _closes_multiline_quote(line, multiline_quote):
                multiline_quote = None
            continue
        match = ASSIGNMENT.fullmatch(line)
        if match is None:
            output.append(line)
            generic = GENERIC_ASSIGNMENT.match(line)
            if generic is not None:
                multiline_quote = _starts_multiline_quote(generic.group(1))
            continue
        key = match.group("key")
        output.append(
            f"{match.group('prefix')}{replacements[key]}"
            f"{match.group('suffix') or ''}{match.group('newline') or ''}"
        )
        replaced.add(key)

    newline = "\r\n" if "\r\n" in text else "\n"
    missing = [key for key in TARGET_KEYS if key not in replaced]
    if missing and output and not output[-1].endswith(("\n", "\r")):
        output[-1] += newline
    output.extend(f"{key}={replacements[key]}{newline}" for key in missing)
    return "".join(output).encode("utf-8")


def write_connected_env(snapshot: EnvSnapshot, token: str, chat_id: str) -> None:
    updated = _updated_content(snapshot, token, chat_id)
    temporary_path: Path | None = None
    try:
        if (
            _stat_signature(snapshot.path) != snapshot.stat
            or snapshot.path.read_bytes() != snapshot.content
        ):
            raise SetupError("설정 파일이 실행 중 변경되어 저장하지 않았습니다.")
        descriptor, raw_path = tempfile.mkstemp(
            prefix=f".{snapshot.path.name}.", dir=snapshot.path.parent
        )
        temporary_path = Path(raw_path)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        if (
            _stat_signature(snapshot.path) != snapshot.stat
            or snapshot.path.read_bytes() != snapshot.content
        ):
            raise SetupError("설정 파일이 실행 중 변경되어 저장하지 않았습니다.")
        os.replace(temporary_path, snapshot.path)
        temporary_path = None
        os.chmod(snapshot.path, 0o600)
    except SetupError:
        raise
    except OSError as exc:
        raise SetupError("Telegram 설정을 안전하게 저장하지 못했습니다.") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except OSError:
                pass


class TelegramSetup:
    def __init__(self, client: httpx.AsyncClient, token: SecretStr) -> None:
        self.client = client
        self.token = token

    async def _call(
        self, method: str, *, json: dict[str, object] | None = None
    ) -> dict[str, object]:
        try:
            response = await self.client.post(
                f"/bot{self.token.get_secret_value()}/{method}", json=json
            )
            if response.status_code != 200:
                raise SetupError("Telegram Bot API 요청이 거절되었습니다.")
            data = cast(object, response.json())
        except SetupError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise SetupError("Telegram Bot API 응답을 확인할 수 없습니다.") from exc
        if not isinstance(data, dict) or data.get("ok") is not True:
            raise SetupError("Telegram Bot API 요청이 거절되었습니다.")
        return cast(dict[str, object], data)

    async def bot_username(self) -> str:
        data = await self._call("getMe")
        result = data.get("result")
        if not isinstance(result, dict) or result.get("is_bot") is not True:
            raise SetupError("Telegram 봇 정보를 검증하지 못했습니다.")
        username = result.get("username")
        if not isinstance(username, str) or not BOT_USERNAME.fullmatch(username):
            raise SetupError("Telegram 봇 사용자 이름을 검증하지 못했습니다.")
        return username

    async def ensure_polling_available(self) -> None:
        data = await self._call("getWebhookInfo")
        result = data.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("url", ""), str):
            raise SetupError("Telegram webhook 상태를 검증하지 못했습니다.")
        if result.get("url"):
            raise SetupError(
                "이 봇은 webhook을 사용 중입니다. 기존 연결을 바꾸지 말고 "
                "전용 봇을 사용하세요."
            )

    async def wait_for_challenge(
        self,
        challenge: str,
        *,
        issued_at: int,
        deadline_seconds: int = 120,
        poll_timeout: int = 10,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> SecretStr:
        expected = f"/start {challenge}"
        message_deadline = issued_at + deadline_seconds
        monotonic_deadline = monotonic() + deadline_seconds
        offset: int | None = None
        while (remaining := monotonic_deadline - monotonic()) > 0:
            payload: dict[str, object] = {
                "timeout": min(poll_timeout, max(0, int(remaining))),
                "allowed_updates": ["message"],
            }
            if offset is not None:
                payload["offset"] = offset
            data = await self._call("getUpdates", json=payload)
            updates = data.get("result")
            if not isinstance(updates, list):
                raise SetupError("Telegram 연결 응답을 검증하지 못했습니다.")
            for update in updates:
                if not isinstance(update, dict):
                    continue
                update_id = update.get("update_id")
                if type(update_id) is int:
                    offset = max(offset or 0, update_id + 1)
                message = update.get("message")
                if not isinstance(message, dict) or message.get("text") != expected:
                    continue
                sender = message.get("from")
                chat = message.get("chat")
                sent_at = message.get("date")
                if not isinstance(sender, dict) or not isinstance(chat, dict):
                    continue
                sender_id = sender.get("id")
                chat_id = chat.get("id")
                if (
                    type(sender_id) is int
                    and type(chat_id) is int
                    and sender_id == chat_id
                    and sender.get("is_bot") is False
                    and chat.get("type") == "private"
                    and type(sent_at) is int
                    and issued_at - 5 <= sent_at <= message_deadline
                    and monotonic() <= monotonic_deadline
                    and chat_id > 0
                ):
                    return SecretStr(str(chat_id))
            remaining = monotonic_deadline - monotonic()
            if remaining > 0:
                await sleep(min(0.25, remaining))
        raise SetupError(
            "제한 시간 안에 올바른 휴대폰 연결 응답을 확인하지 못했습니다."
        )


async def run_setup(
    path: Path,
    *,
    send_test: bool,
    output: Callable[[str], None] = print,
    client: httpx.AsyncClient | None = None,
    challenge: str | None = None,
    issued_at: int | None = None,
    deadline_seconds: int = 120,
    poll_timeout: int = 10,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> str | None:
    snapshot = read_env_snapshot(path)
    raw_token = snapshot.values.get("TELEGRAM_BOT_TOKEN", "")
    if not TELEGRAM_BOT_TOKEN.fullmatch(raw_token):
        raise SetupError(".env.prod의 Telegram bot token 형식을 확인하세요.")
    token = SecretStr(raw_token)
    owns_client = client is None
    active_client = client or httpx.AsyncClient(
        base_url="https://api.telegram.org",
        timeout=15,
        follow_redirects=False,
        trust_env=False,
    )
    try:
        setup = TelegramSetup(active_client, token)
        username = await setup.bot_username()
        await setup.ensure_polling_available()
        one_time_challenge = challenge or secrets.token_urlsafe(24)
        started = issued_at if issued_at is not None else int(time.time())
        output(f"@{username} 봇을 확인했습니다.")
        output("휴대폰 Telegram에서 2분 안에 아래 일회용 링크를 열고 시작을 누르세요.")
        output(f"https://t.me/{username}?start={one_time_challenge}")
        chat_id = await setup.wait_for_challenge(
            one_time_challenge,
            issued_at=started,
            deadline_seconds=deadline_seconds,
            poll_timeout=poll_timeout,
            monotonic=monotonic,
            sleep=sleep,
        )
        write_connected_env(snapshot, raw_token, chat_id.get_secret_value())
        if not send_test:
            output("Telegram 설정을 저장했습니다. 테스트 메시지는 전송하지 않았습니다.")
            return None
        delivery = await send_text(
            active_client,
            token,
            chat_id,
            "Jusik Telegram 알림 연결 확인",
        )
        if delivery == "telegram_sent":
            output(
                "Telegram 설정을 저장했고 Bot API가 테스트 메시지를 접수했습니다. "
                "실제 휴대폰 수신 여부는 Telegram 앱에서 확인하세요."
            )
        elif delivery == "telegram_unknown":
            output(
                "Telegram 설정을 저장했습니다. 테스트 메시지 접수 결과는 알 수 없으며 "
                "중복 방지를 위해 다시 보내지 않았습니다."
            )
        else:
            output(
                "Telegram 설정을 저장했습니다. 테스트 메시지는 Bot API에서 "
                "접수되지 않았습니다."
            )
        return delivery
    finally:
        if owns_client:
            await active_client.aclose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Jusik Telegram 알림 연결")
    parser.add_argument(
        "--send-test",
        action="store_true",
        help="연결 저장 후 일반 테스트 메시지를 한 번 전송합니다.",
    )
    args = parser.parse_args()
    try:
        delivery = asyncio.run(run_setup(ROOT / ".env.prod", send_test=args.send_test))
    except (SetupError, KeyboardInterrupt) as exc:
        message = (
            str(exc) if isinstance(exc, SetupError) else "사용자가 연결을 취소했습니다."
        )
        print(message, file=sys.stderr)
        return 1
    return 1 if delivery in {"telegram_failed", "telegram_unknown"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
