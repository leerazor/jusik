# Jusik

등록한 한국투자증권(KIS)과 키움증권 계좌를 한 화면에서 조회하는 로컬 읽기 전용 현황판입니다. 계좌별 자산 요약과 국내·해외 주식 보유내역을 함께 표시합니다. 프론트엔드는 Next.js App Router, React, TypeScript를 사용하고 백엔드는 Python 3.13과 FastAPI를 사용합니다.

## 로컬 실행

최초 의존성 설치와 계좌 설정을 마쳤다면 저장소 루트에서 다음 명령 하나로 백엔드와 프론트엔드를 함께 실행합니다.

```bash
./start.sh
```

http://localhost:3000 에 접속합니다. 설정된 ngrok 터널이 없으면 함께 실행하고 외부 접속용 HTTPS 주소도 표시합니다. 이미 같은 프론트엔드로 연결된 안전한 터널이 실행 중이면 이를 재사용하며 스크립트가 종료할 때 건드리지 않습니다. `Ctrl+C`로 이 스크립트가 시작한 계좌 백엔드, 연구 백엔드, 프론트엔드, ngrok과 각 자식 프로세스를 함께 종료합니다. 한 프로세스가 종료되면 나머지도 종료됩니다. 3000, 8000 또는 8001 포트가 이미 사용 중이면 해당 TCP 포트에서 수신 중인 프로세스에 종료 신호를 보냅니다. 5초 안에 종료되지 않으면 강제 종료한 뒤 서버를 다시 실행합니다. 포트를 해제하지 못하면 실행을 중단합니다. 포트 확인에는 `lsof`와 `ss`가 필요합니다. 스크립트는 실행 위치와 관계없이 동작하며 의존성을 자동 설치하지 않습니다.

앱 자체에는 사용자 인증이 없습니다. 외부 접속은 아래의 ngrok basic-auth 정책을 통과해야 하며 세 서버는 loopback에만 바인딩됩니다. 최초 설치 또는 개별 실행은 아래 명령을 사용합니다.

### ngrok 외부 접속 설정

ngrok 계정의 Linux 설치 안내에 따라 WSL에 ngrok을 설치하고 `ngrok config add-authtoken`으로 토큰을 등록합니다. 토큰과 비밀번호는 저장소에 넣지 않습니다. 다음 파일을 `~/.config/ngrok/jusik-policy.yml`에 만들되, 내용은 YAML 문법이 아니라 아래의 정확한 JSON 형식을 사용합니다. 사용자 이름과 긴 비밀번호는 직접 정한 값으로 바꿉니다.

```json
{
  "on_http_request": [
    {
      "actions": [
        {
          "type": "basic-auth",
          "config": {
            "credentials": ["jusik:REPLACE_WITH_RANDOM_PASSWORD"],
            "enforce": true
          }
        }
      ]
    }
  ]
}
```

정책 파일 권한을 제한한 뒤 `./start.sh`를 실행합니다.

```bash
chmod 600 ~/.config/ngrok/jusik-policy.yml
./start.sh
```

스크립트는 정책 파일이 현재 사용자 소유의 일반 파일인지, 권한이 `600`인지, 조건 없는 basic-auth 한 개만 강제하는지 먼저 확인합니다. 실행 중인 ngrok이 있으면 관리 API에서 목적지가 `127.0.0.1:3000` 또는 `localhost:3000`인 공식 HTTPS 주소인지 확인하고, 인증 없는 요청이 리디렉션 없이 `401`과 Basic 인증 요구를 반환할 때만 재사용합니다. 검증에 실패하면 서버를 시작하지 않습니다. 표시된 외부 주소는 PC나 모바일 브라우저에서 열고 정책 파일에 정한 사용자 이름과 비밀번호로 로그인합니다.

백엔드:

```bash
pyenv install -s 3.13.15
python -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.lock
backend/.venv/bin/python -m uvicorn jusik.main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log
```

프론트엔드:

