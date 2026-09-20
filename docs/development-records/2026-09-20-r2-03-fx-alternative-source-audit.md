# R2-03 대체 FX 원천 audit

- 상태: ECB 원천 확인·PIT application 미승격
- 기록 시각: 2026-09-20T00:00:00Z
- 작업 slug: `r2-03-fx-alternative-source-audit-20260920`
- 기준/통합: `b268cde` / 통합 예정
- 범위: ECB Data API의 KRW/EUR·USD/EUR reference rates를 키 없이 bounded 조회해 USD/KRW 파생 가능성과 publication metadata를 확인했습니다. 원장·NAV·기존 FX DB는 변경하지 않았습니다.

## 변경과 결정

- `2025-09-11`, `2025-10-13`, `2025-11-11`에는 두 reference rate가 있어 Decimal USD/KRW 파생값을 계산할 수 있었습니다. `2026-04-03`은 두 시계열 모두 관측이 없었습니다.
- ECB CSV에는 관측일·값·상태는 있으나 publication timestamp/first-seen 시각 필드가 없어 거래일 cutoff에 사용 가능했다고 증명할 수 없습니다.
- ECB 파생값은 exploratory evidence로만 보존하며 R2-03 FX application, canonical NAV, Sharpe에는 연결하지 않습니다. ECOS/BOK는 더 직접적인 KRW/USD 원천 후보지만 별도 API key와 source contract가 필요합니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. 기존 FRED-only collector 계약과 readiness를 변경하지 않았습니다.
- 운영 문서: `docs/worktree-tasks.md`에 대체 원천 조사와 차단 조건을 등록합니다.
- API·설정·데이터 계약: `KOREAEXIM_API_KEY` 선택형 collector 설정과
  `NetworkCollectorTransport.koreaexim()`을 추가했습니다. 키가 없으면 네트워크를 호출하지
  않고, 캐시 request key에는 `authkey`를 포함하지 않습니다. 기존 FRED/US 수집 경로와
  readiness·성과 적용은 변경하지 않았습니다. `.env.example`와 `.env.dev.example`에는
  placeholder만 추가해 등록 위치와 alias를 명시했습니다.

## 검증

- ECB Data API bounded requests — HTTP 성공, 3개 경계 날짜 파생 가능, 1개 날짜 missing.
- summary SHA-256: `2d465e7eb8597ad50fcc9d787998327f51b5833cc7cbfb3f6b6e3f63234bb83d`.
- raw KRW/EUR SHA-256: `efcac27cb5f816b82239e4df6de15463dfa34ab6a271e439809028a29cbe3ce1`.
- raw USD/EUR SHA-256: `616edab84efe9d11ccda72f0f874630f7b4680777ef5e3d6cda4c379a2753d2c`.
- Korea Exim parser/transport fixture — collector pytest `144 passed`; Ruff·strict mypy·diff 통과.
- 후속 FX/provenance/accounting/SEC/action/metrics 회귀 bundle — `215 passed`, 경고 2건.

## 안전·운영 상태

- 실주문·PAPER/live 승격·remote push·Windows 종료를 수행하지 않았습니다.
- raw/summary는 `/home/kwl/.local/share/jusik/portfolio-audit/20260920-fx-alternative-source-audit/`에만 저장했습니다.

## 증거와 재개

- 남은 작업·차단 조건: publication/availability timestamp가 있는 FX 원천 또는 승인된 보수적 publication policy가 필요합니다. ECOS API key를 확보하면 BOK 원/달러 종가 계약을 별도로 검증할 수 있습니다. 한국수출입은행 환율 Open API도 무료 대안 후보이며, 신규 `oapi.koreaexim.go.kr` endpoint와 서비스키 신청이 필요하고 실제 공표시각 계약은 별도 확인해야 합니다.
- 서비스키 없이 신규 endpoint를 bounded 호출한 결과는 HTTP 200이지만 `result=3`이고 모든 환율 필드가 null이었습니다. 이는 인증키 부족 증거이며 자료 관측으로 사용하지 않습니다. 응답 SHA-256은 `737f0e0235e82006eaabd9a2fa91dd30f42167d655335fe0cc3b6c24511023e2`입니다.
- 향후 키가 제공될 때의 재사용을 위해 `parse_koreaexim_exchange_response()`와 `KOREAEXIM_URL` 상수를 추가했습니다. parser는 성공한 단일 USD row만 허용하고 키 오류·누락·비수치 rate를 fail-closed하며 기본 availability를 다음 UTC 자정으로 둡니다. 선택형 network collector는 일별 `searchdate` 요청만 준비하며, 실제 키가 없으면 호출하지 않습니다. 경제 결과에는 아직 연결하지 않았습니다.
- 다음 시작: 사용자가 ECOS Open API key를 제공하면 bounded canonical probe를 수행하고, 그 전에는 SEC action review를 계속 진행합니다.
