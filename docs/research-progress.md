# 연구 진행 대시보드 백엔드

백엔드는 `GET /api/research/progress`에서 자동 개발 runner의 상태와 검증된 연구 결과 catalog를 한 번에 읽어 준다. 이 응답은 화면 표시용 공개 투영이며, 요청을 보내거나 runner 작업을 변경하지 않는다. 응답에는 원본 prompt, 오류 본문, 파일 경로, PID, evidence가 포함되지 않는다.

## 읽기 원칙

- runner DB는 SQLite URI `mode=ro`로 열고 `PRAGMA query_only=ON`을 적용한 일관 읽기 트랜잭션에서만 조회한다.
- `RunnerStore`를 만들지 않으므로 부모 디렉터리 생성, DDL, migration, 권한 변경이 발생하지 않는다.
- 기본 runner 설정은 `~/.config/jusik/development-runner.json`, DB는 설정의 `state_dir/runner.db`이며, 앱 factory의 `runner_db_path` 주입값이 우선한다.
- service와 timer는 고정된 `systemctl --user is-active` 호출로만 확인한다. DB에 기록된 `running`은 별도로 표시하며 service 생존 여부로 대체하지 않는다.
- 설정·DB가 없거나 잠겨 있거나 스키마가 다르면 해당 runner 상태만 `unavailable` 또는 `invalid`로 반환한다.

## 연구 catalog

`history_dir/progress.json`을 매 요청 다시 읽고 Pydantic으로 검증한다. 기본 디렉터리는 `~/.local/share/jusik/research-history`이며, 앱 factory의 `progress_history_dir`로 테스트 입력을 주입할 수 있다. 잘못된 catalog는 research만 `invalid`로 만들고 runner 응답은 계속 제공한다.

catalog의 금액·수익률·현금·낙폭·레버리지·회전율·비용 값은 유한한 decimal 문자열이어야 한다. 기간은 ISO 날짜이고 비교 ID는 catalog 전체에서 유일해야 한다. 화면용 report 링크는 검증된 `report_artifact_sha256`으로만 구성한다.

이 화면의 연구 결과는 배당·세금 제외 historical price-only 결과이며 미래 성과를 보장하지 않는다. `cash_statistic`은 `mean`과 `median`을 구분해 표시해야 하며, 서로 다른 cohort를 하나의 timeline으로 합치지 않는다.

## 테스트 주입

`create_research_app`은 `runner_config_path`, `runner_db_path`, `progress_history_dir`, `runner_service_probe`를 받는다. probe는 systemd unit 이름을 받아 `active`, `inactive`, `unknown` 중 하나를 반환한다. 테스트는 임시 catalog와 SQLite DB를 사용하고 실제 사용자 설정·상태 파일을 변경하지 않아야 한다.