```bash
nvm install
nvm use
cd frontend
npm ci
npm run dev
```

http://localhost:3000 을 엽니다. `./start.sh`는 실행마다 고유한 build 디렉터리에 프론트엔드를 먼저 production build한 뒤 기존 3000·8000·8001 listener를 교체하고 두 백엔드와 Next.js production server의 준비 상태를 확인합니다. build가 실패하면 현재 서버가 사용하는 산출물과 프로세스를 건드리지 않습니다. `/research`에서는 별도 연구 백엔드의 대상 종목, 일정, 검증 결과, KIS 읽기 전용 실시간 시세, 승인 대기 신호와 앱 내부 paper 체결을 확인합니다. 처음 사용하는 경우 `/research-guide.html`에서 화면 순서와 결과 해석을 확인할 수 있습니다. 인증정보와 증권 계좌 식별자는 백엔드에만 둡니다. 실제 주문 endpoint와 증권사 주문 호출은 구현하지 않았습니다.

## 한국투자증권 설정

백엔드는 저장소 루트의 `.env.prod`를 명시적으로 불러옵니다. 기존 파일은 보존하세요. 새로 설치할 때는 `.env.example`을 `.env.prod`로 복사한 뒤 로컬에서만 값을 채웁니다. 실제 인증정보와 계좌 식별자는 절대 커밋하지 마세요. 이 현황판은 모의투자 잔고가 아닌 실전 계좌의 **조회 권한**을 사용하므로 `.env.dev`는 불러오지 않습니다. 한국투자증권의 공식 실전 URL만 허용하며, 환경 변수가 파일 값보다 우선합니다.

기존 단일 계좌 변수도 계속 지원합니다.

```dotenv
KIS_APP_KEY=replace_with_app_key
KIS_APP_SECRET=replace_with_app_secret
KIS_CANO=replace_with_account_number
KIS_ACNT_PRDT_CD=replace_with_product_code
```

여러 계좌는 한 줄 JSON 배열로 추가합니다. `id`는 화면에서 쓰는 고정 식별자이고, `label`은 백엔드가 외부에 표시하는 유일한 계좌 이름입니다. 각 항목은 전역 App Key와 App Secret을 상속합니다. 다른 KIS 앱을 사용하는 계좌는 해당 항목에 `app_key`와 `app_secret`을 모두 넣으세요.

```dotenv
KIS_ACCOUNTS=[{"id":"general","label":"일반 계좌","cano":"00000000","acnt_prdt_cd":"01"},{"id":"account_2","label":"두 번째 계좌","cano":"11111111","acnt_prdt_cd":"01","app_key":"replace_with_other_app_key","app_secret":"replace_with_other_app_secret"}]
```

계좌번호는 KIS 8자리 `CANO`와 2자리 상품코드를 사용합니다. 계좌 ID와 증권 계좌 조합은 중복될 수 없습니다. 빈 배열, 잘못된 JSON, 불완전한 인증정보, 중복 계좌는 비밀값을 노출하지 않고 백엔드 시작을 중단합니다.

백엔드는 접근 토큰을 메모리에 보관하고 같은 앱 인증정보를 쓰는 계좌에서는 만료 직전까지 같은 토큰을 재사용합니다. KIS 토큰 발급 제한을 피하려면 백엔드 worker 하나를 계속 실행하세요. 인증 실패 후에는 인증정보 조합별로 1분 동안 재시도를 막습니다. 증권사 요청 제한을 줄이기 위해 잔고 요청 간격은 최소 1초입니다. 포트폴리오 응답은 백엔드에서 30초 동안 캐시하며, 브라우저와 Next.js 데이터 캐시는 끕니다. 30초 안에 새로고침하면 원래 시각이 유지된 같은 스냅샷을 반환합니다.

## 키움증권 설정

