# ECOS·FRED 원/달러 진단 비교

`backend/jusik/research_ecos_fx_comparison.py`는 고정한 FRED DEXKOUS CSV의 지정 날짜 1~10개를 ECOS `731Y001/D/0000001`의 원/달러 매매기준율과 대조한다. FRED는 뉴욕 정오 매입환율이다. 같은 날짜가 같은 고시 시점을 뜻하지 않으며 차이는 자료 차이 진단값일 뿐 오류나 투자 성과가 아니다.

입력은 `--baseline` CSV, 전체 파일 bytes의 `--baseline-sha256`, 중복 없는 ISO 날짜 `--dates`, 존재하지 않는 `--output-dir`이다. ECOS의 고정 `sample` endpoint만 사용하며 별도 인증값을 읽지 않는다. 예:

```bash
cd backend
.venv/bin/python -m jusik.research_ecos_fx_comparison \
  --baseline /path/to/frozen-DEXKOUS.csv \
  --baseline-sha256 <검증한-64자리-SHA256> \
  --dates 2025-09-11 \
  --output-dir /path/to/new-diagnostic-directory
```

CSV 해시·행·날짜·출력 충돌은 조회 전에 확인한다. 날짜마다 HTTPS GET 한 번만 수행하며 재시도·redirect가 없다. 정상 ECOS JSON 원문만 크기를 제한해 저장하고 SHA-256 및 UTC 조회시각을 JSON 보고서에 기록한다. 결측·오류에는 값을 만들지 않고 FRED의 명시적 결측과 행 부재도 구분한다. 출력은 새 디렉터리의 `comparison.json`, `comparison.md`, 성공 날짜별 원문 JSON이다. 기존 CSV, DB, cache, 전략, readiness는 변경하지 않는다.

ECOS의 공표 시각과 vintage는 확인되지 않았으므로 `publication_at`·`vintage`는 `null`, `point_in_time_verified`와 `eligible_for_performance`는 `false`다. 이 진단을 NAV, 비용 차감 수익률, 전략 선정 또는 PAPER/live 승격에 사용하지 않는다.
