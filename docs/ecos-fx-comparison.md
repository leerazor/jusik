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

CSV 해시·행·날짜·출력 충돌은 조회 전에 확인한다. 날짜마다 HTTPS GET 한 번만 수행하며 재시도·redirect가 없다. 정상 ECOS JSON 원문만 크기를 제한해 저장하고 SHA-256 및 본문 수신 후 UTC 조회시각을 JSON 보고서에 기록한다. 결측·오류의 `fetched_at`은 `null`이며 값을 만들지 않는다. FRED의 명시적 결측과 행 부재도 구분한다. 수치가 비정상적이거나 차이 계산이 불가능하면 해당 날짜만 오류로 남긴다. 출력은 새 디렉터리의 `comparison.json`, `comparison.md`, 성공 날짜별 원문 JSON이다. 기존 CSV, DB, cache, 전략, readiness는 변경하지 않는다.

ECOS의 공표 시각과 vintage는 확인되지 않았으므로 `publication_at`·`vintage`는 `null`, `point_in_time_verified`와 `eligible_for_performance`는 `false`다. 이 진단을 NAV, 비용 차감 수익률, 전략 선정 또는 PAPER/live 승격에 사용하지 않는다.

## 공식 항목과 시점 경계

[ECOS 공식 항목 목록의 `731Y001` 첫 10행](https://ecos.bok.or.kr/api/StatisticItemList/sample/json/kr/1/10/731Y001)에서 `ITEM_CODE=0000001`, `CYCLE=D`, `ITEM_NAME=원/미국달러(매매기준율)`, `UNIT_NAME=원`을 확인했다. **이 조회 응답에는** 최초 공표시각이나 과거 수정본을 구분할 vintage 필드가 없다. 다른 ECOS 기능까지 없다고 판단한 것은 아니다.

[한국은행 매매기준율 FAQ](https://www.bok.or.kr/portal/bbs/P0001949/list.do?menuNo=200156&pageIndex=3)는 최근 거래일에 중개된 미달러 현물환율을 거래량으로 가중평균하는 기준이라고 설명한다. 이는 일반적인 산정 기준이며, 각 ECOS 관측일이 어느 기초 거래일에 대응하는지, 정확히 언제 갱신됐는지, 과거 값이 어떻게 수정됐는지는 확정하지 못한다. FRED DEXKOUS의 뉴욕 정오 매입환율과 기준도 다르므로 ECOS 값으로 FRED 결측을 자동 보충하거나 NAV·성과 입력으로 승격하지 않는다. 임의의 1일 지연도 최초 사용 가능 시점의 증거가 아니다.

PIT 적용 검토는 관측일과 기초 거래일의 의미, 공표 시간대와 최초 사용 가능 시점, 수정 이력·vintage 자료, 기존 FX 적용 계약의 날짜·환율 기준·비용 정합성을 확인한 뒤 재개한다. 확인 전에는 현재 진단 등급을 유지한다.
