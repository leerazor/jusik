import asyncio
import stat
from pathlib import Path

import httpx
import pytest

import jusik.telegram_setup as telegram_setup
from jusik.telegram_setup import (
    SetupError,
    read_env_snapshot,
    run_setup,
    write_connected_env,
)

TOKEN = "123456789:" + "A" * 35
CHAT_ID = 123456789
ISSUED_AT = 2_000_000_000


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    async def sleep(self, delay: float) -> None:
        self.value += delay


def update(
    *,
    text: str = "/start challenge-code",
    sender_id: int = CHAT_ID,
    chat_id: int = CHAT_ID,
    chat_type: str = "private",
    is_bot: bool = False,
    sent_at: int = ISSUED_AT,
) -> dict[str, object]:
    return {
        "update_id": 10,
        "message": {
            "text": text,
            "date": sent_at,
            "from": {"id": sender_id, "is_bot": is_bot, "first_name": "Private"},
            "chat": {"id": chat_id, "type": chat_type, "title": "Private group"},
        },
    }


def make_env(path: Path) -> bytes:
    content = (
        "# existing comment\r\n"
        "MULTILINE='first\r\n"
        "TELEGRAM_CHAT_ID=must-stay-inside\r\n"
        "last'\r\n"
        "TELEGRAM_ENABLED=false # enabled comment\r\n"
        f'TELEGRAM_BOT_TOKEN="{TOKEN}" # token comment\r\n'
        "OTHER=value\r\n"
    ).encode()
    path.write_bytes(content)
    return content


def make_handler(
    updates: list[dict[str, object]],
    *,
    webhook_url: str = "",
    send_result: httpx.Response | Exception | None = None,
) -> tuple[httpx.MockTransport, list[str]]:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        calls.append(method)
        if method == "getMe":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {"id": 1, "is_bot": True, "username": "JusikTestBot"},
                },
            )
        if method == "getWebhookInfo":
            return httpx.Response(
                200, json={"ok": True, "result": {"url": webhook_url}}
            )
        if method == "getUpdates":
            current = updates.copy()
            updates.clear()
            return httpx.Response(200, json={"ok": True, "result": current})
        if method == "sendMessage":
            if isinstance(send_result, Exception):
                raise send_result
            return send_result or httpx.Response(200, json={"ok": True})
        raise AssertionError("unexpected Telegram method")

    return httpx.MockTransport(handler), calls


def run(
    path: Path,
    transport: httpx.MockTransport,
    *,
    send_test: bool = False,
    deadline_seconds: int = 1,
) -> tuple[str | None, list[str]]:
    output: list[str] = []
    clock = FakeClock()

    async def execute() -> str | None:
        async with httpx.AsyncClient(
            base_url="https://api.telegram.org", transport=transport
        ) as client:
            return await run_setup(
                path,
                send_test=send_test,
                output=output.append,
                client=client,
                challenge="challenge-code",
                issued_at=ISSUED_AT,
                deadline_seconds=deadline_seconds,
                poll_timeout=0,
                monotonic=clock,
                sleep=clock.sleep,
            )

    return asyncio.run(execute()), output


def test_setup_accepts_only_exact_private_human_challenge_and_preserves_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / ".env.prod"
    make_env(path)
    transport, calls = make_handler([update()])

    delivery, output = run(path, transport)

    assert delivery is None
    saved = path.read_text()
    assert "# existing comment\n" in saved
    assert "TELEGRAM_CHAT_ID=must-stay-inside" in saved
    assert "TELEGRAM_ENABLED=true # enabled comment" in saved
    assert f"TELEGRAM_BOT_TOKEN={TOKEN} # token comment" in saved
    assert f"TELEGRAM_CHAT_ID={CHAT_ID}" in saved
    assert "OTHER=value" in saved
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    joined = "\n".join(output)
    assert "https://t.me/JusikTestBot?start=challenge-code" in joined
    assert TOKEN not in joined
    assert str(CHAT_ID) not in joined
    assert "Private" not in joined
    assert calls == ["getMe", "getWebhookInfo", "getUpdates"]


