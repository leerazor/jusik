# 자동 공학 발굴 복구 handoff

- 기록 시각: 2026-09-25T22:06:00Z.
- 저장소: `/home/kwl/projects/jusik`, `main`; 기능 통합 `9cb75fc`, 운영 보강 `27d3972`, 첫 제품 `ec77cd4`, 동일 제품 branch 이력 연결 `136f050`.
- 목표: 밤새 고정 목록 소진 상태로 idle만 반복한 원인을 고치고, 다음 공학 과제를 스스로 발굴·검토·구현하게 한다.

## 완료한 변경과 검증

`automatic_engineering_discovery=true` 설치에서 기존 READY·구현 review 다음에 읽기 전용 발굴과 별도 범위 검토를 실행한다. 명시한 8개 모듈의 source/test 쌍 중 하나만 승인·영속 등록하며 기존 구현·독립 완료 review를 사용한다. 같은 입력의 후보는 최대 3개, no_work·변하지 않은 blocker는 LLM을 무의미하게 반복 호출하지 않는다. 투자 게이트와 권한·credential 정책은 변경하지 않았다.

runner 관련 main pytest 240개, Ruff, strict mypy, 별도 Sol review를 통과했다. 운영에서 시장 달력 오류 계약 과제를 발굴했다. 첫 시도는 오프라인 설치 캐시와 잘못된 blocker 출력으로 실패해 원본을 보존했다. 해당 작업 전용 venv를 기존 requirements로 복구하고 실제 dispatch의 안내·출력 schema를 보강했다. 새 시도의 `ec77cd4`와 별도 reviewer PASS를 확인했다. 최종 task는 `ENGINEERING_COMPLETE/NOT_EVALUATED`이며 main 제품 pytest 13개도 통과했다.

## 현재 운영과 보존

기록 저장 중 runner를 pause했고 timer는 계속 활성 상태다. 이 기록 commit 뒤 tracked-clean main에서 재개한다. 재개 후 실제 다음 발굴 상태는 [외부 운영 확인](/home/kwl/.local/share/jusik/portfolio-audit/20260926-engineering-discovery/RUNTIME.md)과 현재 DB를 확인한다. timer 활성만으로 개발 진행을 판단하지 않는다.

완료된 구현·제품 worktree 두 개는 정상 제거했다. branch·commit과 audit 설치 cache는 보존했다. 기존 task 140개·attempt 199개·review 5개는 백업과 동일하고 DB integrity `ok`다. 사용자 미추적 `HANDOFF.md`, 다른 worktree, 과거 실패 기록은 그대로다. 원격 push·실주문·추가 결제·Windows 종료는 하지 않았다. 필요한 사용자 결정은 없다.

세부 근거와 안전한 복구 방법은 [개발 기록](../development-records/2026-09-26-lab-engineering-discovery.md)을 읽는다. 코드 agent 최종 turn의 helper audit에는 log 순서 한계가 있었으며 child 자체 model/effort 근거와 독립 Sol 검토로 대조했다. helper가 모든 turn을 통과했다고 주장하지 않는다.

## 다음 시작

“`docs/handoffs/2026-09-26-engineering-discovery.md`와 연결한 개발 기록·외부 RUNTIME.md를 읽고, Git 상태·runner DB discovery/task·systemd 실행을 확인하라. 활성 runner와 main을 동시에 수정하지 말고, 다음 READY 작업 또는 의미 있는 입력 변화에 따른 발굴이 이어지는지 확인하라. 실주문·투자 기준·권한 변경은 별도 승인 없이 하지 말라.”
