# 2026-09-24 strict mypy ignore cleanup

## 변경

`backend/jusik/kiwoom_config.py`의 `_env_file` 설정 로딩과 `backend/jusik/main.py`의 환경 기반 `Settings()` 생성에 남아 있던 불필요한 `type: ignore[call-arg]` 및 오해를 부르는 주석을 제거했다. 실행 의미와 환경변수·secret 처리 경계는 변경하지 않았다.

## 검증

- `backend/.venv/bin/mypy jusik --strict`: 153개 source, 오류 없음
- `backend/.venv/bin/ruff check jusik/kiwoom_config.py jusik/main.py`: 통과
- `backend/.venv/bin/python -m pytest -q tests/test_kiwoom.py tests/test_research_config.py`: 32 passed

전체 suite의 남은 held-band 고정 SHA와 immutable archive calendar hash 실패는 별도 provenance drift이며 이번 변경으로 완화하지 않는다.

