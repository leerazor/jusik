import asyncio
import csv
import hashlib
import io
import re
import time
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit

import httpx

from jusik.models import MarketIntelligence, NewsItem, SourceStatus

BOK_RATE_URL = "https://www.bok.or.kr/portal/singl/baseRate/list.do?menuNo=200643"
BOK_RSS_URL = "https://www.bok.or.kr/portal/bbs/B0000501/news.rss?menuNo=201264"
FED_RATE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFEDTARL,DFEDTARU"
FED_RSS_URL = "https://www.federalreserve.gov/feeds/press_monetary.xml"
BBC_RSS_URL = "https://feeds.bbci.co.uk/news/world/rss.xml"
TRUTH_RSS_URL = (
    "https://news.google.com/rss/search?q=%22Truth%20Social%22%20when%3A7d"
    "&hl=ko&gl=KR&ceid=KR%3Ako"
)
TRUTH_ARCHIVE_RSS_URL = "https://www.trumpstruth.org/feed"
TRUTH_NAMESPACE = "https://truthsocial.com/ns"
MAX_RESPONSE_BYTES = 1_000_000


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style"}:
            self.ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.parts.append(data)


def _plain_text(value: str | None, *, limit: int = 280) -> str:
    parser = _TextExtractor()
    parser.feed(value or "")
    parser.close()
    text = " ".join(unescape(" ".join(parser.parts)).split())
    return text[:limit]


def _safe_truth_url(value: str | None, *, archive: bool) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value.strip())
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port is not None
            or parsed.query
            or parsed.fragment
        ):
            return None
    except ValueError:
        return None
    if archive:
        if parsed.hostname not in {"trumpstruth.org", "www.trumpstruth.org"}:
            return None
        path_ok = re.fullmatch(r"/statuses/\d+", parsed.path)
    else:
        if parsed.hostname != "truthsocial.com":
            return None
        path_ok = re.fullmatch(
            r"/(?:users/[A-Za-z0-9_]+/statuses/\d+|@[A-Za-z0-9_]+/(?:posts/)?\d+)",
            parsed.path,
        )
    return value.strip() if path_ok else None


