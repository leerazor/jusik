# GPU stress 기존 fixture CPU/CUDA 기술 검증

- 상태: 완료 (`ENGINEERING_COMPLETE/NOT_EVALUATED`; parity와 제한된 처리 시간 확인만 수행)
- 기록 시각: 2026-09-28T05:18:10Z
- 작업 slug: `gpu-stress-fixture-parity-v1`
- 기준/통합: 검증한 실행 코드의 local `main` 기준 `e2c2bbcd228c96db3be4b1e65a940a8096098ab1`; 제품 코드 변경 없이 테스트와 증거만 확인했습니다. 기록·등록부는 별도 문서 closeout으로 통합합니다.
- 범위: 기존 GPU stress 경로와 기존 4-point 합성 test fixture만으로 CPU/CUDA 결과 parity와 실행 시간을 확인했습니다. OOS·전략 튜닝·투자 판단·후보 승인 근거는 만들지 않았습니다.

## 입력과 실행

- 기존 `backend/tests/test_research_portfolio_gpu_stress.py::_request`와 `backend/jusik/research_portfolio_gpu_stress.py`만 사용했습니다. 고정 seed `20260913`, block `2`, horizon `3`, scenario `4096`인 동일 request를 CPU와 CUDA에서 각각 실행했습니다. 새 fixture·시장자료·전략 조건은 만들지 않았습니다.
- request SHA-256은 `8b06abc6d967802090edad52932af60a828245f792ef5a204c897d9e6635b1e1`, 기존 helper가 쓴 source SHA-256은 `9eead0c857a3b1a3540bd52a28f348cf62e5b379e823b797bd9939d0125e68ac`입니다. stress module SHA `397e118c6e7f139c98604f566b8dc5c95830a179a56601876c71845190996a79`, test source SHA `966fb6da3042ef302539e7ec93d635e7c5295826fb1722c641b337fb336cdb84`입니다.
- 최초 paired run은 미리 설치된 root venv를 사용했습니다. 결과는 참고용으로 보존했지만 worktree별 환경 분리 절차를 만족하지 않아 최종 acceptance에서 제외했습니다. 그 뒤 task worktree의 `backend/.venv`를 Python 3.13.15, PyTorch `2.11.0+cu128`/CUDA 12.8, project core `pydantic-settings`, pytest, numpy로 별도 준비했습니다. 공개 package index만 사용했고 유료 자료·서비스나 credential은 사용하지 않았습니다.
- 전용 venv 초기 pytest 시도는 9 passed/8 failed였습니다. 원인은 아직 설치되지 않은 `pydantic`으로 인한 fixture model parse 실패였고 코드·테스트 변경은 없었습니다. 프로젝트 core dependency와 NumPy 설치 뒤 targeted file은 `17 passed in 1.14s`였습니다. 초기 실패와 환경 보완은 외부 audit에 각각 보존했습니다.
- 최종 검증은 기존 request/source를 그대로 재사용하여 전용 venv에서 CPU·CUDA 각 1회 실행했습니다. 양쪽 exit code 0, 선택 device `cpu`/`cuda`, 4096 scenario, 내부 Torch/Decimal tolerance 검사 통과입니다. request/index/result/summary/hash manifest는 CPU와 CUDA 간 동일하고 앞서 보존한 pair와도 같습니다. `indices.json` SHA `671f6e50567d180860cab5961fd18c8ef90ad3fe58c8f671fc44a0ba15b4541c`, `results.json` SHA `96b1463b642f9684d79135450e6748c336c420452e3b704395da339a5d863c4d`, `summary.json` SHA `e661543faff2958cd8e88c3e0e28d9bded3a93a7e34ae1f68a08fc639322fac8`, CPU/CUDA hash manifest SHA `21c1f64999a5eee09815963393ef0017dd476cb570e723f73f4ee3cccfebb4b45`입니다.
- audit directory는 `/home/kwl/.local/share/jusik/portfolio-audit/20260928-gpu-stress-fixture-parity-v1/`입니다. 최초 참고 pair의 `verification.json` SHA `e74e603d4d0dc834179550cead0e22b4e1d271cd0c9ac82e903fe0392848a749`; task-local venv의 최종 `worktree-venv/verification.json` SHA `35b8983c38a1e1a18c0bffa93b60ace3663bb93899fc5b88e4295190ed65d644`입니다. 독립 `role.review`가 task-local Python 환경, paired outputs, manifest, timing 제한과 보존된 audit을 확인해 PASS했습니다. 최종 개발 기록·handoff도 별도 읽기 전용 review에서 PASS했습니다.

## 처리 시간과 해석 한계

- 최종 task-venv pair의 `elapsed_seconds`: CPU `0.085804s`, CUDA `0.361621s`. warmed backend timing: CPU 2/8 thread `0.001976/0.001908s`; CUDA는 host/device transfer 포함·synchronized `0.002719s`. CUDA 실행 안의 CPU 2/8 thread timing은 `0.002639/0.001965s`입니다.
- GPU 이용률은 실행 직전 89%, 종료 뒤 46%였고 memory는 약 11.6 GiB였습니다. GPU 부하가 격리되지 않았으므로 시간은 관측값으로만 보존합니다. 이 3-step synthetic fixture와 단일 pair에서 속도 우위·일반 throughput을 결론내리지 않습니다.
- 기존 code의 회귀 테스트는 task-local venv에서 `17 passed`했습니다. 초기 bootstrap 시도 `9 passed, 8 failed`은 아직 설치되지 않은 Pydantic으로 인한 fixture setup 실패였고, `pydantic-settings` core dependency 설치 후 통과했습니다. 공개 package index에서 무료 dependency bootstrap을 했으며 시장자료·유료 service·credential은 사용하지 않았습니다. source 변경은 없어 별도 lint/type check는 하지 않았습니다.
- explore, plan, code_small, 두 review child 모두에 대해 기존 parent/child JSONL로 routing post audit을 수행했고, 지정 role/model과 일치해 PASS했습니다. 마지막 review의 parent/child link는 `01a0dfc9-d8d7-7240-a2fb-5eeb6fa9e991` / `01a0e662-1313-7e53-9e7f-873f1be4ba11`이며, 마지막 audit은 `check_routing.py post`에서 review / `gpt-6-sol` / actual type `review` / 1 child turn을 확인했습니다. 기존 증거로 확인하지 못한 routing audit 공백은 없습니다.

## 문서·안전·재개

- 사용자/운영 문서와 API·설정·데이터 계약은 바뀌지 않았습니다. 시장/provider 자료, OOS·전략 평가, 구매·credential, PAPER/live·주문은 없었습니다.
- `jusik-research-universe.service`는 계속 inactive였고 설정은 변경하지 않았습니다. 문서 수정을 위해 pause한 roadmap runner는 closeout에서 기존 `paused=false`로 복원했습니다. 마지막 확인은 timer active, runner service inactive, research service inactive였습니다.
- audit의 CLI outputs, fixture hashes, 두 실행 환경·timing, bootstrap 실패/수정 결과와 검증 JSON은 다음 작업자가 재현을 검토할 수 있게 보존했습니다. root `HANDOFF.md`는 수정하지 않았습니다.
- 남은 투자 작업이나 데이터 승인으로 연결하지 않습니다. 이 bounded technical slice는 종료됐고, 이후 GPU stress 검증은 별도 등록 범위가 필요합니다.