키움 계좌는 저장소 루트의 `.env.kiwum`을 별도로 불러옵니다. 이 파일이 없으면 기존 KIS 계좌만 조회합니다. 새 환경에서는 `.env.kiwum.example`을 `.env.kiwum`으로 복사하고 로컬에서만 값을 채우세요. 실제 파일은 Git에서 제외됩니다.

```dotenv
APP_ENV=kiwum
APP_KEY=replace_with_app_key
APP_SECRET=replace_with_app_secret
BASE_URL=https://api.kiwoom.com

# 선택 안전 검증: 두 값을 함께 설정하거나 둘 다 생략합니다.
# CANO=replace_with_8_digit_account_number
# ACNT_PRDT_CD=replace_with_2_digit_product_code
```

`BASE_URL`은 공식 운영 origin 또는 키움에서 안내하는 토큰 URL `https://api.kiwoom.com/oauth2/token`을 사용할 수 있으며, 백엔드는 운영 origin으로 정규화합니다. 모의투자 및 임의 호스트는 받지 않습니다. 현재 설정은 운영 계좌의 읽기 전용 잔고 조회만 지원합니다.

토큰 발급 후 `ka00001`로 토큰에 연결된 계좌번호가 올바른 10자리인지 먼저 확인합니다. 키움 토큰은 연결된 단일 계좌의 잔고만 조회합니다. `CANO` 8자리와 `ACNT_PRDT_CD` 2자리는 선택 안전 검증값이며, 설정하려면 두 값을 함께 입력해야 합니다. 명시한 조합이 토큰 계좌와 일치할 때만 잔고를 조회합니다. 두 값을 생략해도 발견한 계좌번호는 저장하거나 응답에 포함하지 않습니다. 키움의 지정단말기 인증 오류가 발생하면 키움 REST API 이용 등록 및 지정단말기 설정을 확인하세요.

키움은 국내 평가금, 원화·외화 예수금, 해외증권 원화 평가금, 국내·외 부채를 읽기 전용 API로 조회합니다. 필요한 구성요소를 모두 검증했을 때만 `국내주식 평가 + 원화·외화 예수금 + 해외주식 원화평가 - 총부채`를 추정 순자산으로 표시합니다. 구성요소나 환율이 없으면 국내 추정예탁자산만 별도로 표시하고 통합 순자산에는 포함하지 않습니다. 미국 주식은 거래소와 종목 필터를 생략한 전체 잔고 조회가 성공했을 때 미국 시장 결과에 포함합니다.

## 원화 환산과 종목 평가