def _published(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        return (
            parsed.replace(tzinfo=UTC)
            if parsed.tzinfo is None
            else parsed.astimezone(UTC)
        )
    except (TypeError, ValueError):
        return None


def _assessment(category: str, title: str) -> str:
    lower = title.lower()
    if category in {"korea_rate", "us_rate"}:
        if any(word in lower for word in ("인상", "raise", "higher", "tighten")):
            return "금리 민감 성장주와 부채 비중을 확인하고 변동성 확대에 대비하세요."
        if any(word in lower for word in ("인하", "cut", "lower", "ease")):
            return (
                "금리 민감 자산의 반응을 확인하되 기사 한 건만으로 "
                "비중을 바꾸지 마세요."
            )
        return "공식 금리 결정과 보유 종목의 금리 민감도를 함께 확인하세요."
    if category == "geopolitics":
        return "에너지·방산·운송 노출과 환율 변동을 확인하고 급한 추격매매를 피하세요."
    return "Truth Social 원문과 공식 발표를 교차 확인한 뒤 관련 업종 노출을 점검하세요."


def parse_rss(xml: str, category: str, source: str, limit: int = 5) -> list[NewsItem]:
    root = ET.fromstring(xml)
    result: list[NewsItem] = []
    for item in root.findall(".//item")[:limit]:
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        if not title or not url.startswith("https://"):
            continue
        published = _published(item.findtext("pubDate"))
        identity = hashlib.sha256(f"{category}:{url}".encode()).hexdigest()[:16]
        result.append(
            NewsItem(
                id=identity,
                category=category,
                title=title,
                url=url,
                source=source,
                published_at=published,
                assessment=_assessment(category, title),
            )
        )
    return result


def parse_truth_archive_rss(xml: str, limit: int = 5) -> list[NewsItem]:
    root = ET.fromstring(xml)
    result: list[NewsItem] = []
    for item in root.findall(".//item"):
        archive_url = _safe_truth_url(item.findtext("link"), archive=True)
        if archive_url is None:
            continue
        original_url = _safe_truth_url(
            item.findtext(f"{{{TRUTH_NAMESPACE}}}originalUrl"), archive=False
        )
        raw_title = _plain_text(item.findtext("title"))
        title = (
            "트럼프 계정 게시물 (제목 없음)"
            if not raw_title or raw_title.casefold().startswith("[no title]")
            else raw_title
        )
        excerpt = _plain_text(item.findtext("description")) or None
        published = _published(item.findtext("pubDate"))
        identity = hashlib.sha256(
            f"truth_social_post:{archive_url}".encode()
        ).hexdigest()[:16]
        result.append(
            NewsItem(
                id=identity,
                category="truth_social_post",
                title=title,
                url=archive_url,
                original_url=original_url,
                excerpt=excerpt,
                source="Trump's Truth 제3자 보관본",
                published_at=published,
                assessment=(
                    "제3자 보관본에는 재게시물이 포함될 수 있습니다. 게시물의 주장을 "
                    "실제 정책으로 간주하지 말고 원문과 공식 발표를 교차 확인하세요."
                ),
            )
        )
        if len(result) >= limit:
            break
    return result


def parse_bok_rate(html: str) -> tuple[Decimal, date]:
    table_match = re.search(
        r"<caption>한국은행 기준금리 추이</caption>(.*?)</table>", html, re.DOTALL
    )
    if table_match is None:
        raise ValueError("Rate table missing")
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_match.group(1), re.DOTALL)
    current_year: int | None = None
    candidates: list[tuple[date, Decimal]] = []
    for row in rows:
        cells = [
            unescape(re.sub(r"<[^>]+>", "", cell)).strip()
            for cell in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.DOTALL)
        ]
        for cell in cells:
            if re.fullmatch(r"20\d{2}", cell):
                current_year = int(cell)
        day_cell = next(
            (cell for cell in cells if re.fullmatch(r"\d{2}월\s*\d{2}일", cell)), None
        )
        rate_cell = next(
            (cell for cell in reversed(cells) if re.fullmatch(r"\d+(?:\.\d+)?", cell)),
            None,
        )
        if current_year and day_cell and rate_cell:
            month, day = (int(value) for value in re.findall(r"\d+", day_cell))
            candidates.append((date(current_year, month, day), Decimal(rate_cell)))
    if not candidates:
        raise ValueError("Rate row missing")
    latest_date, latest_rate = max(candidates)
    if latest_date > datetime.now(UTC).date():
        raise ValueError("Future rate date")
    return latest_rate, latest_date


def parse_fed_rate(csv_text: str) -> tuple[str, date]:
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    candidates: list[tuple[date, Decimal, Decimal]] = []
    today = datetime.now(UTC).date()
    for row in reader:
        try:
            observed = date.fromisoformat(row["observation_date"])
            lower = Decimal(row["DFEDTARL"])
            upper = Decimal(row["DFEDTARU"])
        except (KeyError, ValueError, InvalidOperation):
            continue
        if (
            observed <= today
            and lower.is_finite()
            and upper.is_finite()
            and lower <= upper
        ):
            candidates.append((observed, lower, upper))
    if not candidates:
        raise ValueError("Target range missing")
    observed, lower, upper = max(candidates)
    return f"{lower}%–{upper}%", observed


