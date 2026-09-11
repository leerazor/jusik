# 실험 소스·대조군 검증

`jusik.research_experiment_guard`는 실험 실행 전에 원본과 격리된 변형 소스,
대조군 결과를 읽기 전용으로 검증한다. `sha256_file`과 `verify_hashes`는 파일
바이트가 등록된 SHA-256과 같은지 확인한다. 파일이 없거나 해시가 다르면 검증은
실패한다.

`verify_unheld_entry_source`는 두 소스의 등록 해시를 먼저 확인한 뒤, 변형 파일에
`and positions[symbol] > 0` 한 줄만 추가되었는지 확인한다. 중복 앵커, 앵커가 아닌
추가 변경, 원본에 이미 앵커가 있는 경우를 모두 거부한다. 이 검사는 실제
`research_portfolio_engine.py`를 수정하거나 실행하지 않는다.

`verify_control_output`은 등록된 기대 JSON의 해시와 전체 객체 구조·값을 비교한다.
배열 순서와 객체 키 집합도 비교하며, 불리언과 숫자를 같은 값으로 취급하지 않는다.
`NaN`·무한대와 중복 JSON 키는 유효한 대조군 출력으로 허용하지 않는다. helper는
거래, 이벤트, 데이터베이스, import side effect를 수행하지 않는다.
