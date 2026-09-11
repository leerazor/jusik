# 전략 연구 백엔드

전략 연구 기능은 기존 실계좌 조회 백엔드와 분리된 모의 검증 서비스입니다. KIS 모의투자 앱 키로 선택한 국내주식 1~10개의 과거 일봉을 읽고 추세·거래량 전략을 같은 조건에서 비교합니다. 실시간 시세도 읽기 전용이며 증권사 주문 API는 구현하지 않습니다. 사용자가 승인한 체결은 앱 내부 paper 원장에만 기록됩니다.

## 실행

### 사용자 운용 기준 (2026-09-10)

사용자가 확정한 운용 예정 금액은 1억 원이며, 감내 가능한 최대 손실은 전체 포트폴리오의 고점 대비 20%, 레버리지 ETF의 합산 비중 상한은 전체 순자산의 20%입니다. 레버리지 비중은 상품 평가금액 기준이며 배수 환산 노출과 구분합니다. 향후 전략 비교는 이 기준을 사용합니다. 20%는 사용자 위험 허용 한도이며, 손실이 반드시 그 이내로 제한된다는 보장은 아닙니다.

현재 진행 중인 PAPER 세션은 초기 자금 1억 원, 레버리지 상한 20%, 낙폭 대응 기준 10%로 고정되어 있습니다. 사용자 허용 한도와 전략의 실제 방어 기준은 구분하며, 기존 세션의 비교 가능성을 위해 이번 기준 기록에서 실행 정책이나 원장을 변경하지 않았습니다. 더 높은 낙폭 대응 기준은 별도 후보 검증 후 반영합니다.

저장소 루트의 `.env.dev`에 KIS 모의투자 앱 설정이 있어야 합니다. 연구 서비스는 이 파일만 명시적으로 읽으며 프로세스 환경의 KIS 변수와 `.env.prod`를 사용하지 않습니다. 공식 모의투자 호스트 `https://openapivts.koreainvestment.com:29443`만 허용합니다. 계좌번호는 읽지 않습니다.

```bash
backend/.venv/bin/python -m uvicorn jusik.research_app:app \
  --app-dir backend --host 127.0.0.1 --port 8001 --no-access-log
```

프론트엔드는 기본적으로 `http://127.0.0.1:8001`을 조회합니다. 다른 로컬 포트를 쓰려면 프론트엔드 프로세스에 `JUSIK_RESEARCH_BACKEND_URL`을 지정합니다. 브라우저에서 `http://localhost:3000/research`를 엽니다.

연구 실행은 SQLite의 `~/.local/share/jusik/research.db`에 대상 종목, 일정, 요청, 입력 스냅샷, 결과, 전략 버전, 신호 제안, paper 현금·포지션·체결을 저장합니다. worker 하나가 최대 10개의 대기 작업을 순서대로 처리하고, 시작하지 못한 대기 작업은 재시작 후 이어갑니다. 수집·계산 중 중단된 작업은 실패로 명시합니다. 완료된 실행의 재생은 외부 데이터를 다시 받지 않고 저장된 불변 입력을 사용합니다.

## 백그라운드 전략 최적화

오프라인 optimizer는 완료된 연구의 저장 스냅샷만 읽어 이동평균·거래량 44개, 모멘텀 9개, 직전 고가 돌파 3개, 평균 회귀 9개, 기존 소형 PyTorch MLP 3개, RSI 눌림목 9개, ATR 추세 9개와 비용 인식 MLP 3개를 포함한 기존 89개 후보를 계속 비교합니다. universe 연구에는 아래의 20일 추세 대조군과 외부 변수 filter 3개를 뒤에 붙여 총 93개를 평가합니다. 기존 89개의 ID·파라미터·계산 순서는 유지합니다. 증권사, OpenAI, paper 원장과 주문 경로를 호출하지 않습니다. 원본 `research.db`는 read-only 모드로 열고 결과는 별도 `~/.local/share/jusik/research-optimizer.db`와 `~/.local/share/jusik/optimizer-artifacts`에 저장합니다.

기본 백엔드 의존성을 설치한 뒤 CUDA 12.8 optimizer 의존성을 별도로 설치합니다.

```bash
backend/.venv/bin/python -m pip install -r backend/requirements.optimizer-cu128.lock
```

한 번만 탐색하거나 상태와 중지를 확인하는 명령은 다음과 같습니다. `--device cuda`는 CUDA가 실제로 사용 가능하지 않으면 안전하게 실패합니다. GPU가 없을 때 CPU로 실행하려면 `--device cpu`, 자동 선택은 `--device auto`를 사용합니다.

```bash
cd backend
.venv/bin/python -m jusik.research_optimizer run --once --device cuda
.venv/bin/python -m jusik.research_optimizer status
.venv/bin/python -m jusik.research_optimizer stop
```

`run`의 기본 검증 방식은 아래의 walk-forward입니다. 기존 단일 60/20/20 분할을 재현해야 할 때만 `--validation-mode single`을 명시합니다. 단일 방식에는 아래 연구용 위험 정책을 적용하지 않아 기존 저장 결과와 계산 의미를 유지합니다.

```bash
.venv/bin/python -m jusik.research_optimizer run --once \
  --device cpu --validation-mode single
```

지속 실행은 사용자 systemd service로 관리하는 것을 권장합니다. 설치된 `jusik-research-optimizer.service`는 아래처럼 제어합니다.

```bash
systemctl --user start jusik-research-optimizer
systemctl --user status jusik-research-optimizer
systemctl --user restart jusik-research-optimizer
systemctl --user stop jusik-research-optimizer
journalctl --user -u jusik-research-optimizer -f
```

systemd를 사용하지 않는 임시 실행은 로그 경로를 만든 뒤 분리 실행할 수 있습니다.

```bash
mkdir -p ~/.local/state/jusik
cd backend
setsid nice -n 10 .venv/bin/python -m jusik.research_optimizer \
  run --device cuda >~/.local/state/jusik/research-optimizer.log 2>&1 < /dev/null &
```

프로세스 lock은 optimizer 하나만 실행되게 합니다. 후보마다 결과를 저장하므로 중단 후 같은 입력과 코드로 다시 실행하면 완료 후보를 건너뜁니다. 수집 시각만 다른 같은 데이터는 한 번만 계산합니다. 코드, 요청, 데이터 내용, 후보 설정, Python·PyTorch·CUDA 버전 또는 장치 선택이 달라지면 새 탐색으로 기록합니다. 상태의 heartbeat가 3분 넘게 갱신되지 않은 실행은 `stale`로 표시합니다.

기본 walk-forward 검증은 요청 기간의 거래일을 확장 학습 120일, 검증 40일, OOS(out-of-sample) 40일로 나누고 40일씩 전진합니다. 최소 240개의 요청 기간 거래일과 그 앞의 지표 준비 일봉 60개가 있어야 두 fold를 만들 수 있습니다. 예를 들어 244일이면 두 fold를 평가하고 마지막 4일은 사용하지 않으며, 상태에 이 tail을 표시합니다. 각 fold는 현금과 위험 상태를 초기자금으로 다시 시작하므로 fold 수익률을 인위적으로 복리 연결하지 않습니다.

각 fold에서 설정된 후보를 모두 검증합니다. MLP는 fold별 학습 구간만으로 별도 표준화·학습하고, 학습 경계를 넘는 다음 시가 라벨을 버리며, 모델 artifact도 fold별로 분리합니다. 검증 점수는 `수익률 - 최대 낙폭`이고 거래가 없는 후보를 제외하며 후보 ID로 동률을 결정합니다. 검증 승자를 데이터베이스에 먼저 고정한 다음 그 승자와 20일 기준 전략만 OOS에서 평가합니다. 중단 후 재시작해도 완료 후보와 fold를 건너뛰고 이미 고정한 승자를 바꾸지 않습니다. OOS를 본 뒤 후보를 다시 선택하지 않습니다. 이 시간순 확장 방식은 [scikit-learn TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)과 같은 계열의 검증 원칙을 따릅니다.

비용 인식 MLP 3개까지의 기존 실행에서는 fold마다 89개 후보를 검증합니다. 기존 MLP 3개의 7개 입력 특성, 1일 방향 라벨, 학습·추론 경로와 artifact 형식은 바꾸지 않습니다. 새 MLP는 기존 7개 특성에 최근 5일·20일 일간 수익률 표준편차와 최근 20일 `(수정고가-수정저가)/수정종가` 평균을 더한 10개 특성을 사용합니다. 입력 표준화는 각 fold 학습 구간에서만 계산합니다. hidden 16, epoch 32, learning rate 0.005, weight decay 0.01과 고정 seed를 사용해 모델 규모를 미리 제한합니다.

새 라벨은 신호일 다음 수정시가에 진입해 1일 또는 5일 뒤의 다음 수정시가에 청산한다고 가정한 순수익이 양수인지 나타냅니다. 진입에는 슬리피지와 매수 수수료, 청산에는 슬리피지·매도 수수료·매도세를 반영하며 청산 시가가 학습 종료일을 넘는 표본은 버립니다. 후보는 1일 horizon·0.55, 5일 horizon·0.55, 5일 horizon·0.60 확률 임계값 조합입니다. 이 horizon은 라벨 가설일 뿐 최소 보유기간이 아니며, 실제 보유 신호는 매일 다시 계산합니다. 출력값은 별도 calibration을 거치지 않았으므로 실제 상승 확률로 해석하지 않습니다.

