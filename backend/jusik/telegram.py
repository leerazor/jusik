import httpx
from pydantic import SecretStr

from jusik.models import Alert


class TelegramNotifier:
    def __init__(
        self,
        client: httpx.AsyncClient,
        token: SecretStr,
        chat_id: SecretStr,
    ) -> None:
        self.client = client
        self.token = token
        self.chat_id = chat_id

    async def send(self, alert: Alert) -> str:
        text = (
            f"[Jusik] {alert.title}\n{alert.message}\n{alert.market} · {alert.symbol}"
        )
        try:
            response = await self.client.post(
                f"/bot{self.token.get_secret_value()}/sendMessage",
                json={"chat_id": self.chat_id.get_secret_value(), "text": text},
            )
            if response.status_code != 200:
                return "telegram_failed"
            data = response.json()
            return (
                "telegram_sent"
                if isinstance(data, dict) and data.get("ok") is True
                else "telegram_failed"
            )
        except httpx.TimeoutException:
            return "telegram_unknown"
        except (httpx.HTTPError, ValueError):
            return "telegram_failed"