모든 국내·해외 주식 표와 합계는 원화로 표시합니다. 증권사 계좌 응답에서 종목별 환율이 검증되면 그 환율을 우선 사용하고, 없으면 [Frankfurter](https://frankfurter.dev/)의 통화별 KRW 일별 기준환율을 `Decimal`로 받아 소수점 변환 오차 없이 계산합니다. 평균매입가와 현재가도 종목에 표시된 같은 환율을 적용하며, 환율 기준일과 출처를 화면에서 확인할 수 있습니다. 환율이 없거나 5일보다 오래되면 해당 종목의 원화 값을 조회 불가로 남기며, 일부 종목만 더한 원화 합계를 전체 합계처럼 표시하지 않습니다. 원통화 잔고도 종목 상세에 함께 표시합니다.

매입금액과 평가손익도 현재 표시된 같은 환율로 환산하므로, 실제 매입 시점 환율을 기준으로 한 환차손익은 포함하지 않습니다.

보유 종목의 PER, PBR, EPS, BPS는 KIS 국내 현재가 및 해외주식 현재가상세 조회에서 가져옵니다. 키움 미국 종목은 NASDAQ·NYSE·AMEX를 순차 조회하고 현재가상세 응답의 종목코드와 통화가 보유 종목과 정확히 일치할 때 거래소를 확정합니다. ETF는 개별기업 가치평가 규칙에서 제외합니다. 화면의 매수·보유·매도 검토 문구는 다음 고정 규칙을 설명하는 점검 신호이며 투자 자문이나 자동 주문이 아닙니다.

- 손실률 -12% 이하 또는 수익률 25% 이상: 매도 또는 차익 실현 검토
- EPS 양수이고 PER 15 이하 또는 PBR 1.5 이하: 매수 검토
- 지표 누락, 오류, 48시간 초과, 미래 시각: 판단 보류
- 나머지: 보유 검토

## Telegram 알림

백엔드는 5분마다 보유 종목과 규칙 신호를 다시 확인합니다. 새 매수·매도 검토 신호는 앱 안에 기록합니다. 같은 계좌·시장·종목·규칙 버전의 같은 신호는 SQLite에 저장해 재시작 후에도 중복 전송하지 않습니다. 판단 보류는 기존 상태를 지우지 않습니다. SQLite는 단일 사용자 로컬 앱에서 이 작은 알림 상태를 별도 서버 없이 영구 보존하기 위해 사용합니다.

무료 휴대폰 알림은 Telegram Bot API를 사용합니다. 다른 서비스에서 webhook이나 polling에 사용하는 봇의 연결을 바꾸지 않도록 `@BotFather`에서 Jusik 전용 봇을 만드세요. 토큰은 로컬 `.env.prod`의 `TELEGRAM_BOT_TOKEN`에만 저장하고 채팅이나 명령행에 붙여 넣지 않습니다.

```bash
cd backend
.venv/bin/python -m jusik.telegram_setup

# 연결 저장 후 일반 확인 메시지 한 건을 보내려는 경우에만 사용합니다.
.venv/bin/python -m jusik.telegram_setup --send-test
```

명령은 봇과 기존 webhook 상태를 확인한 뒤 일회용 링크를 표시합니다. 2분 안에 휴대폰 Telegram에서 링크를 열고 시작을 눌러야 하며, 정확한 난수 응답을 보낸 개인 채팅의 사람 계정만 연결합니다. 임의의 최근 채팅을 선택하지 않습니다. 연결되면 `.env.prod`의 `TELEGRAM_ENABLED`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 세 키만 원자적으로 저장하고 파일 권한을 `0600`으로 제한합니다. 완료 후 백엔드를 재시작해야 감시 알림 전송이 시작됩니다.

기본값 `TELEGRAM_ENABLED=false`에서는 외부 메시지를 보내지 않습니다. `--send-test` 성공 표시는 Telegram Bot API가 메시지를 접수했다는 뜻이며 실제 휴대폰 수신은 Telegram 앱에서 별도로 확인해야 합니다. timeout처럼 접수 결과를 알 수 없으면 중복 방지를 위해 자동 재전송하지 않습니다. 이미 SQLite에 기록된 동일 신호도 Telegram을 연결했다는 이유만으로 다시 보내지 않으며, 상태가 바뀐 뒤 새 매수·매도 신호가 생길 때 전송합니다. Telegram 메시지에는 증권 계좌 ID나 번호를 넣지 않습니다.
이 감시는 로컬 백엔드 프로세스에서 실행되므로 앱, WSL 또는 PC가 꺼져 있으면 알림도 중단됩니다.

## 금리와 외부 소식

보유 종목 조회와 별도로 30분 캐시를 두고 아래 공개 소스를 병렬 수집합니다. 한 소스가 느리거나 실패해도 잔고 화면을 막지 않습니다. 화면은 각 소스의 정상·실패 상태, 링크, 수집 시각을 표시합니다.

- 한국은행 기준금리 표와 한국은행 통화정책 RSS
- FRED의 미국 연방기금 목표금리 하단·상단 일별 CSV와 Federal Reserve 통화정책 RSS
- BBC World RSS의 국제·전쟁 소식
- Google News의 최근 7일 Truth Social 관련 RSS 검색 결과
- 운영자 FAQ가 공개한 Trump's Truth RSS의 트럼프 계정 게시물 제3자 보관본

기사별 대응 평가는 금리 민감도, 환율, 에너지·방산·운송 노출, 원문 교차 확인 같은 조건부 점검 문구입니다. Google News 관련 보도와 Trump's Truth 보관본은 Truth Social의 공식·완전 피드가 아닙니다. 보관본에는 재게시물이 포함될 수 있고 게시물의 주장이 실제 정책을 뜻하지 않으므로 Truth Social 원문과 공식 발표를 교차 확인해야 합니다. 앱은 제3자 RSS가 제공한 제목과 최대 280자의 일반 텍스트 발췌만 표시하며 Truth Social 서버를 직접 조회하거나 기사 본문을 수집하지 않습니다.

## 타 증권사 계좌

이 앱은 한국투자증권과 키움증권 계좌를 조회합니다. `KIS_ACCOUNTS`에 메리츠증권이나 신한투자증권 계좌를 넣어도 조회할 수 없습니다. 각 증권사의 App Key와 App Secret은 해당 증권사 API 호출에만 사용됩니다.

토스처럼 여러 금융회사의 정보를 한 화면에 모으는 서비스는 KIS 다계좌 설정과 다른 문제입니다. 각 증권사의 공식 조회 API를 개별 연동하거나, 사용자 동의를 받아 표준 API로 금융정보를 전송하는 마이데이터 사업 구조가 필요합니다. 금융위원회는 여러 금융회사의 개인신용정보를 수집해 사용자에게 제공하는 마이데이터 서비스를 허가 대상으로 설명합니다. 개인 로컬 앱에 KIS 키만 추가해서 같은 기능을 만들 수는 없습니다.

- 한국투자증권 계좌 여러 개: 현재 `KIS_ACCOUNTS`에 직접 등록합니다.
- 키움증권 계좌: `.env.kiwum`의 인증정보에 연결된 단일 계좌를 조회합니다.
- 메리츠·신한 등 다른 증권사: 증권사별 공식 조회 API의 제공 범위, 이용 조건, 사용자 인증 방식을 각각 확인한 뒤 별도 adapter를 구현해야 합니다.
- 토스 수준 통합: 마이데이터 또는 제휴 서비스의 법적·보안·운영 요건을 먼저 결정해야 합니다.

## 조회 범위와 의미

- `KIS_ACCOUNTS`에 명시한 모든 계좌 또는 기존 `KIS_CANO` 단일 계좌를 조회합니다. KIS는 고객의 모든 계좌를 자동 발견하는 API를 제공하지 않습니다.
- `.env.kiwum`이 있으면 토큰에 연결된 키움 계좌 한 개를 추가로 조회합니다. 선택 검증값을 설정한 경우 토큰 계좌와 일치하지 않으면 잔고 API를 호출하지 않습니다.
- KIS 투자계좌 자산현황에서 받은 원화 순자산, 총 평가금액, 예수금, 미실현 손익, 해외주식 평가금액을 표시합니다. 지원하지 않거나 없는 요약 필드는 0으로 바꾸지 않고 사용할 수 없음으로 남깁니다.
- 국내주식과 미국(NASD 실전 조회는 미국 거래소 포함)·홍콩·상하이·선전·일본·하노이·호치민 해외주식을 조회합니다.
- 잔고 API 스냅샷이며 실시간 시세가 아닙니다. 특히 장 마감 중 가격은 지연될 수 있습니다. 조회 완료 시각은 내부에서 UTC로 저장하고 한국 시각으로 보여 주며 거래소 시세 시각과 다릅니다.
- 보유 수량, 평균 매입가, 현재가, 매입금액, 평가금액, 미실현 손익, 계산 수익률을 표시합니다.
- 통합 원화 순자산은 KIS가 제공한 원화 순자산과 구성요소가 모두 검증된 키움 추정 순자산의 합계입니다. KIS 순자산에 주식 평가금액을 다시 더하지 않습니다. 부분 합계와 사용할 수 없는 합계는 화면에 명확히 표시합니다.
- 원화·달러·홍콩달러·위안·엔·베트남동 주식은 모두 원화로 환산해 합산합니다. 실제 환전 가능액이나 세금 계산이 아닙니다. 채권, 선물·옵션, 연금 전용 포지션, 실현 손익은 이번 버전 범위 밖입니다.
- 백엔드는 `Decimal`로 계산하고 금융값은 문자열로 API를 통과합니다. 수익률은 소수 둘째 자리에서 반올림합니다. 표시용 가격 정밀도는 부동소수점 계산 없이 잘라 냅니다. 매입금액이 0이면 수익률은 정의되지 않아 대시로 표시합니다.
- 한 시장을 포함하려면 모든 연속 조회 페이지가 성공해야 합니다. 완전히 같은 중복 포지션은 제거하고, 서로 충돌하는 중복 포지션은 해당 시장 조회를 실패 처리해 이중 합산을 막습니다. 수량이 0인 포지션은 제외합니다.
- 키움 국내 잔고는 동일 종목의 현금·신용 보유분을 합산하고 평균매입가를 수량 가중 계산합니다. 미국 잔고 수량은 주문가능수량이 아닌 `poss_qty`를 사용합니다.
- 계좌와 시장 조회 실패를 명확히 표시합니다. 성공한 계좌와 시장 결과는 계속 표시합니다. 주식 합계는 성공한 시장 조회만 포함하고, 순자산 합계는 검증된 원화 순자산이 있는 계좌만 포함합니다. 필수 보유 필드가 없거나 잘못되면 0으로 바꾸지 않고 검증에 실패합니다.
- 날짜별 포트폴리오 스냅샷과 수익률 추이 차트는 없습니다. SQLite에는 중복 알림 방지를 위한 신호 상태와 최근 알림만 저장합니다.

## 검사

```bash
cd backend
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy jusik
cd ../frontend
npm run lint
npm run typecheck
npm run build
```

테스트는 모의 증권사 응답만 사용하며 주문을 내지 않습니다. 설정 검증, 계좌 일치 확인, 토큰 재사용, 부분·전체 실패, 잔고 0, `Decimal` 정밀도, 음수·누락 값, 페이지 조회, 시간대 경계, 캐시 합치기, 오류 정보 가리기를 검증합니다. 부분 체결과 취소·거절 주문은 이 앱이 처리하지 않으며 증권사가 반영한 최종 보유내역을 조회합니다.

## GitHub

remote가 없으면 README나 license 없이 빈 비공개 GitHub 저장소를 만듭니다. 그 뒤 `git remote add origin https://github.com/YOUR_USERNAME/jusik.git`로 URL을 설정합니다. Git을 아직 초기화하지 않았다면 먼저 `git init -b main`을 실행합니다.

커밋 전 `git status --short`, `git check-ignore .env.prod .env.dev`를 실행하고 `git diff --cached`를 확인합니다. 프로젝트 코드와 자리표시자 설정만 stage 합니다. 첫 커밋은 `git push -u origin main`으로 push 합니다. 무시된 환경 파일을 강제로 추가하지 마세요. 이 설정은 커밋·원격 저장소 생성·push를 자동으로 하지 않습니다.

## API 참고 자료

- [KIS 국내주식 잔고조회 예제](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_balance/inquire_balance.py)
- [KIS 투자계좌 자산현황조회 예제](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_account_balance/inquire_account_balance.py)
- [KIS 해외주식 잔고조회 예제](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/inquire_balance/inquire_balance.py)
- [KIS Open API 서비스](https://apiportal.koreainvestment.com/apiservice)
- [키움 REST API 공식 명세](https://github.com/Kiwoom-Securities/Kiwoom-REST-API)
- [금융위원회 마이데이터 허가 안내](https://www.fsc.go.kr/po010105/74324)
- [금융결제원 오픈뱅킹 서비스](https://openapi.kftc.or.kr/service/openBanking)
- [Next.js 설치](https://nextjs.org/docs/app/getting-started/installation)