walk-forward에는 fold마다 같은 연구용 위험 정책을 적용합니다. 신규 진입 예산은 해당 시가의 고정 평가액을 기준으로 종목당 20%, 전체 60%이며, 기존 균등 배분 한도·남은 현금·비용·정수 수량 제한도 함께 적용합니다. 같은 시가의 동시 매수는 누적 예산을 차감합니다. 진입 뒤 가격 gap이나 비용 때문에 시가·종가 기준 노출 비율이 한도를 넘을 수 있으며 이 초과는 상태에 기록할 뿐 강제 축소하지 않습니다. 따라서 이 비율은 계속 유지되는 포트폴리오 한도가 아닙니다.

종가 평가액이 fold의 종가 기준 고점보다 10% 이상 하락하면 위험 상태를 fold 끝까지 고정합니다. 대기 중인 매수를 취소하고 보유분을 다음 거래 가능한 시가에 매도하도록 예약합니다. 일봉이 없거나 거래량이 0이면 청산도 다음 거래 가능 일봉까지 남아 있으며 새로 진입하지 않습니다. 종가 확인 뒤 다음 시가에 청산하므로 최대 낙폭이 10%를 넘지 않는다고 보장하지 않습니다. 상태에는 발동일·발동 낙폭·남은 포지션과 관찰된 노출 초과를 기록합니다.

fold OOS 합격에는 승자의 거래가 하나 이상이고, 수익률이 기준 이상이며, 최대 낙폭이 기준 이하이면서 10% 이하인 조건을 모두 요구합니다. 최소 두 fold가 모두 통과하면 상태에 연구 비교 조건 충족으로 표시하고 평균·최저 OOS 수익률, 최대 낙폭, 평균 초과 수익률과 승리 fold 수를 함께 보여 줍니다. 이는 자동 거래 준비 또는 실전 적합 판정이 아닙니다.

RSI 눌림목 후보는 수정종가가 60일 이동평균보다 높은 동안 7·14·21일 Wilder RSI가 각각 30·40·45 이하인 조합을 보유 조건으로 사용합니다. 첫 구간의 상승분과 하락분 평균으로 초기화한 뒤 Wilder 재귀 평활을 적용합니다. ATR 추세 후보는 수정종가가 20일 이동평균보다 높고 10·14·20일 Wilder ATR을 수정종가로 나눈 값이 각각 3%·5%·8% 이하인 조합을 사용합니다. ATR true range에는 전일 수정종가와 당일 수정고가·수정저가 사이의 상승·하락 gap을 모두 포함합니다. 계산식은 [Fidelity RSI 안내](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/RSI)와 [Fidelity ATR 안내](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/atr)를 따릅니다.

두 조건은 매일의 목표 보유 상태입니다. 조건이 거짓으로 바뀌면 다음 거래 가능 시가에 청산하며, 신규 진입 때만 확인하는 filter나 고정 손절 규칙으로 해석하지 않습니다.

최적화 결과는 저장된 후보 집합과 기간에서의 실험 결과일 뿐 모든 시장에서 가장 좋은 거래 로직을 보장하지 않습니다. 같은 과거 데이터에서 반복한 walk-forward OOS는 새로 도착한 미래 데이터가 아니며, 일별 스냅샷의 날짜 구간이 겹치면 결과도 서로 독립적인 전진 검증 증거가 아닙니다. 현재 평가 데이터는 2개 종목에 한정되고 공식 거래소 달력도 없어서 전체 시장·상장폐지 종목·공통 누락 거래일을 대표하지 않습니다. optimizer는 결과를 paper 전략으로 자동 선택하거나 실전 거래에 승격하지 않습니다.

## 3년 종목별 universe 연구

`research_universe`는 기존 국내 paper 연구와 분리된 오프라인 수집·탐색 경로입니다. 삼성전자(`005930`), SK하이닉스(`000660`), 한국 ETF 4개(`487230`, `487240`, `0173Y0`, `0190C0`)와 미국 종목 10개(`SOXL`, `NVDA`, `GOOGL`, `COHR`, `TQQQ`, `MSFT`, `ARM`, `AMD`, `GEV`, `VRT`)를 native ticker 그대로 추적합니다. 각 종목을 별도 현금 계정으로 평가하며 KRW와 USD 손익을 합산하지 않습니다. 기존 paper 요청 모델의 6자리 국내 종목 제한과 주문 없는 구조는 그대로 유지합니다.

```bash
cd backend
.venv/bin/python -m jusik.research_universe run --once --device cuda
.venv/bin/python -m jusik.research_universe collect-external
.venv/bin/python -m jusik.research_universe status
.venv/bin/python -m jusik.research_universe report
.venv/bin/python -m jusik.research_universe stop
```

지속 실행은 기존 optimizer와 같은 SQLite control과 process lock을 사용합니다. 따라서 두 optimizer를 동시에 실행하지 않습니다. 서비스는 외부 자료를 6시간마다 확인하고 16개 종목은 하루 간격으로 갱신한 뒤 평가 가능한 종목을 순서대로 처리합니다. 수집 원문과 정규화 스냅샷은 `~/.local/share/jusik/research-universe.db`, 외부 자료 원문·revision은 `~/.local/share/jusik/research-external.db`, 탐색 결과는 기존 `~/.local/share/jusik/research-optimizer.db`, 보고서는 `~/.local/share/jusik/research-universe-reports`에 저장합니다. 같은 내용은 다시 계산하지 않고 fold·후보 checkpoint부터 재개합니다.

## 통합 포트폴리오 연구

## 전진 PAPER 관찰과 개발 이력

`/research/forward`는 과거 결과의 보유나 손익을 가져오지 않고 활성화 시점의
1억원 현금으로 시작하는 별도 PAPER 원장이다. 검증 구간에서 고정한
`portfolio_inverse_volatility_fx_vix_v1`과 `low_turnover_combined` 정책만 사용한다.
월요일 00:00 UTC 정기 판단은 28일 간격이며, 마감 전에 저장된 일봉·외부 변수
버전만 참조한다. 재시작이 15분을 넘기거나 입력이 없으면 과거 결정을 합성하지
않고 누락 사건을 기록한다.