def test_setup_rejects_wrong_target_forgery_bot_and_expired_updates(
    tmp_path: Path,
) -> None:
    path = tmp_path / ".env.prod"
    original = make_env(path)
    invalid = [
        update(text="/start wrong"),
        update(sender_id=11111),
        update(chat_type="group"),
        update(is_bot=True),
        update(sent_at=ISSUED_AT - 10),
    ]
    transport, calls = make_handler(invalid)

    with pytest.raises(SetupError) as error:
        run(path, transport)

    assert path.read_bytes() == original
    assert TOKEN not in str(error.value)
    assert str(CHAT_ID) not in str(error.value)
    assert "sendMessage" not in calls


def test_setup_rejects_active_webhook_without_changing_it_or_saving(
    tmp_path: Path,
) -> None:
    path = tmp_path / ".env.prod"
    original = make_env(path)
    transport, calls = make_handler([], webhook_url="https://private.invalid/hook")

    with pytest.raises(SetupError) as error:
        run(path, transport)

    assert "전용 봇" in str(error.value)
    assert "private.invalid" not in str(error.value)
    assert path.read_bytes() == original
    assert calls == ["getMe", "getWebhookInfo"]


def test_env_update_rejects_duplicates_ambiguity_and_concurrent_change(
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate"
    duplicate.write_text(f"TELEGRAM_BOT_TOKEN={TOKEN}\nTELEGRAM_BOT_TOKEN={TOKEN}\n")
    with pytest.raises(SetupError):
        read_env_snapshot(duplicate)

    ambiguous = tmp_path / "ambiguous"
    ambiguous.write_text(f"TELEGRAM_BOT_TOKEN {TOKEN}\n")
    with pytest.raises(SetupError):
        read_env_snapshot(ambiguous)

    changed = tmp_path / "changed"
    original = make_env(changed)
    snapshot = read_env_snapshot(changed)
    changed.write_bytes(original + b"CHANGED=true\n")
    with pytest.raises(SetupError):
        write_connected_env(snapshot, TOKEN, str(CHAT_ID))
    assert changed.read_bytes().endswith(b"CHANGED=true\n")
    assert not list(tmp_path.glob(".changed.*"))


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (httpx.Response(200, json={"ok": True}), "telegram_sent"),
        (httpx.Response(403, json={"ok": False}), "telegram_failed"),
        (httpx.ReadTimeout("unknown"), "telegram_unknown"),
    ],
)
def test_send_test_sends_at_most_once_and_preserves_unknown(
    tmp_path: Path,
    response: httpx.Response | Exception,
    expected: str,
) -> None:
    path = tmp_path / ".env.prod"
    make_env(path)
    transport, calls = make_handler([update()], send_result=response)

    delivery, output = run(path, transport, send_test=True)

    assert delivery == expected
    assert calls.count("sendMessage") == 1
    assert f"TELEGRAM_CHAT_ID={CHAT_ID}" in path.read_text()
    if expected == "telegram_unknown":
        assert any("다시 보내지 않았습니다" in line for line in output)


def test_without_send_test_never_calls_send_message(tmp_path: Path) -> None:
    path = tmp_path / ".env.prod"
    make_env(path)
    transport, calls = make_handler([update()])

    run(path, transport, send_test=False)

    assert "sendMessage" not in calls


def test_api_rejection_does_not_expose_response_or_credentials(tmp_path: Path) -> None:
    path = tmp_path / ".env.prod"
    original = make_env(path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            text=f"private response {TOKEN} {CHAT_ID}",
        )

    with pytest.raises(SetupError) as error:
        run(path, httpx.MockTransport(handler))

    message = str(error.value)
    assert TOKEN not in message
    assert str(CHAT_ID) not in message
    assert "private response" not in message
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    ("delivery", "exit_code"),
    [(None, 0), ("telegram_sent", 0), ("telegram_failed", 1), ("telegram_unknown", 1)],
)
def test_cli_exit_code_distinguishes_test_delivery_result(
    monkeypatch: pytest.MonkeyPatch,
    delivery: str | None,
    exit_code: int,
) -> None:
    async def fake_run_setup(*args: object, **kwargs: object) -> str | None:
        return delivery

    monkeypatch.setattr(telegram_setup, "run_setup", fake_run_setup)
    monkeypatch.setattr(telegram_setup.sys, "argv", ["telegram_setup"])

    assert telegram_setup.main() == exit_code