class NewsService:
    def __init__(self, client: httpx.AsyncClient, *, cache_seconds: int = 1800) -> None:
        self.client = client
        self.cache_seconds = cache_seconds
        self._cached: MarketIntelligence | None = None
        self._cached_at = 0.0
        self._lock = asyncio.Lock()
        self._source_cache: dict[str, tuple[str, datetime]] = {}

    async def _get(self, url: str) -> str:
        response = await self.client.get(url)
        response.raise_for_status()
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise ValueError("Response too large")
        return response.text

    async def intelligence(self) -> MarketIntelligence:
        async with self._lock:
            if self._cached and time.monotonic() - self._cached_at < self.cache_seconds:
                return self._cached
            now = datetime.now(UTC)
            sources = (
                ("bok_rate", "한국은행 기준금리", BOK_RATE_URL),
                ("bok_news", "한국은행 통화정책 소식", BOK_RSS_URL),
                ("fed_rate", "미국 연준 목표금리", FED_RATE_URL),
                ("fed_news", "미국 연준 통화정책 소식", FED_RSS_URL),
                ("world", "BBC 국제 소식", BBC_RSS_URL),
                ("truth", "Truth Social 관련 보도", TRUTH_RSS_URL),
                (
                    "truth_archive",
                    "트럼프 계정 게시물 · 제3자 보관본",
                    TRUTH_ARCHIVE_RSS_URL,
                ),
            )
            fetched = await asyncio.gather(
                *(self._get(url) for _, _, url in sources), return_exceptions=True
            )
            statuses: list[SourceStatus] = []
            content: dict[str, str] = {}
            for (source_id, label, url), value in zip(sources, fetched, strict=True):
                if isinstance(value, BaseException):
                    previous = self._source_cache.get(source_id)
                    if previous is not None:
                        content[source_id] = previous[0]
                    statuses.append(
                        SourceStatus(
                            id=source_id,
                            label=label,
                            status="error",
                            source_url=url,
                            fetched_at=previous[1] if previous else now,
                            stale=previous is not None,
                            error=(
                                "갱신에 실패해 이전 수집값을 표시합니다."
                                if previous
                                else "소스를 갱신하지 못했습니다."
                            ),
                        )
                    )
                else:
                    content[source_id] = value
                    self._source_cache[source_id] = (value, now)
                    statuses.append(
                        SourceStatus(
                            id=source_id,
                            label=label,
                            status="ok",
                            source_url=url,
                            fetched_at=now,
                        )
                    )
            korea_rate = None
            korea_date = None
            us_rate = None
            us_date = None
            news: list[NewsItem] = []
            parsers = (
                ("bok_news", "korea_rate", "한국은행"),
                ("fed_news", "us_rate", "Federal Reserve"),
                ("world", "geopolitics", "BBC News"),
                ("truth", "truth_social", "Google News"),
            )
            try:
                korea_rate, korea_date = parse_bok_rate(content["bok_rate"])
            except (KeyError, ValueError):
                self._mark_parse_error(statuses, "bok_rate")
            try:
                us_rate, us_date = parse_fed_rate(content["fed_rate"])
            except (KeyError, ValueError):
                self._mark_parse_error(statuses, "fed_rate")
            for source_id, category, source in parsers:
                try:
                    news.extend(parse_rss(content[source_id], category, source))
                except (KeyError, ET.ParseError):
                    self._mark_parse_error(statuses, source_id)
            try:
                news.extend(parse_truth_archive_rss(content["truth_archive"]))
            except (KeyError, ET.ParseError):
                self._mark_parse_error(statuses, "truth_archive")
            news.sort(
                key=lambda item: item.published_at or datetime.min.replace(tzinfo=UTC),
                reverse=True,
            )
            unique_news: list[NewsItem] = []
            seen_urls: set[str] = set()
            seen_titles: set[str] = set()
            cutoff = now - timedelta(days=30)
            for item in news:
                normalized_title = item.title.casefold()
                if (
                    item.url in seen_urls
                    or normalized_title in seen_titles
                    or (item.published_at is not None and item.published_at < cutoff)
                ):
                    continue
                seen_urls.add(item.url)
                seen_titles.add(normalized_title)
                unique_news.append(item)
            self._cached = MarketIntelligence(
                korea_base_rate=korea_rate,
                korea_rate_as_of=korea_date,
                us_target_rate=us_rate,
                us_rate_as_of=us_date,
                news=unique_news[:25],
                sources=statuses,
                fetched_at=now,
            )
            self._cached_at = time.monotonic()
            return self._cached

    @staticmethod
    def _mark_parse_error(statuses: list[SourceStatus], source_id: str) -> None:
        for index, status in enumerate(statuses):
            if status.id == source_id:
                statuses[index] = status.model_copy(
                    update={
                        "status": "error",
                        "error": "소스 형식을 해석하지 못했습니다.",
                    }
                )