실시간 관찰은 기존 `KisReadOnlyStream` 연결 한 개에서 16종목을 다중 구독한다.
국내 `H0STCNT0` 46필드와 미국 `HDFSCNT0` 공식 25필드 및 레거시 26필드만
허용한다. 제어 메시지의 `encrypt` 값으로 평문 여부를 판정하며 주문통보나 암호화
payload는 처리하지 않는다. 구현 계약은 한국투자증권의
[공식 Open Trading API 저장소](https://github.com/koreainvestment/open-trading-api)를
고정 커밋으로 읽어 확인했다. 미국 무료 시세의 지연 표시는 0분을 사용하지만 실제
전달 지연을 보장하지 않는다.

구독 요청은 공식 고정 커밋의 해외주식 WebSocket 예제와 같이 하나의 기존 소켓에서
0.5초 간격으로 전송하며, 별도 수신 루프는 송신 중에도 ACK·PING·시세를 계속
처리한다. 각 연결 시도마다 전송 대기, 승인 대기, 승인됨, 거부 단계를 새로 기록하고
요청·전송 시작·응답·첫 시세 UTC 시각을 분리한다. 마지막 요청 전송 후 10초가 지나도
응답이 없으면 `승인 확인 지연`으로 표시할 뿐 거부나 미지원으로 추정하지 않는다.
한 종목이라도 승인되면 나머지 응답을 기다리기 위해 연결을 끊지 않는다. 이전 연결의
시세와 카운터는 새 연결의 수신 증거로 사용하지 않는다.

`H0STCNT0`, `HDFSCNT0`별 데이터 프레임, 유효 시세, 검증 실패 수는 제한된 정수
카운터로만 공개한다. 원문 제어 메시지, 승인키, 예외 본문은 저장하거나 화면에
노출하지 않는다. 승인 ACK만 있고 첫 시세가 없는 상태는 `승인됨·첫 시세 대기`로
표시한다. 이 상태만으로 장외 시간, 권한, 서버 문제 등 원인을 단정하지 않으며 이번
구현 자체도 미국 실제 시세 도착을 확인했다는 증거로 사용하지 않는다.

전진 PAPER의 정규장 시세 적격성, 확정 종가 checkpoint, 보유 종목 종가 선택,
분할 차단 시작 시각은 저장소에 포함된 XKRX·XNYS 고정 달력을 함께 사용한다.
달력은 `exchange_calendars==4.12`를 격리된 생성 환경에서 실행해
2023-01-01~2026-12-31의 모든 현지 날짜를 `session`, `closed`, `unavailable`로
명시한다. NAS·NYS·AMS는 XNYS 공통 정규장 일정으로 판단한다. 누락·중복·잘못된
UTC 시각·지원 범위 밖 날짜·파일 SHA 불일치는 평일 고정 시각으로 대체하지 않고
관련 체결과 전체 포트폴리오 평가를 차단한다. 폐장 시각의 시세는 기존 의미대로
포함한다.

XKRX 4.12의 수능일 특별 시간이 2020년까지만 포함되어 있어 2023~2025년은 각
연도의 확인된 증권사 공지에 따라 10:00~16:30 KST를 생성 metadata에 명시했다.
2026-11-19는 교육부가 시험일을 공지했지만 거래소 시간이 아직 확인되지 않아
`unavailable`로 두었다. 확인 전에는 그 날짜를 정상 세션으로 추정하지 않는다.
지원 종료 전에 새 공휴일·임시 휴장·특별 시간을 공식 거래소 공지와 대조하고,
새 버전과 SHA를 검증한 뒤 다시 배포해야 한다. 런타임은 범위를 자동 연장하지 않는다.

재생성은 서비스 가상환경과 분리된 임시 Python 3.13 환경에서만 수행한다. pandas와
numpy는 생성 과정의 전이 의존성이며 서비스 requirements에는 추가하지 않는다.

```bash
cd backend
CALENDAR_VENV="$(mktemp -d /tmp/jusik-market-calendar.XXXXXX)"
python3.13 -m venv "$CALENDAR_VENV"
"$CALENDAR_VENV/bin/python" -m pip install \
  -r scripts/market-calendar-requirements.txt
"$CALENDAR_VENV/bin/python" scripts/generate_market_calendar.py
```

생성 후에는 NYSE 공식 휴장·조기 폐장과 KRX 공식 공지의 특별 세션을 다시 대조하고,
backend 테스트와 웹 상태의 provider version·지원 범위·파일 SHA를 확인한다. 예정
달력은 발표 뒤 생길 임시 휴장을 모두 보장하지 않으므로 공지가 바뀌면 생성기 override,
원천 URL, 테스트를 함께 갱신한다.

결정 뒤 처음 도착한 15초 이내 정규장 시세로 정수 수량 전량 체결을 가정한다.
부분 체결, 주문장 깊이, 시장 충격은 모델링하지 않으며 실제 브로커 주문 경로를
호출하지 않는다. USD 평가는 일별 USD/KRW 대용치를 사용한다. 10% 낙폭 판단은
활성화 이후 새로 확인한 종가 체크포인트 원장으로만 수행하고 장중 값은 경보로만
남긴다. 따라서 10% 평생 손실 보장이나 자동매매 적격성을 뜻하지 않는다.
USD/KRW 관측이 7일을 넘으면 평가와 체결을 차단한다. 기업행동은 운영자가 원문과
증거 SHA-256을 확인하고 효력 거래일의 실제 개장 전에 등록한 정수 정방향 분할만
지원한다. 법적 기준일이 아니라 분할 수정 거래가 시작되는 XKRX·XNYS 개장 UTC
시각을 효력 시각으로 쓴다. 등록 시각과 원문 관측 시각이 효력 시각보다 늦거나,
거래소 달력의 실제 개장과 다르면 등록을 거부한다. 역분할, 소수 수량, noop, 배당
현금과 현금 정산은 계속 차단한다. 비동시 시장과 매도 비용 때문에 다른 보유가 일시적으로 한도를
넘으면 `cap_constraint_deferred` 사건에 종목과 범위를 기록한다. 정기·시세 워커의
내부 오류는 예외 본문을 저장하지 않고 채널, 고정 오류 코드, UTC 시각만 상태에 남긴다.

검증 manifest는 자동 수집물이 아니다. 운영자가 보관한 증거 파일의 식별자와
SHA-256, HTTPS 원문, 실제 관측 시각, 명시적 검증 표시를 직접 작성한다. 빈 events
배열은 현재 등록할 분할이 없다는 정상 상태다. 아래 값은 형식 설명용이며 실제
등록에는 검증한 원문, 증거 hash, 미래 효력 시각을 넣는다.

```json
{
  "schema_version": 1,
  "events": [
    {
      "symbol": "NVDA",
      "exchange": "NAS",
      "numerator": 10,
      "denominator": 1,
      "source_url": "https://www.sec.gov/example",
      "evidence_id": "operator-archive-id",
      "evidence_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "operator_verified": true,
      "observed_at": "2026-11-30T12:00:00Z",
      "effective_at": "2026-12-01T14:30:00Z"
    }
  ]
}
```

manifest의 `exchange`는 시세 화면과 같은 `KRX`, `NAS`, `NYS`, `AMS` 값이다.
등록 명령은 현재 시스템 UTC를 별도 `registered_at`으로 저장하며 이를 덮어쓰는 CLI
옵션은 없다. 다음 명령은 등록만 하며 주문 API를 호출하지 않는다.

```bash
backend/.venv/bin/python -m jusik.research_corporate_actions \
  --db "$HOME/.local/share/jusik/research-forward.db" \
  --session "<active-forward-session-id>" \
  --manifest "/path/to/operator-verified-splits.json"
```

워커는 tick, 시세 저장, checkpoint보다 먼저 등록된 due event를 적용한다. 같은
세션·종목·효력 시각은 동일한 경제 사건이며 같은 증거의 재등록과 재시작 적용은
멱등이다. 비율이나 증거가 달라지면 충돌로 거부한다. 효력 시각 이후 체결이나
checkpoint가 이미 있으면 소급 수정하지 않고 차단한다. 보유가 없어도 0주에서 0주로
처리해 이후 매수가 다시 분할되지 않게 한다. 적용 뒤에는 효력 시각 전 캐시 시세를
현재 평가와 체결에서 제외한다.

분할 적용은 수량에 정수 배율을 곱하고 평균원가를 같은 배율로 나눈다. 평균원가는
기존과 같이 40자리 Decimal 계산 결과를 문자열로 저장한다. 3:1처럼 순환소수가
생기면 총 원가 동일성은 이 표현 정밀도 안에서 유지되며 cash, 고점, 세션 설정은
변하지 않는다. 기존 fill과 checkpoint를 다시 쓰지 않는다.

새 metadata와 application 테이블은 기존 4열 기업행동 테이블에 덧붙인 sidecar다.
아직 분할이 적용되지 않았다면 구버전 코드는 sidecar를 무시할 수 있다. 분할이 이미
적용된 DB를 되돌릴 때는 테이블이나 행만 삭제하지 말고 적용 전 SQLite 전체 백업을
복원한다. 수량 변경과 audit 행을 분리해서 되돌리면 원장 재생이 차단된다. metadata가
없는 기존 기업행동 행도 안전하게 재생할 수 없으므로 계속 차단한다.

### 기업행동 자동 관측

별도 수집기는 고정된 16종목의 Yahoo Chart 분할·배당 metadata를 매일 관측한다.
거래소 현지 오늘을 끝으로 최근 1,095일을 요청하고, 가격 지표 준비용 추가 조회 구간에
있는 이벤트는 저장하지 않는다. 종목·Yahoo symbol·거래소·통화·시간대가 registry와
정확히 일치하고 분할 비율이 양의 정수, 배당액이 양의 유한 Decimal인 응답만 받는다.
OHLC 검증과 이 metadata 검증은 서로 분리되어 있다.

```bash
cd backend
.venv/bin/python -m jusik.research_action_collection \
  --once \
  --db "$HOME/.local/share/jusik/research-action-collection.db"
```

앱은 같은 DB를 쓰는 비동기 수집 task를 별도 HTTP client로 시작한다. 성공한 출처는
완료 시각부터 24시간 뒤, 실패한 출처는 1시간 뒤가 다음 예정 시각이다. 재시작 때
예정 시각이 지난 출처만 한 차례 처리하며 가짜 과거 실행을 만들지 않는다. 종목은
순서대로 독립 처리되어 한 종목의 HTTP·형식·DB 오류가 PAPER task나 다른 종목을
중단시키지 않는다. 전체 HTTP 작업은 30초, 본문은 2 MiB로 제한한다.

DB 옆 `.lock` 파일을 nonblocking `flock`으로 잡아 CLI와 앱의 동시 cycle을 막는다.
pending attempt는 lock을 얻은 process만 interrupted로 복구한다. SQLite lock 대기는
100 ms로 제한하고 앱 event loop 밖 thread에서 접근한다. 종료 중인 DB 작업은 끝까지
확인한 다음 cycle lock을 풀며, 완료하지 못한 attempt는 다음 cycle에 즉시 재시도한다.

성공 응답의 원문 bytes, SHA-256, HTTP 상태, 요청 URL과 실제 완료 UTC를 보존한다.
원문이 없는 timeout·전송 실패·중단은 다운로드 링크를 만들지 않는다. 2 MiB를 넘은
본문도 완전한 원문으로 표시하지 않는다. 이벤트 identity는 provider·symbol·kind·공급자
key이며, 같은 key의 값이 바뀔 때마다 append-only revision을 남긴다. A→B→A처럼 값이
되돌아와도 세 번째 revision을 보존하고, 연속해서 같은 값이면 revision 수는 늘리지
않고 최근 관측 시각만 갱신한다. `first_seen_at`은 수집 성공이 실제 완료된 UTC이며
공급자 사건 날짜로 소급하지 않는다.

성공 응답의 조회 범위 안에서 기존 이벤트가 다시 보이지 않으면
`not_seen_in_latest_response`로 표시한다. 빈 events 또는 events container가 없는 성공
응답도 같은 규칙을 적용한다. 조회 범위 밖 이벤트와 마지막 성공 자료는 실패 때문에
바뀌지 않는다. 이 표시는 취소나 삭제 확정이 아니다. 지급일, 세금, 공식 발표 시각도
Yahoo metadata만으로 알 수 없다.

`/research/actions`는 16개 출처 상태, 미검증 이벤트, 값 변경 revision과 SHA-256으로
검증된 원문 bytes 다운로드를 표시한다. 원문이 JSON이 아닌 HTTP 오류 본문일 수도
있으므로 다운로드는 `.body`와 `application/octet-stream`으로 제공한다. cursor 목록은
기본 50건, 최대 100건이다. 수집 결과는 검증
manifest에 자동 등록되지 않고 전진 PAPER 분할 적용이나 배당 현금에 연결되지 않는다.
수집 DB를 되돌릴 때는 앱을 중지한 뒤 DB, `-wal`, `-shm`, `.lock`을 함께 보존 또는
교체한다. 구버전 앱은 이 독립 DB를 읽지 않으므로 기존 forward DB와 원장은 그대로
동작한다.

공식 근거 대조는 자동 수집 revision에 운영자가 실제로 읽은 발행사 문서를 연결하는
별도 sidecar다. importer는 manifest가 지정한 exact revision과 저장된 content SHA-256,
로컬 근거 파일 SHA-256을 다시 확인한다. HTTPS 문서 URL, 발행사, 문서 안의 위치와 실제
확보 UTC를 보존하며 URL을 다시 요청하지 않는다. 로컬 파일 경로는 API에 노출하지
않는다.

```json
{
  "schema_version": 1,
  "reviews": [{
    "review_key": "nvda-split-2024-review-v1",
    "revision_id": "<64-hex>",
    "content_sha256": "<64-hex>",
    "operator_verified": true,
    "evidence": {
      "local_file": "/path/to/issuer-document.pdf",
      "sha256": "<64-hex>",
      "source_url": "https://issuer.example/document.pdf",
      "publisher": "Issuer name",
      "locator": "pages 1-2, split ratio and trading date",
      "captured_at": "2026-09-10T09:25:12Z"
    },
    "extracted_facts": {
      "numerator": 10,
      "denominator": 1,
      "adjusted_trading_date": "2024-06-10",
      "amount": null,
      "currency": null,
      "comparable_share_basis": null,
      "ex_dividend_date": null,
      "record_date": null,
      "payment_date": null,
      "legal_effective_date": "2024-06-07"
    }
  }]
}
```

```bash
cd backend
.venv/bin/python -m jusik.research_action_review \
  --db "$HOME/.local/share/jusik/research-action-collection.db" \
  --manifest "/path/to/operator-reviewed-actions.json"
```

분할은 비율을 교차 곱으로 비교하고 공급자의 수정 거래일과 근거의
`adjusted_trading_date`를 비교한다. 배당은 금액, 통화, `ex_dividend_date`와 명시적인
`comparable_share_basis=true`를 비교한다. record date, payment date, legal effective
date는 각 역할을 따로 보존하며 ex-dividend date나 수정 거래일로 바꾸어 쓰지 않는다.
필수 근거가 모두 같으면 `matched`, 일부가 문서에 없으면 `partial`, 알려진 값이 다르면
`mismatched`다. 이 상태는 importer가 입력한 신뢰 표식이 아니라 저장된 revision과
추출 사실을 비교한 결과다.

같은 `review_key`와 같은 내용의 재가져오기는 최초 시각을 바꾸지 않는다. 같은 key의
다른 내용은 manifest 전체를 거부한다. 근거 해석을 고칠 때는 새 key를 사용하며 같은
revision의 다음 review sequence로 append한다. 검토는 revision ID에만 붙으므로 공급자
값이 A→B→A로 돌아와도 과거 A 검토를 새 revision이 물려받지 않는다. `reviewed_at`과
`imported_at`은 CLI 실행의 실제 UTC이며 이를 덮어쓰는 옵션은 없다.

공식 근거 대조 테이블 두 개는 기존 수집 테이블을 수정하지 않는다. `/research/actions`
에서는 수집 freshness와 대조 결과를 분리하고 현재 미검토 revision 수를 함께 표시한다.
원문은 ID allowlist와 저장 SHA 검증 뒤 octet-stream으로 내려준다. 대조 DB 오류는 수집과
PAPER를 막지 않는다. rollback은 가져오기 전 collection DB 전체 백업을 복원하거나,
아직 외부에 참조되지 않은 경우 새 `action_reviews`, `action_review_evidence` sidecar만
제거한다. 공식 근거 대조는 verified split manifest 승격, 배당 현금, 세금, 지급 권리,
실제 주문을 수행하지 않는다.

`/research/history`는 공개용 seed와 이후 자동 journal을 함께 표시한다. 공개 문서는
SHA-256 ID allowlist를 거쳐 복사하며 DB, 원본 manifest, 절대 경로는 노출하지 않는다.
seed 재가져오기는 이미 공개한 항목의 삭제나 수정을 거부하고 journal DB는 공개
artifact 디렉터리 밖에 보존한다.

공개 이력 가져오기:

```bash
python -m jusik.research_history import \
  --seed /path/to/public-history-seed.json \
  --artifacts-dir /path/to/public-history-artifacts \
  --target ~/.local/share/jusik/research-history
```

종목별 결과와 별도로 16개 종목을 원화 1억원 단일 현금 계좌에서 함께 평가합니다. 매주 월요일 00:00 UTC까지 확정된 종가와 외부 관측만 사용해 목표 비중을 정하고, 한국과 미국 시장의 다음 실제 일봉 시가에 각각 체결합니다. 미국 종목은 별도 달러 현금 원장을 두지 않고 매 거래에서 USD/KRW를 적용하며 환전 스프레드를 비용으로 기록합니다.

고정 후보는 균등, 최근 60일 역변동성, 모멘텀 상위 4개 역변동성·양의 상관 패널티의 3가지 배분법과 외부 변수 필터 없음, 금리, 환율·VIX, 시장 스트레스의 4가지 조합으로 총 12개입니다. 상관 패널티는 두 종목의 과거 UTC 날짜별 수익률이 모두 있는 날짜만 맞춘 뒤 양의 Pearson 상관 평균을 구하고, 역변동성 점수를 `1 + 양의 상관 평균`으로 나눕니다. 종목별 20%, 총투자 60%, SOXL·TQQQ 합산 20% 상한과 종가 고점 대비 10% 손실 제한을 모든 후보에 동일하게 적용합니다.

전체 공통 거래일 앞 120개는 준비 구간, 다음 40개는 후보 선택 구간입니다. 순비용 수익률, 최대 낙폭, 회전율, 후보 ID 순으로 승자를 한 번 고정한 뒤 남은 구간에서 현금을 초기화하지 않고 연속 평가합니다. 현금 기준과 동일 비중 추세 기준을 함께 표시하며 선택한 정책을 그대로 사용한 수수료·슬리피지·환전비용 2배 결과도 제공합니다. 보유평가를 본 뒤 후보를 다시 선택하지 않습니다.

```bash
cd backend
.venv/bin/python -m jusik.research_portfolio run
.venv/bin/python -m jusik.research_portfolio status
```

완료 결과는 `~/.local/share/jusik/research-universe-reports/portfolio-runs/<run-id>`에 JSON, Markdown, CSV와 전체 고정 입력 manifest로 저장합니다. `portfolio-latest.json`은 완전히 기록된 실행만 가리킵니다. `/research/portfolio`에서 선택 과정, 연속 원화 평가액, 비용, 최신 목표·실제 배분과 허용된 산출물을 확인할 수 있습니다. 이 연구는 현재 archive를 이용한 과거 재구성이며 point-in-time 또는 미래 성과가 검증되지 않았고 자동매매에 사용할 수 없습니다.

### 사전 고정 저회전·재진입 정책 비교

주간 지시가 첫 유효 개장에 도달하면 매도, 무거래, 0수량, 자금 부족을 포함해 그 지시를 한 번만 소비합니다. 한 지시의 방향은 체결 전 평가액으로 고정하므로 같은 지시에서 매도한 뒤 다시 매수하지 않습니다. 이 체결 수정을 공통 대조군으로 삼아, 이전 검증에서 고정한 `portfolio_inverse_volatility_fx_vix_v1` 후보에 재진입, 원화 변동성 배율, 두 조건의 결합, 4주 저회전 결합을 더한 5개 정책을 비교합니다. 기존 12개 후보 검증은 수정된 공통 엔진으로 따로 계산하며, 그 선택이 달라져도 정책 비교 후보를 바꾸지 않습니다.

재진입 정책은 위험 청산이 모두 체결된 뒤 28일을 기다리고, 기존 외부 gate를 통과하면서 양의 목표 종목이 2개 이상인 월요일을 2회 연속 확인합니다. 확인 직후가 아니라 다음 정기 재배분에 진입합니다. episode 고점은 재진입 시 실제 평가액으로 다시 잡지만 최초 실행부터의 lifetime 고점과 낙폭은 초기화하지 않습니다. 따라서 10% lifetime 낙폭을 보장하는 규칙이 아닙니다.

변동성 배율은 각 월요일 00:00 UTC 전에 알려진 61개 global UTC 종가일의 수정가격을 원화로 환산해 60개 수익률의 모집단 표준편차에 `sqrt(252)`를 곱합니다. 목표 비중으로 가중한 종목별 연 변동성 합을 보수적 risk proxy로 사용하고, 10%를 넘으면 `min(1, 10% / proxy)`만큼 목표를 줄입니다. 이 값은 공분산을 반영한 포트폴리오 변동성 추정치가 아닙니다. 필요한 과거 가격이나 당시 이용 가능한 환율이 없으면 결과를 불완전으로 처리합니다.

저회전 정책은 평가 시작일 이후 첫 월요일을 기준으로 4주마다만 정기 재배분합니다. 실제 비중과 목표 비중 차이가 2%p 미만이면 그 종목의 일반 거래를 건너뜁니다. 위험 청산, 0 목표 청산, 상한 위반 축소에는 이 구간을 적용하지 않습니다. `policy-comparison.csv`, `policy-monthly.csv`, `policy-events.csv`에는 다섯 정책의 기본·비용 2배 결과, 0거래 월을 포함한 월별 거래와 일말 평가액 기준 회전율, 상태 변화를 기록합니다. 투자일은 실제로 관측된 UTC 종가일 중 종가 평가액이 현금보다 큰 날의 비율이며 달력의 빈 날을 보간하지 않습니다.

거래 빈도를 줄이는 규칙은 거래비용과 행동 편향을 줄일 가능성이 있지만 수익 개선을 보장하지 않습니다. 거래비용과 과도한 매매에 관한 [FINRA의 온라인 거래 안내](https://www.finra.org/investors/investing/investment-products/stocks/day-trading), 변동성 관리의 장기 증거를 다룬 [NBER Working Paper 22208](https://www.nber.org/papers/w22208), 변동성 관리 성과에 다른 해석을 제시한 [Xu의 반대 증거](https://www.lehigh.edu/~xuy219/research/COWY.pdf)를 함께 참고합니다. 이번 표는 이미 본 과거 보유평가 구간을 재사용한 후향 비교이고 장중 체결을 검증하지 않았으며, 결과로 정책을 선택하거나 실거래에 자동 승격하지 않습니다.

평가 요청은 거래소 현지 날짜 기준 전일까지의 최근 3년입니다. 지표 준비용으로 약 180일을 추가 수집하고, 실제 확보한 61번째 일봉과 요청 시작일 중 늦은 날을 평가 시작일로 사용합니다. 완료되지 않은 현지 당일 봉과 상장 기준일 전 봉은 제외합니다. ARM은 2023년 9월 14일, GEV는 정규 거래가 시작된 2024년 4월 2일부터 사용합니다. 상장 이력이 짧은 `0173Y0`, `0190C0`도 목록에서 빼지 않으며 준비 60개와 평가 240개를 충족하지 못한 이유를 상태와 보고서에 남깁니다.

미국 가격·거래량과 전체 종목의 symbol·통화·거래소·시간대·주식분할 metadata는 인증 없는 Yahoo chart에서 받습니다. Yahoo 국내 OHLC에는 유효하지 않거나 누락된 과거 행이 확인되어, 국내 6종목 가격과 거래량은 기존 KIS 모의투자 일봉의 검증된 원주가를 사용하고 Yahoo는 기업행동 metadata 확인에만 사용합니다. 종목별 수집이 실패하면 다른 종목은 계속 처리하며 이전 성공 스냅샷은 삭제하지 않고 `stale`로 표시합니다. 값을 임의 보간하거나 고가·저가 범위를 고치지 않습니다. Yahoo의 과거 데이터 한계는 [Yahoo 도움말](https://help.yahoo.com/kb/SLN28256.html)을 참고합니다.

Yahoo OHLC는 과거 주식분할이 반영된 가격입니다. 미국 종목은 각 일봉 이후 발생한 분할 비율을 곱해 당시 원주가 OHLC를 복원하고, 공급자 OHLC 자체를 신호·ML 라벨용 분할 수정가격으로 보존합니다. `adjclose`의 배당 조정값은 사용하지 않습니다. NVDA의 2024년 6월 10일 10:1, TQQQ의 2025년 11월 20일 2:1 분할처럼 보유 중 발생한 기업행동은 해당 거래일 시가 전에 수량에 반영합니다. 역분할로 생긴 소수 주식은 그날 원주가 시가로 현금 정산했다고 가정해 별도 기록합니다. 이 정산가격은 실제 브로커 조건이 아닙니다. 공급자 volume은 그대로 사용하며 과거 원거래량으로 재구성하지 않습니다.

모든 종목은 기존 89개와 사전 고정한 외부 변수 연구 후보 4개, 120/40/40일 walk-forward, 40일 step, 종목당 20%·전체 60% 진입 예산과 10% 종가 고점 대비 낙폭 정책을 동일하게 사용합니다. 초기자금은 KRW 종목 1억원, USD 종목 10만 달러입니다. 신규 외부 연구의 고정 비용 가정은 매수·매도 수수료 0.1%, 슬리피지 0.1%, 매도세 0%이며 실제 증권사 요율이나 개인 세금을 뜻하지 않습니다. 배당·ETF 분배금·원천징수·환전·FX·총수익률은 포함하지 않으므로 결과는 세전 가격 손익 연구입니다.

### 시점 기준 외부 변수 후보

외부 변수 연구의 첫 후보는 기존 `trend_20_v1` 신호를 그대로 실행하는 filter 없는 대조군입니다. 나머지 세 후보도 같은 20일 추세 신호가 참일 때만 아래 조건을 추가로 확인합니다. 파라미터는 OOS를 보기 전에 고정했으며 이 실행에서 다시 조정하지 않습니다.

- 금리 조건: 미국 10년-2년 국채금리 차가 -1%p 이상이고 10년 금리의 20개 관측값 변화가 +0.50%p 이하
- 환율·변동성 조건: USD/KRW의 20개 관측값 수익률이 +5% 이하이고 VIX가 30 이하
- stress 조건: USO와 GLD의 20개 관측값 수익률이 각각 +15%, +10% 이하이고 HYG는 -3% 이상

각 신호일의 거래소 종가 시각을 기준으로 그때 공개됐다고 가정한 revision만 사용합니다. 미국 종가와 국채 자료는 보수적으로 다음 UTC 날짜 이후, Yahoo 일봉은 session timestamp가 공개시각을 뜻하지 않으므로 이틀 뒤 UTC 날짜 이후 사용할 수 있다고 가정합니다. 초기 3년 값은 현재 archive를 과거로 재구성한 것으로, 실제 당시에 알려진 원시점 vintage임을 입증하지 못합니다. 따라서 모든 외부 변수 실행과 종목별 CSV는 `evidence_class=reconstructed_historical_exploration`, `point_in_time_verified=false`, `prospective_validation_eligible=false`로 고정합니다. `research_comparison_met`가 참이어도 이는 재구성 과거자료 안의 비교 조건만 뜻하며 전진 검증 통과나 paper·실전 승격 근거가 아닙니다. 이후 발견된 과거 누락값과 수정값은 수집 시각 전으로 소급하지 않고 append-only revision으로 남깁니다. 20개 이전 유효 관측값과 현재값이 필요하고 최신값이 7일보다 오래되면 누락으로 처리합니다. 검증 구간에 필요한 값이 하나라도 없으면 해당 macro 후보만 명시적으로 부적격 처리하며 다른 89개 후보는 계속 평가합니다. OOS에서 누락되면 현금 상태를 선택하고 누락 날짜 수를 기록하며 fold 합격으로 표시하지 않습니다. 값을 0으로 채우거나 무기한 이전값을 사용하지 않습니다.

[미국 재무부 수익률 XML](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve), [CBOE VIX CSV](https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv), Yahoo chart의 USD/KRW·USO·GLD·HYG를 신호 입력으로 수집합니다. SPY와 SMH는 이후 진단용으로만 보관합니다. [GPR 일별 자료](https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls)와 [New York Fed EFFR archive](https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json)는 원문과 수집 상태만 저장하고 현재 후보에는 사용하지 않습니다. GPR 과거값은 당시 알려진 값으로 간주하지 않으며 최초 수집 이후의 미래 연구에서만 revision을 평가할 수 있습니다. FRED의 일반 조회 날짜는 vintage 증거로 사용하지 않습니다.

외부 자료 원문, 성공·실패 시각, 범위, age와 오류는 출처별로 분리해 보관합니다. 한 출처 실패가 다른 출처나 주가 후보를 중단시키지 않으며 이전 성공 자료는 삭제하지 않고 stale로 표시합니다. 보고서의 `external.md`는 수집 출처, 실제 신호 사용 여부와 제외 항목을 따로 보여 줍니다. 이 filter 결과도 반복된 과거 자료 연구이며 거시 변수 효과나 미래 성과를 입증하지 않고 자동매매 후보를 승격하지 않습니다.

보고서는 종목별 CSV와 한국어 Markdown으로 원자적으로 교체합니다. 요청·실제·평가 범위, 준비/평가 일봉 수, 통화, freshness, fold·후보 진행 수, 통과 fold, 평균·최악 OOS 수익률과 최대 낙폭, 비용 조건과 오류를 표시합니다. 통화가 다른 성과를 합친 순위는 만들지 않습니다. 반복되는 과거 OOS는 새 미래 holdout이 아니고, 16개 고정 종목은 생존편향과 전체 시장 대표성 문제를 해소하지 않습니다. 공식 거래소 달력, 배당, 상장폐지 전체 이력, 장중 호가가 없으므로 자동 paper 선택이나 실전 주문 근거로 사용하지 않습니다.

한국 ETF 상품 정보와 상장 기준은 [KODEX 미국AI전력핵심인프라](https://www.samsungfund.com/etf/product/view.do?id=2ETFN6), [KODEX AI전력핵심설비 관련 자료](https://www.samsungfund.com/upload/kodex/newsroom/20260427141121713.pdf), [KODEX 미국AI광통신네트워크 안내](https://m.samsungfund.com/etf/insight/newsroom/view.do?seq=74574), [RISE 상품 정보](https://www.riseetf.co.kr/prod/finderDetail/44K4)를 기준으로 고정했습니다. GEV의 정규 거래 시작일은 [GE Vernova 분사·NYSE 거래 안내](https://www.gevernova.com/news/press-releases/ge-vernova-completes-spin-off-begins-trading-new-york-stock-exchange)를 따릅니다.

## 비교 규칙

- 기준 전략 `trend_20_v1`: 수정 종가가 20거래일 단순이동평균보다 높으면 보유합니다.
- 후보 전략 `trend_20_60_v1`: 위 조건과 함께 20거래일 평균이 60거래일 평균보다 높으면 보유합니다.
- 신호는 장 마감 뒤 계산하고 종목별 다음 거래 가능 일봉의 원주가 시가로 체결합니다.
- 매도부터 처리한 뒤 종목 코드 순서로 매수합니다. 하나의 공통 현금 잔고를 사용하고, 종목별 한도는 당시 평가액을 전체 종목 수로 나눈 값입니다.
- 정수 수량, 수수료, 매도세, 슬리피지를 `Decimal`로 계산합니다. 거래량 0인 일봉에는 체결을 만들지 않습니다.
- 마지막 보유분은 강제 매도하지 않고 마지막 확인 종가로 평가합니다.
- 각 연구 실행의 전체 비교 기간 앞 70%는 학습 구간, 뒤 30%는 해당 실행의 시간순 평가 구간으로 나눕니다. 평가 구간은 원래 초기자금으로 새로 시작하며 앞 구간의 일봉은 지표 준비에만 사용합니다. 정기 실행 사이에는 기간이 겹칠 수 있으므로 내장 전략의 반복 결과를 새로운 미사용 표본으로 해석하지 않습니다.
- 내장된 20일, 20/60일, 20/60일+거래량 전략은 같은 평가 구간에서 실행합니다. 기준 이상의 수익률과 기준 이하의 최대 낙폭을 모두 충족해야 합격합니다.
- 제한형 AI 후보는 제안에 사용한 평가 종료일과 실제 제안 생성일 중 늦은 날짜를 기준일로 고정합니다. 기준일 뒤에 새로 생긴 거래일이 20개 이상인 첫 후속 구간만 평가합니다. 후보 정의, 출처 실행·입력·구현 지문, 평가 실행·입력·구현 지문과 기간을 저장하며 후속 평가 전에는 paper 전략으로 선택할 수 없습니다.
- 추천은 평가 결과로 갱신되지만 paper 운영 전략은 사용자가 별도로 선택해야 바뀝니다.

입력, 고정 계산 사양, 현재 로드된 엔진·전략 소스에는 각각 SHA-256을 기록합니다. 저장된 구현 지문이나 계산 사양이 현재 프로세스와 다르면 같은 버전 재생 요청을 거부합니다. 준비 구간 60개 일봉이 없거나 원주가와 수정주가의 날짜가 다르거나 수정 비율이 기간 중 바뀌면 결과를 `insufficient`로 처리합니다. 종목별 거래일 차이는 만들거나 지우지 않고 데이터 범위에 기록합니다.

공식 KRX 거래일 달력은 아직 입력 스냅샷에 포함하지 않습니다. 따라서 모든 종목에서 동시에 누락된 일봉은 휴장일과 구분할 수 없습니다. 결과와 UI는 이 상태를 `common_sessions_unverified` 경고로 표시하며, 기대 거래일 대비 누락 수는 `확인 불가`로 둡니다. 숫자로 표시하는 누락 수는 다른 요청 종목의 날짜 합집합과 비교한 상대 차이입니다.

## 시장 이벤트

서킷브레이커와 사이드카는 출처 URL, 발생·인지·재개 시각을 포함한 JSON 배열로 선택 입력합니다. 입력하지 않으면 이벤트가 없었다고 판정하지 않고 범위를 `확인 불가`로 표시합니다. 제공된 이벤트도 전체 이력이 아니라 사용자 제공분으로 표시합니다.

시장 이벤트는 종목의 KOSPI·KOSDAQ 소속과 같은 경우에만 적용합니다. 소속을 확인할 수 없는 종목과 이벤트를 함께 요청하면 검증 불충분으로 끝냅니다. 사이드카는 전체 주식 거래중단으로 처리하지 않습니다. 시가 전에 알려진 이벤트가 있으면 후보 전략의 다음 신규 진입만 한 번 미룹니다. 서킷브레이커 중단 구간이 가정한 시가 체결과 겹치면 일봉만으로 체결을 복원하지 않고 검증 불충분으로 처리합니다. 오후에 발생한 이벤트가 같은 날 아침 체결을 소급해서 막지는 않습니다.

이 정책은 KRX 제도 자체를 재현한 규칙이 아니라 일봉 연구용 보수적 가정입니다. 정확한 장중 발동 이력과 호가 데이터 없이는 시장조치 전후 체결을 완전히 검증할 수 없습니다.

## 실시간 감시와 승인

`/research`에서 KIS `H0STCNT0` 국내 체결가 구독을 켤 수 있습니다. 연결 승인, 종목별 구독 확인, heartbeat, 다중 레코드와 46개 필드를 검증합니다. 연결 끊김, 30초 무수신, 오래되거나 미래인 시세에서는 승인을 체결하지 않습니다. 실시간 tick은 마지막 확정 일봉 신호의 가격 적합성만 확인하며 일봉 전략을 장중 전략으로 바꾸지 않습니다.

확정 일봉과 선택한 paper 전략으로 매수·매도 제안을 만들고 종목, 수량, 가격 한도, 만료, 전략 버전, 출처 실행과 신호 입력 지문, 이유를 저장합니다. 신호 입력 지문은 전략 정의와 해당 종목의 계산 구간에 실제 사용한 확정 수정종가·거래량으로 만듭니다. 수집 시각과 연구 실행 ID는 제외합니다. 같은 신호를 거절하거나 만료하면 같은 확정 일봉과 신호 입력에서는 다시 제안하지 않습니다. 새 확정 일봉에서 신호가 해제되거나 실제 신호 입력이 바뀌면 이전 대기 제안을 만료합니다. 사용자가 승인할 때 최신 확정 일봉 신호, 시세, 활성 전략, 현금·포지션, 중복·만료를 다시 확인합니다. 매수와 매도 모두 승인해야 하며 거절할 수 있습니다. 실제 주문 모드와 증권사 주문 경로는 없습니다.

OpenAI 검토는 키·모델·양수 일일 token 예산을 모두 명시한 경우에만 정기 연구 완료 뒤 실행합니다. 요청 본문과 JSON Schema의 UTF-8 byte 수에 여유분을 더해 입력 token을 보수적으로 예약하고 남은 예산 안에서 출력 상한을 줄입니다. 응답이 불확실한 실패도 예약량을 당일 사용량으로 유지합니다. 이 수치는 과금 명세가 아니라 호출 전 상한을 지키기 위한 보수적 예약량입니다. Structured Outputs를 검증해 제한된 이동평균·거래량 후보만 저장합니다. 계산, 합격 판정, 실행 코드 생성과 주문은 LLM에 맡기지 않습니다. 호출 실패는 결정론적 백테스트 결과를 실패로 바꾸지 않습니다. 초기 과거 뉴스·공시 backfill과 OpenAI Batch API lifecycle은 아직 지원하지 않습니다.

## 현재 한계

현재 버전은 국내주식 일봉, 체결가 stream, 원주가 시가 체결과 고정 비용 가정만 지원합니다. 기업 재무·업종 상대가치, 공시·뉴스 사건 이력, 배당·총수익률, 호가잔량·부분 체결, 상장폐지 전체 universe는 아직 포함하지 않습니다. 공식 KRX 달력도 없어 모든 종목에 함께 누락된 일봉을 판별하지 못합니다. 이 상태의 성과는 실전 주문 근거가 아니며 실제 전략으로 자동 승격하지 않습니다.

## 검증된 배당 기여분 overlay

고정 포트폴리오 실행 `c94690f0ee13f01b1810ac0368e84fdcaeb1c1bbe7f396985d04dd3634b5ead0`의 거래와 평가액을 바꾸지 않고, 현재 revision에 대한 최신 공식 근거 대조가 `matched`인 배당만 세전 기여분으로 더해 볼 수 있습니다.

```bash
cd backend
.venv/bin/python -m jusik.research_dividend_overlay \
  --source-run-id c94690f0ee13f01b1810ac0368e84fdcaeb1c1bbe7f396985d04dd3634b5ead0 \
  --review-db ~/.local/share/jusik/research-action-collection.sqlite3 \
  --source-report-dir ~/.local/share/jusik/research-universe-reports \
  --report-dir ~/.local/share/jusik/research-dividend-reports
```

결과는 `dividend-overlay-runs/<run-id>/`에 원본·검토 snapshot·캘린더·계산 코드 해시와 함께 저장됩니다. 같은 입력은 기존 산출물의 해시를 검증해 재사용하며 기존 `portfolio-latest` 포인터는 변경하지 않습니다. 웹의 `/research/portfolio/dividends`에서 계산 결과와 원장, 환율 근거, coverage를 확인할 수 있습니다.

배당락일 실제 개장 직전 수량으로 권리를 계산하고 지급일 다음 현지 자정을 receivable에서 native cash로 옮기는 표시 경계로 사용합니다. 세금, 브로커 통화 최소 단위 반올림, 재투자, 환전, 이자와 환전 비용은 추정하지 않습니다. USD 잔액은 해당 평가 시각까지 공개됐고 UTC 관측일이 7일 이내인 고정 USD/KRW revision으로만 원화 환산합니다. 계산 가능한 한 건은 전체 배당 coverage나 완전한 총수익률을 뜻하지 않으며, 이 후향 결과는 자동 원장 반영·미래 검증·주문에 사용되지 않습니다.

롤백은 연구 앱에서 이 조회 화면과 API를 제거하고 `research-dividend-reports` 디렉터리를 보관하거나 분리하면 됩니다. 수집 DB와 공식 근거 검토 테이블은 읽기 전용으로 사용하며, 기존 포트폴리오 실행과 PAPER 원장은 수정하지 않습니다.

## 실시간 신호 증거와 포트폴리오 robustness

고정 미래 PAPER 평가는 현재 활성 session과 source run
`fa0907ecfe86b19836881e5a78a874925fc611978ffe31064eacc82a0a46f687`를
2026-09-14 00:00 UTC 전에 다음 명령으로 한 번 등록합니다. 시작·종료 시각과 등록
시각을 바꾸는 CLI 옵션은 없습니다.

```bash
cd backend
.venv/bin/python -m jusik.research_prospective_registration \
  --forward-db ~/.local/share/jusik/research-forward.db \
  --source-report-dir ~/.local/share/jusik/research-universe-reports \
  --output-dir ~/.local/share/jusik/research-prospective
```

등록 파일은 `research-prospective/<session-id>.json` 하나입니다. 활성 session을 읽기
전용으로 조회하고 원장을 만들거나 초기화하지 않습니다. session config와 기존 policy
hash, source manifest·result 원문 SHA-256과 공통 input hash, 평가에 사용하는 명시적
코드·달력 파일 SHA-256, 2026-09-14 00:00 UTC부터 2026-11-09 00:00 UTC까지의
56일 기간과 평가 정의를 canonical contract SHA-256으로 묶습니다. 이 기간은 고정
정책의 28일 주기 두 번을 관측하는 짧은 운영 창이며 평가 통과를 뜻하지 않습니다.
같은 identity의 동시·반복 등록은 최초 파일 byte, mtime과 실제 `registered_at`을
유지하며 다른 identity는 기존 파일을 덮어쓰지 않고 거부합니다.

평가 정의는 비용 차감 원화 NAV 수익률, NAV 최대 낙폭, 총 거래대금/시작 NAV
회전율, 거래·환전 비용과 fill에 실제 사용한 execution quote 근거입니다. 현금
benchmark는 0%입니다. 시작 NAV는 초기 현금 1억원이나 현재 현금으로 대체하지 않으며
시작·끝 평가 근거가 없으면 향후 계산을 불완전으로 처리합니다. 사용자의 허용 손실
20%와 현재 정책의 10% 낙폭 방어 기준은 서로 다른 값으로 보존합니다. 이번 등록은
실적 계산이나 합격 판정을 만들지 않고 PAPER 전용이며 자동 승격 대상이 아닙니다.

`/api/research/validation/prospective`와 `/research/validation`은 `not_registered`,
`planned`, `observing`, `window_elapsed`, `identity_mismatch`, `invalid_contract`를
표시합니다. 앱 시작 때 잡은 코드 지문과 조회 시점 디스크 지문을 계약과 각각
비교하고, session·source·config·코드·달력 불일치는 기간 상태보다 먼저 표시합니다.
큰 source 파일 해시와 JSON 검증은 요청 event loop 밖에서 수행합니다. 파일 읽기나
내용 검증 실패는 경로·내부 예외를 노출하지 않고 fail closed 상태로 반환합니다.
`window_elapsed`는 평가 통과를 뜻하지 않습니다.

`/api/research/validation/prospective/readiness`는 등록 상태와 분리해 평가 경계와
체결 근거의 준비 상태만 읽기 전용으로 점검합니다. 시작·종료 시각과 UTC로 정확히
같은 checkpoint가 없으면 `missing`, 아직 경계 전이면 `not_due`입니다. exact
checkpoint가 있어도 현재 행에는 입력 provenance가 없으므로 NAV 값을 반환하거나
준비 완료로 승격하지 않고 `unverified_candidate`로 표시합니다. 경계 수집기는 아직
구현되지 않았습니다. 이전 종가, 현재 현금, 초기 현금은 경계 NAV 대신 사용하지
않습니다.

계약 구간 `[start, end)`은 fill의 `received_at`을 UTC로 정규화해 포함 여부를
정합니다. 해당 PAPER fill은 실제 체결 sidecar 원문 SHA-256, quote 모델, 종목과
시장·수신 시각 연결을 최대 5,000건까지 검사합니다. 전체 fill 수는 별도로
세며 검사 한도를 넘으면 잘림과 미검사 건수를 표시하고 불완전으로 처리합니다. 0건은
`unobserved`이며 통과가 아닙니다. sidecar의 연결 무결성은 가격·통화·슬리피지 또는
재무 계산의 정확성을 증명하지 않습니다. 시간 문자열은 offset 표기를 포함해 aware
datetime으로 해석한 뒤 UTC로 비교하며, 손상된 시각·DB·등록 identity는 행을 버리지
않고 readiness 조회 전체를 사용할 수 없는 상태로 닫습니다.

연구 앱의 별도 raw boundary monitor는 5초 monotonic 간격으로 등록된 시작·종료
경계가 도래했는지만 확인합니다. `create_research_app` factory에서는 기본 비활성이고
실제 앱 entrypoint에서만 활성화됩니다. 경계가 오면 nonblocking 경계별 file lock을
먼저 잡은 뒤 등록 identity와 활성 PAPER session을 검증하고, SQLite `mode=ro`의 한
read transaction에서 allowlist 원장 행을 관측합니다. 시작은 2026-09-14 00:00 UTC,
종료는 2026-11-09 00:00 UTC이며 미래 시계를 주입하는 운영 옵션은 없습니다.

결과는
`~/.local/share/jusik/research-prospective-captures/<session-id>/<start|end>.json`에
canonical JSON과 자체 SHA-256으로 한 번만 게시합니다. 임시 파일과 file·directory
fsync 뒤 no-overwrite link로 공개하며, 재시작과 동시 실행은 기존 파일을 다시
검증해 byte와 mtime을 유지합니다. 손상된 기존 파일은 덮어쓰지 않습니다. 읽기 중
취소되면 진행 중인 DB thread와 게시 정리가 끝날 때까지 lock을 유지합니다.
수집 뒤 collector가 바뀌어도 과거 파일은 파일 안의 startup·capture hash 일치와
계약·session·경계·자체 SHA를 검증해 계속 보존하고 내려받을 수 있습니다. 실행 중인
collector와 현재 디스크 hash가 달라지면 새 경계 수집만 거부합니다.

snapshot은 typed allowlist인 활성 session, position, decision, fill, execution quote,
decision이 참조한 input version, 검증된 분할 metadata·application, checkpoint와
종목별 읽기 시점 최신 시세만 포함합니다. 최신 시세는 경계 당시 사용 가능했던
시세가 아니라 `latest_at_read_time` 관측이며 market·received 시각을 함께 보존합니다.
일반 행 256 KiB, 표별 5,000행, input 100개·개별 16 MiB, 누적 원문 56 MiB와 최종
artifact 64 MiB 상한을 적용합니다. 큰 payload는 SQL byte 길이를 먼저 확인하고,
누락 reference·손상 payload·생략 건수와 제한된 ID 목록을 issue로 남깁니다. issue가
있어도 최초 `captured_with_issues` 파일을 고정하고 더 좋은 상태를 만들기 위해 다시
수집하지 않습니다.

`/api/research/validation/prospective/boundary-captures`는 monitor 실행 여부, 실제 마지막
poll 시각, `scheduled`, `collecting`, `captured_raw`, `captured_with_issues`, `error`와
startup·현재 collector source hash를 표시합니다. start/end 이외의 경로는 허용하지
않으며 download는 현재 계약과 canonical artifact를 다시 검증한 동일 bytes와
`X-Content-SHA256`을 반환합니다. raw snapshot은 경계 시점 상태의 as-of 재구성,
승인 NAV, 평가 입력 완성 또는 숫자 성과 계산이 아닙니다. 외부 DB, 시세 정책,
PAPER 원장과 등록 계약은 수정하지 않습니다.

`/api/research/validation/prospective/boundary-evidence/<start|end>`는 검증된 원시
artifact만 사용해 내부 참조와 부분 일관성을 검사합니다. 경계 전 `not_due`, 경계가
왔지만 파일이 없으면 `missing`, 손상되거나 읽을 수 없으면 `unavailable`, 검사한
경우 `inspected`로 구분합니다. 현재 DB에서 빠진 값을 보완하지 않습니다. 같은
artifact에는 같은 검사 결과를 만들며 체결·보유 종목 상세는 각각 50건까지만
표시하고 전체·생략 건수를 별도로 보존합니다.

체결 검사는 session, decision, input version, 실제 사용 시세 참조와 종목·시장·수신
시각을 비교합니다. 체결가는 producer의 Decimal precision 40, 거래대금은 저장
경로의 Decimal precision 28과 `ROUND_HALF_EVEN`을 분리해 허용 오차 없이
재현합니다. 재현할 수 없는 숫자는 실패로 추정하지 않고 `unknown`입니다. 비용은
유한한 비음수 값인지까지만 확인하며 전체 비용 산식 검증을 주장하지 않습니다.
경계 뒤 체결은 원시 관측에 포함될 수 있는 진단 정보이며 운영 장애로 판정하지
않습니다.

보유 종목의 최신 시세와 입력 안의 과거 가격·USD/KRW는 후보 존재와 이용 가능
시각만 진단합니다. `latest_at_read_time`은 경계 가격이 아니며 어떤 가격·환율을
선택할지, 체결 환율의 외부 원문, 원장 commit 시각, 기업행동 완결성과 NAV는
증명하지 않습니다. 내용 SHA는 변경 검출값이지 출처 진위 증명이 아닙니다. 모든
결과의 `accepted_nav`와 `evaluation_inputs_complete`는 false이고 수익률을 계산하지
않습니다.

서버 UTC는 운영 기록이며 암호학적 타임스탬프가 아닙니다. 등록 뒤 같은 byte가 계속
유지됐거나 과거 코드가 변경 뒤 복원되지 않았음을 독립적으로 증명하지 못합니다.
미래 decision의 시점별 입력은 기존 PAPER 원장의 input version으로 별도 고정됩니다.
등록 화면과 read-only API를 제거해도 계약 파일과 PAPER 원장은 유지되며, rollback 시
계약 파일을 별도 보관할 수 있습니다.

연구 앱은 별도 진단 task에서 시작 직후와 이후 monotonic 60초 간격으로
`LC_ALL=C SYSTEMD_COLORS=0 timedatectl timesync-status --no-pager`를 실행합니다.
명령 전체 제한은 3초이고 stdout·stderr 합계는 64 KiB까지만 읽습니다. timeout,
명령 부재, 비정상 종료, 크기 초과, 알 수 없는 단위나 누락 값은 원문·stderr·환경을
노출하지 않는 제한 오류 코드로 표시합니다. 취소나 제한 초과 시 child process를
종료하고 회수한 뒤 앱이 종료됩니다.

offset은 부호를 유지한 Decimal millisecond로 변환하며 `ns`, `us`, `µs`, `ms`,
`s`를 지원합니다. delay, jitter와 packet count는 명령이 제공할 때만 표시하고
동기화 여부를 직접 측정하지 못하면 `null`입니다. 각 완료 probe는 packet count가
같아도 고유 sample ID로 `forward_events`의 `clock_sample`에 저장됩니다. 화면의
`sampled_at`은 명령을 읽어 마친 UTC 시각이고 실제 NTP packet 측정 시각은 아닙니다.
probe나 저장 실패는 clock 상태에만 남으며 5초 PAPER 판단 worker 실패, 시세 신선도,
미래 시각 허용치, 정책과 주문 상태를 바꾸지 않습니다. 과거 표본은 기존 events export로
확인하며 별도 공개 이력 spam은 만들지 않습니다.

`/research/validation`은 서로 다른 두 검증을 나눠 표시합니다. 실시간 신호 증거는 최근 7일 안의 거래소 현지 날짜 한 날에 대해 고정 거래소 달력의 완료된 정규장 분만 분모로 사용합니다. session 활성화 중간 분과 현재 진행 중인 분은 제외하고, 같은 종목·분의 저장 표본은 coverage에서 한 번만 셉니다. 미관측 분과 gap은 저장된 분 표본의 차이이며 전체 tick 유실이나 시세 가용성 SLA를 뜻하지 않습니다. `received_at - market_at` 지연, 15초 초과, 2초를 넘는 미래 시각을 별도로 표시합니다. 현재 ACK·protocol counter·reconnect는 현재 프로세스 연결 epoch이고 durable feed 상태 이벤트와 구분합니다.

지연은 전체와 16개 종목별로 같은 정규장 저장 행을 집계합니다. 정규장 밖 행은 지연 통계와 이상 표본에서 제외하고, 같은 분이라도 저장 이유가 다른 행은 합치지 않습니다. 15초를 초과하거나 2초보다 앞선 표본은 원래 관측 ID, 저장 이유, UTC 시장·수신 시각과 microsecond를 보존한 정확한 millisecond 차이를 보여 줍니다. 상세 목록은 시장 시각 내림차순, 수신 시각 내림차순, 종목·관측 ID 오름차순의 최대 50건이며 전체 건수와 잘림 여부를 별도로 표시합니다. 이 진단만으로 한국 시장의 분 공백을 장애나 tick 유실로 단정하거나 현재 feed 상태를 과거 날짜의 원인으로 추정하지 않습니다.

새 PAPER fill은 기존 현금·포지션·fill 트랜잭션 안에서 실제 체결 계산에 사용한 `ResearchQuote` JSON과 SHA-256을 `forward_execution_quotes` sidecar에 함께 저장합니다. 기존 분 표본과 `fill.quote_id`는 유지합니다. 과거 fill은 소급 생성하지 않아 `legacy_sample_only`, `missing`, `mismatch`로 구분될 수 있습니다. sidecar를 해석하지 못하는 이전 코드는 기존 fill과 원장을 그대로 읽을 수 있습니다.

고정 포트폴리오 실행의 rolling robustness는 다음 명령으로 생성합니다.

```bash
cd backend
.venv/bin/python -m jusik.research_portfolio_robustness \
  --source-run-id c94690f0ee13f01b1810ac0368e84fdcaeb1c1bbe7f396985d04dd3634b5ead0 \
  --source-report-dir ~/.local/share/jusik/research-universe-reports \
  --report-dir ~/.local/share/jusik/research-validation-reports
```

최초 120 union dates를 준비 구간으로 두고 후보 선택 80일과 그 뒤 OOS 80일을 80일씩 전진합니다. 완전한 7개 fold만 사용하고 남은 14일 tail은 표시만 합니다. fold마다 12개 후보를 OOS 전에 선택하고, 선택 후보 1배·비용 2배, equal-none, 고정 inverse-volatility/fx-vix 1배·2배, signal window 15/25와 volatility window 45/75의 한 변수 민감도를 계산합니다. 모든 실행은 `low_turnover_combined`, 현금 1억원, 종목 20%, 전체 60%, 레버리지 ETF 20%, 낙폭 10%, 4주 주기를 유지합니다.

각 fold는 현금에서 독립 시작하므로 fold 수익률을 복리 연결하거나 연속 실전 NAV로 해석하지 않습니다. 과거 자료를 반복 사용한 후향 robustness이며 새로운 깨끗한 holdout, 미래 검증, 자동 정책 승격 또는 주문 근거가 아닙니다. 결과는 `~/.local/share/jusik/research-validation-reports/portfolio-robustness-runs/<run-id>/`에 원본 hash, 고정 specification, 사용 코드 hash와 함께 저장됩니다. 기존 포트폴리오 run과 `portfolio-latest.json`은 수정하지 않습니다. 롤백은 새 조회 API/UI와 sidecar writer를 제거해도 기존 테이블을 보존하는 방식이며, 새 robustness 디렉터리는 별도로 보관하거나 분리할 수 있습니다.

## USD/KRW 출처 연결 조회 v2

`research_fx_provenance.resolve_fx_provenance`는 외부 자료 SQLite를 읽기 전용 한
transaction으로 조회해 특정 UTC cutoff에서 선택 가능한 USD/KRW 관측과 보존 원문을
연결합니다. `observed_on`은 cutoff의 UTC 날짜 이하여야 하고 `available_at`과 원문
`captured_at`도 cutoff 이하여야 합니다. 관측일 내림차순, 공개시각 내림차순,
revision 오름차순으로 고른 최신값이 7일보다 오래됐거나 값·연결 원문·SHA가 유효하지
않으면 이전값으로 조용히 대체하지 않고 `unavailable`로 닫습니다. KRW는 외부 출처를
꾸미지 않고 1의 `identity_conversion`으로 반환합니다.

결과의 원문 ID는 `SHA256(source + NUL + body)`, 별도 본문 SHA와 보존 시각을
포함하지만 본문 자체나 로컬 경로는 노출하지 않습니다. 원문 hash는 저장된 bytes의
연결과 변경 여부만 확인하며 그 안의 환율 값, 출처의 진위 또는 역사적 시점성을
증명하지 않습니다. `read_started_at`과 `read_finished_at`은 실제 읽기 구간이고 원장
commit 시각이 아닙니다. 이 조회는 현재 체결이나 NAV에 연결되지 않았으므로
`linked_to_execution`, `accepted_nav`, `historical_point_in_time_proven`은 항상
false입니다.

다음 개발 우선순위는 체결에서 실제 선택한 환율과 시세를 같은 protocol의 receipt
journal에 원자적으로 남기고 commit 시각 대신 관측 구간 증거를 보존하는 것입니다.
그 뒤 경계 NAV의 가격 선택 정책, 거래소 달력과 기업행동 완결성을 검증해야 합니다.
포트폴리오 위험·비용·regime 실험은 이 측정 기반이 신뢰할 수 있게 된 뒤 진행합니다.

## 격리된 receipt journal 실험

`research_receipt_journal.ReceiptJournal`은 호출자가 명시한 새 SQLite 경로에만 시세와
검증된 FX 출처 bundle을 하나의 canonical payload로 기록하는 격리 실험입니다. 기본
경로나 daemon, API, PAPER 연결은 없습니다. DB는 전용 application ID, schema version과
정확한 두 table 구조를 먼저 확인하며, marker가 없거나 다른 구조인 기존 파일은 빈
파일이어도 수정하지 않습니다. payload는 256 KiB 이하이고 `scope`는
`isolated_experiment`, `production_ledger_linked`와 `accepted_nav`는 항상 false입니다.
합성 테스트에서 `ResearchQuote`의 source enum을 사용해도 실제 KIS 수신을 뜻하지
않으며 실험 보고서가 입력 성격을 별도로 밝혀야 합니다.

첫 transaction은 idempotency key, payload와 SHA-256, 저장 순서 sequence, process clock
ID, commit 호출 전에 읽은 UTC와 monotonic 값을 append합니다. 이 UTC는 실제 commit
시각이 아닙니다. commit 뒤 새 읽기 전용 연결에서 같은 entry와 hash가 보이는지 확인한
후 별도 transaction으로 visibility receipt를 남깁니다. receipt 시각은 그때 읽을 수
있었다는 뜻이며 최초 가시성이나 정확한 commit 순간을 증명하지 않습니다. monotonic
간격은 같은 process clock ID 안에서만 계산하고, UTC 역행은 숨기지 않고 표시합니다.

첫 commit 전 중단은 entry를 남기지 않습니다. entry commit 뒤 receipt 전 중단은
entry만 남기며, 재시작은 현재 시각의 `recovery_visibility`를 추가하고 과거 commit
시각을 추정하지 않습니다. receipt commit 뒤 응답이 사라진 재시도는 원래 entry와
receipt를 그대로 재사용합니다. 같은 key의 다른 payload, 저장 hash 훼손, monotonic
역행은 거부하며 receipt 실패 결과는 entry가 이미 commit됐는지 구분합니다. update와
delete로 과거 기록을 정상화하지 않습니다.

이 실험 journal은 운영 원장의 증거가 아닙니다. 실제 적용에는 원장 변화와 정확히
선택한 시세·FX receipt를 같은 원장 transaction에 저장하는 새 protocol, session 등록과
보존 기준이 먼저 필요합니다. 현재 PAPER DB, 외부 자료 DB와 미래 평가 계약을 대신하거나
우회하지 않습니다.
