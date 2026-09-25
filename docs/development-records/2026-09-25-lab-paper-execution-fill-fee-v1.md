# 오프라인 체결별 수수료 보존

- 상태: 완료
- 기록 시각: 2026-09-25T11:57:48Z
- 작업 slug: `lab-paper-execution-fill-fee-v1`
- 기준/통합: `ded6f33` / `311fed3`
- 범위: 유한 공학 backlog에 명시적 체결 수수료 보존 작업을 추가하고 fake-broker execution journal 계약을 확장했다. 실제 브로커 비용 추정·PnL·주문·PAPER/live 활성화·투자 판정은 제외했다.

## 변경과 결정

- `backend/jusik/development_runner_contract.py`와 backlog 테스트에 네 번째 고정 공학 spec을 등록했다. `8a06611`에서 금액의 유한성 및 NaN/Infinity 거부 요구를 명시했고 별도 Sol 검토 PASS 후 통합했다.
- 자동 구현 `311fed3`은 `backend/jusik/paper_execution_contract.py`의 `Fill`에 선택형 금액·통화 쌍을 추가했다. 금액은 유한한 0 이상 Decimal, 통화는 KRW/USD다. 비용 미상의 legacy 3필드 배열을 계속 읽고 비용이 있으면 5필드로 저장한다. 같은 execution ID의 비용 추가·삭제·변경은 reconciliation에서 거부해 journal을 보존한다.
- 운영 runner의 첫 시도 `dd171f540a6f4cee934ed69456855309`가 제품 커밋 후 독립 review 대기 상태를 거쳤고, 다음 주기 reviewer PASS 후 `DONE/ENGINEERING_COMPLETE/NOT_EVALUATED`가 됐다. 이는 실제 수수료 관측이나 투자 검증이 아니다.

## 문서·계약 영향

- `docs/development-runner.md`의 고정 작업 개수와 운영 reviewer 검증 상태를 갱신했다. `docs/autonomous-trading-lab.md`의 완료된 후속 항목을 현재 상태에 맞춰 좁게 정정했다.
- journal의 기존 3필드 기록을 보존한다. 새 5필드 기록은 구버전 reader가 읽을 수 없으므로 구버전으로 되돌리려면 5필드 기록의 존재 여부를 먼저 확인해야 한다. 실제 broker fee가 체결별 확정값인지, 주문 단위·사후 정정값인지는 아직 확인되지 않아 어댑터에 연결하지 않았다.

## 검증

- spec: backlog pytest 29개, Ruff check/format, 지정 두 파일 strict mypy 통과; 별도 Sol 재검토 PASS.
- 제품: `PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m pytest -q -p no:cacheprovider backend/tests/test_paper_execution_contract.py` — 38 passed.
- 제품 두 파일 Ruff check/format 및 `mypy --strict` — 통과. 비용 미상과 명시적 0의 구분, legacy/new journal 왕복, 불변성 거부 후 journal 보존을 테스트했다.
- 실제 broker/KIS 모의투자·실시간 관측·PnL 대사는 실행하지 않았다.

## 안전·운영 상태

- 실주문·PAPER/live activation·추가 결제·권한/credential 변경·원격 push 없음. runner를 tracked main 편집 중 pause했고, 기록 완료 후 resume한다. timer는 active, 사용자 미추적 루트 `HANDOFF.md`는 보존했다.

## 증거와 재개

- spec 커밋 `8d58a2d`, 수정 `8a06611`, 운영 문서 `b3f2827`, 제품 `311fed3`. 운영 상태는 runner status에서 완료와 투자 미평가를 확인했다.
- 남은 작업: 실제 비용 출처·사후 정정 의미를 확인하기 전 모의 adapter에 비용을 연결하지 않는다. prospective 실제 관찰 수집과 실시간 비용/PnL 대사도 별도 작업이다.
- 다음 시작: Git과 runner READY/idle 상태를 확인하고, 기존 코드에서 독립적으로 재현 가능한 다음 범위 제한 작업을 고른다.
