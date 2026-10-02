# Alpaca SIP 가격 증거 준비

이 독립 CLI는 보존된 Alpaca SIP `1Day`·`raw` 응답을 오프라인에서 검증하고 일봉과 세션 결손을 정규화한다. [고정 범위](/home/kwl/.local/share/jusik/portfolio-audit/20261002-alpaca-price-evidence/scope.json)의 SHA-256, 원문 두 건, 기존 평가 세션 파일의 SHA-256을 명시적으로 전달해야 한다. 네트워크 요청과 캐시·DB 변경은 없다.

```bash
PYTHONPATH=backend backend/.venv/bin/python -m jusik.alpaca_price_evidence \
  --scope /절대경로/scope.json --scope-sha256 <고정 SHA-256> \
  --assessment /절대경로/assessment.json \
  --batch /절대경로/plain-16-sip-raw.json \
  --single /절대경로/rapt-sip-raw.json \
  --expected-sessions /절대경로/us-1y-exclusions.json \
  --expected-sha256 <고정 SHA-256> --output-dir /새/출력/디렉터리
```

출력 디렉터리는 새 경로여야 한다. 입력 해시·SIP 요청 조건·페이지 완료·RAPT 단건 일치·뉴욕 현지 자정 일봉·272개 고정 세션·가격/거래량/중복을 먼저 검사한다. 성공하면 임시 디렉터리에서 완성한 `normalized-prices.json`, `missing-sessions.json`, `validation.json`, `binding.json`을 함께 게시한다. 가격은 JSON 원문의 십진 정밀도를 문자열로 유지한다. 거래량 0인 봉은 남기고 표시한다. 결손은 첫 봉 전·봉 사이·마지막 봉 후로 나누며, 봉이 없는 종목은 원인을 추정하지 않고 `unanchored_no_bar_sessions`로 둔다.

[실행 결과](/home/kwl/.local/share/jusik/portfolio-audit/20261002-alpaca-price-evidence/results/atomic-final/validation.json)는 22개 추적 종목 중 9개 1,683봉, 응답 0봉 7개, 개별 미조회 6개를 구분한다. 0거래량 봉 84개를 보존했고 RAPT 138봉이 단건 응답과 일치했다. 이 산출물은 `evidence_only`이며 종목 동일성, 배당·분할 관측시각, 역사적 가용시각, 연구 인수 및 성과 적격성을 승인하지 않는다. 가격 결손의 원인이나 수익률을 계산하지 않는다.
