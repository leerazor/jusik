# 포트폴리오 GPU allocation screen 입력 차단 기록

- 상태: 완료(문서 기술 slice), 배분 연구: 차단
- 작업 slug: `portfolio-gpu-allocation-screen-42b4`
- 기준/통합: `9945be5d3c8c60c618857b34adb931f0b7e38e1e` / `44f1ff1`
- 범위: 확장 universe allocation 연구의 누락 입력과 재개 조건을 문서화했습니다. 후보 평가·시뮬레이션·GPU stress 결과는 만들지 않았습니다.

## 변경과 결정

- IVV/SGOV point-in-time 가격·세션·분배·FX·total-return 회계 입력이 없어 후보 0, finalist 0, stress 0으로 유지했습니다.
- A/B 설계, 비용·레버리지·chronology·leakage·CPU parity·GPU 자원 상한과 각 gate를 고정했습니다.
- 문서의 모든 성과 필드는 미산출이며 PAPER/live·실주문 승격과 무관합니다.

## 검증

- 문서 diff 및 `git diff --check` — 통과.
- 인용 audit 입력 9개 SHA — 존재 및 일치.
- 독립 문서 검토 — PASS.
- local research backend API와 artifact download — HTTP 200 및 artifact SHA 일치.
- 기본 `/research/history`는 feed pagination으로 신규 entry가 첫 페이지에 즉시 노출되지 않을 수 있어 API `limit=100`과 직접 artifact 경로를 사용해 확인했습니다.

## 안전·운영 상태

- 네트워크 market-data 수집, allocation simulation, GPU, PAPER/live, 주문, DB 변경, runner 설정, remote push — 0회.
- 검증용 local backend/frontend는 확인 후 종료했습니다.

## 증거와 다음 시작

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-gpu-allocation-screen-v1-42b4b5646fe3467394bd0b37d46eac99`; publication은 `publication.json`입니다.
- history artifact SHA: `d43273c15681d0ec8e198fc339a5818ec65f41d062c24f98adf6b0bd9e9e9d43`.
- 다음 시작: 확장 point-in-time 자료와 검증된 total-return 입력이 준비될 때만 최대 32개 후보를 사전등록한 뒤 A/B screen을 재개합니다.

