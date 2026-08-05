# 경찰 판례·법령 AI 봇 (목업 RAG 시연)

경찰 현장 표현을 법률 용어로 변환하고, 관련 판례·법조문을 조회해 적법성 판단·개인 책임
위험·상급심 정보 등을 정리해 보여주는 **시연용 목업 웹 애플리케이션**입니다.

> 이 애플리케이션은 실제 법률 자문이나 수사·재판 판단을 대체하지 않습니다. 모든 판례·법조문·
> 응답은 서버 배포물에 사전 번들된 목업 데이터셋에서만 결정적으로 산출되며, 실시간으로
> 갱신되지 않습니다.

> 이 저장소에는 위 목업 시연 애플리케이션과 완전히 분리된 **실제 RAG 파이프라인**(`rag/`
> 패키지, Gemini 3.6 Flash + Chroma + FastAPI)도 포함되어 있습니다. 목업 계층은 이
> 파이프라인을 임포트하지 않으며, 목업의 "외부 origin 호출 0건" 요구사항에도 영향을 주지
> 않습니다. 실제 RAG 사용법은 하단의 [실제 RAG 파이프라인](#실제-rag-파이프라인-gemini--chroma--fastapi)
> 섹션을 참고하세요.

## 핵심 특징 (목업 시연 애플리케이션)

- **완전 목업 기반**: 검색 엔진, 임베딩, 벡터 데이터베이스, 외부 판례·법령 API, 원격 음성
  인식, 실제 생성형 모델(LLM)을 전혀 사용하지 않습니다. 모든 결과는 `fixtures/` 에 정의된
  고정 데이터셋에서 결정적으로 조회·가공됩니다.
- **결정적이고 추적 가능한 응답**: 화면에 표시되는 모든 법률 관련 값에는 근거가 된 판례·
  법조문·출처 ID(provenance)가 함께 따라붙습니다.
- **8개 경찰 직무 시나리오**: 현행범체포, 임의동행, 긴급체포, 압수수색, 미란다 원칙 고지,
  진술거부권, 가정폭력 초동조치, 음주단속 각각에 적법·위법 판례를 최소 1건씩 포함합니다.
- **단계별 요약, 개인 책임 위험, 유사도 경고, 상급심/확정 정보, 사실관계 타임라인, 보고서
  재사용** 등 실무에서 필요한 검토 흐름을 화면 단위로 제공합니다.
- **동일 origin 전용 배포**: 클라이언트는 같은 서버로만 통신하며(CSP로 외부 origin 차단),
  사용자 입력·선택 문구·보고서 본문을 영구 저장하거나 외부로 전송하지 않습니다.

## 아키텍처 개요

계층 경계를 명확히 나누어 구현했습니다.

| 계층 | 위치 | 언어 | 책임 |
|---|---|---|---|
| 표현(도메인) | `domain/` | Python | 질의 해석, 시나리오 분류, 정렬, 위험 판정, 요약/보고서 생성 등 순수 로직. 현재 시각·난수·네트워크 의존 없음 |
| 데이터 | `data/` | Python | fixture 데이터 모델 정의, 구조/교차 참조 검증, `ValidatedDataset` 생성 |
| 애플리케이션 | `app/` | Python | 명령(Command) 처리, 목업 RAG 상태 전이(reducer), 오류 스냅샷 |
| 웹 서버 | `web/` | Python | WSGI 기반 HTTP 라우팅, 요청 검증, JSON 응답 생성, 정적 자산 제공, 배포 설정 |
| 목업 데이터 | `fixtures/` | Python | 서버 배포물에 번들되는 최소 유효 목업 데이터셋(판례, 법조문, 응답 템플릿 등) |
| 클라이언트 | `static/` | HTML/CSS/JS | 서버가 계산한 값을 표시만 하는 최소 상호작용 레이어. 법률 로직을 재계산하지 않음 |
| 테스트 | `tests/` | Python (pytest) | 단위 테스트, Hypothesis 기반 속성 테스트(PBT), 통합/E2E 테스트, 접근성 테스트 |

전체 요구사항·설계·작업 목록은 `.kiro/specs/police-case-law-ai-bot/`(requirements.md,
design.md, tasks.md)에 정리되어 있습니다.

## 시작하기

### 요구 사항

- Python 3.9 이상, 3.15 미만 (3.14 포함, 실제 3.14.6 환경에서 pytest 전체 스위트 검증됨)

### 1. 가상환경 생성 및 의존성 설치

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

macOS/Linux 셸을 사용한다면 `source .venv/bin/activate`로 대체합니다.

위 목업 시연 애플리케이션(`domain/`, `data/`, `app/`, `web/server.py`, `fixtures/`)은 여전히
표준 라이브러리만 사용하는 순수 구현입니다. `pyproject.toml`의 `dependencies`에 등록된
`chromadb`/`google-genai`/`fastapi`/`uvicorn`/`pydantic`/`pypdf`/`python-multipart`/
`python-dotenv`는 아래 [실제 RAG 파이프라인](#실제-rag-파이프라인-gemini--chroma--fastapi)
(`rag/` 패키지) 전용이며, 목업 계층의 임포트 경로에서는 사용하지 않습니다. `dev` 추가
의존성(`pytest`, `hypothesis`, `mypy`)은 개발 시 필요합니다.

### 2. 웹 서버 실행

```powershell
python -m web.server
```

기본값으로 `http://127.0.0.1:8000` 에서 서비스됩니다. 브라우저로 `/`(상황 검색)와
`/results`(직무 시나리오 비교)에 접속할 수 있습니다.

### 3. 배포 설정 (환경변수)

비밀값·외부 자격 증명은 전혀 사용하지 않으며, 아래 환경변수로만 배포 방식을 조정합니다.

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `POLICE_BOT_HOST` | `127.0.0.1` | 서버가 바인딩할 호스트 |
| `POLICE_BOT_PORT` | `8000` | 서버 포트 (1–65535) |
| `POLICE_BOT_PUBLIC_URL` | `http://127.0.0.1:8000` | 공개 접속 URL (절대 HTTP/HTTPS URL) |
| `POLICE_BOT_HTTPS_ENABLED` | URL 스킴에 따라 자동 결정 | `true`/`false`. `true`이면 공개 URL이 반드시 `https`여야 함 |
| `POLICE_BOT_RUN_MODE` | `production` | `development` / `production` / `test` 중 하나 |

예시:

```powershell
$env:POLICE_BOT_HOST = "0.0.0.0"
$env:POLICE_BOT_PORT = "8080"
$env:POLICE_BOT_PUBLIC_URL = "http://localhost:8080"
python -m web.server
```

## 테스트

```powershell
pytest
```

- 단위 테스트, Hypothesis 기반 속성 테스트(각 속성 최소 100회 실행), 통합/E2E 테스트,
  접근성 관련 테스트를 포함해 전체 스위트를 실행합니다.
- 속성 테스트는 실패 시 seed와 축소된 최소 반례를 보존하므로 실패 로그를 그대로 재현에
  활용할 수 있습니다.

특정 파일/모듈만 실행하려면:

```powershell
pytest tests/test_timeline.py -q
```

## 정적 타입 검사

```powershell
mypy
```

`pyproject.toml`의 `[tool.mypy]` 설정에 따라 `domain`, `data`, `app`, `web`, `fixtures`,
`tests` 전체에 대해 strict 모드로 검사합니다.

## 프로젝트 구조

```
.
├── app/          # 애플리케이션 상태 전이(reducer)와 명령 처리
├── data/         # fixture 데이터 모델과 데이터셋 검증기
├── domain/       # 질의 해석·분류·정렬·위험 판정 등 순수 도메인 로직
├── fixtures/     # 서버에 번들되는 목업 데이터셋 (판례·법조문·응답 템플릿 등)
├── static/       # 클라이언트 HTML/CSS/JS (app.js/app.css: 목업 전용, real_rag.js: 실제 RAG 연동)
├── web/          # WSGI 웹 서버, 라우팅, 배포 설정(config.py)
├── tests/        # pytest 단위/속성/통합/접근성 테스트
├── rag/          # 실제 RAG 파이프라인(Gemini + Chroma + FastAPI, 목업과 완전 분리)
├── precedent/    # crawl_precedents.py로 수집한 판례 마크다운(실제 RAG 인제스트 대상)
├── status/세부법령/ # 법령 PDF(실제 RAG 인제스트 대상)
├── .kiro/specs/  # 요구사항(requirements.md)·설계(design.md)·작업 목록(tasks.md)
├── .env.example  # 실제 RAG용 환경변수 예시(GEMINI_API_KEY 등)
├── pyproject.toml
└── README.md
```

## 주요 화면과 기능

- **상황 검색 (`/`)**: 텍스트 질의 입력 또는 사전 정의된 음성 시연 선택 → 현장 표현 ↔
  법률 검색어 대응 확인 → 목업 검색 결과와 응답, 판례 상세, 선택 영역 재검토, 사실관계
  타임라인, 보고서 생성까지 이어지는 흐름을 제공합니다.
- **직무 시나리오 (`/results`)**: 8개 경찰 직무 시나리오 중 하나를 선택하면 서버가 분류한
  적법/위법/판단 혼재 판례를 3열(또는 좁은 화면에서는 탭) 비교로 보여줍니다. 형사/민사/행정
  보조 필터로 교집합을 좁힐 수 있습니다.
- **판례 상세**: 3줄/10줄/상세 요약, 개인 책임 위험(민사·형사·징계), 유사도 경고와 핵심
  사실 차이, 법령 기준 상태(현행법/구법/판별 불가), 상급심·확정 정보, 판례 전문을 확인할
  수 있습니다.
- **사실관계 타임라인**: 인식된 사건을 시간순/시점 미상으로 분리해 표시하고, 시간·주체·행위를
  직접 수정할 수 있습니다. 수정 내용은 보고서 생성에도 즉시 반영됩니다.

지원 범위, 데이터 구조, 지원 질의 목록 등 더 자세한 내용은 `.kiro/specs/police-case-law-ai-bot/requirements.md`와 `design.md`를 참고하세요.

## 실제 RAG 파이프라인 (Gemini + Chroma + FastAPI)

`rag/` 패키지는 위 목업 시연 애플리케이션과는 별개의, 실제 판례·법령 데이터를 사용하는
검색·생성 파이프라인입니다. `crawl_precedents.py`로 수집한 판례 마크다운(`precedent/`)과
법령 PDF(`status/세부법령/`)를 인제스트해 Chroma 로컬 벡터 인덱스에 저장하고, Gemini로
검색·리포트 생성을 수행합니다.

> ⚠️ 이 파이프라인이 생성하는 결과는 실제 Gemini 모델과 판례·법령 원문 데이터를 사용하지만,
> 여전히 시연/보조 도구입니다. 최종 법률 판단은 관계 법령과 담당자 검토가 필요합니다.
> 또한 아래 FastAPI 서버는 **인증·접근 제어를 구현하지 않은 상태**이므로, 로컬 개발 환경
> 밖(사내망 공유, 공개 배포 등)에 노출하려면 반드시 인증을 추가해야 합니다.

### 1. API 키 설정

```powershell
Copy-Item .env.example .env
notepad .env   # GEMINI_API_KEY=발급받은키 로 채운 뒤 저장
```

`.env`는 `.gitignore`에 포함되어 있어 git에 커밋되지 않습니다. PowerShell 세션에만
임시로 설정하려면 `$env:GEMINI_API_KEY="발급받은키"` 를 사용해도 됩니다.

### 2. 의존성 설치

이미 `pip install -e ".[dev]"`로 설치했다면 `chromadb`, `google-genai`, `fastapi`,
`uvicorn`, `pydantic`, `pypdf`, `python-multipart`, `python-dotenv`가 함께 설치됩니다
(모두 정확한 버전으로 고정되어 있습니다). Python 3.10 이상이 필요합니다.

### 3. RAG 서버 실행

```powershell
uvicorn rag.api:app --port 8001
```

서버 시작 시 `precedent/`, `status/세부법령/`의 원문을 청크로 나눠 Gemini로 임베딩하고
`.chroma_index/`(git에 커밋되지 않음)에 저장합니다. 이미 인덱싱된 경우에는 재사용하며,
강제로 재인덱싱하려면 `POST /api/rag/reindex?force=true`를 호출하세요(Gemini API 비용이
다시 발생합니다).

| 엔드포인트 | 메서드 | 설명 |
|---|---|---|
| `/api/rag/health` | GET | 초기화 상태와 인덱싱된 청크 수 확인 |
| `/api/rag/query` | POST | 질의 검색 + (옵션) Gemini 적법성 리포트·타임라인 생성 |
| `/api/rag/reindex` | POST | 인덱스 재사용 또는(`force=true`) 강제 재구축 |

`/api/rag/query` 요청 예시:

```json
{ "query": "새벽에 확성기로 소음을 낸 집회 신고가 들어왔다", "top_k": 8, "instance": "1심" }
```

`instance`(1심/항소심/상고심)와 `category`(경범죄/식품/청소년 등) 필터는 선택 사항이며,
지정하지 않으면 전체 판례를 대상으로 검색합니다(인덱싱은 항상 전체 판례를 대상으로 하고,
필터링은 검색 시점에 유연하게 적용하는 방식을 사용합니다).

### 4. 목업 웹 화면에서 함께 사용하기

목업 서버(`python -m web.server`)의 상황 입력 화면에는 "실제 AI(Gemini) 분석도 함께
요청" 체크박스가 있습니다. 이 체크박스를 켜고 RAG 서버(위 3번, 기본 포트 8001)가 실행
중이면 목업 결과와 별도로 실제 Gemini 분석 결과가 같은 화면 하단에 표시됩니다. 체크를
끄거나 RAG 서버가 꺼져 있으면 목업 흐름에는 전혀 영향이 없습니다. 이 연동 코드는
`static/real_rag.js`에만 있으며 `static/app.js`(목업 전용, 외부 origin 호출 0건)에는
포함되지 않습니다.

### 5. 환경변수 전체 목록

`.env.example` 파일에 전체 목록과 기본값이 정리되어 있습니다. 주요 항목:

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `GEMINI_API_KEY` | (필수) | Google AI Studio에서 발급받은 API 키 |
| `RAG_GENERATION_MODEL` | `gemini-3.6-flash` | 리포트 생성에 사용할 모델 |
| `RAG_EMBEDDING_MODEL` | `gemini-embedding-001` | 임베딩 모델 |
| `RAG_CHROMA_PATH` | `.chroma_index` | Chroma 로컬 인덱스 저장 경로(저장소 루트 기준) |
| `RAG_TOP_K` | `8` | 기본 검색 결과 개수 |

## 보안·개인정보 관련 참고사항

- 입력한 상황 질의, 선택 문구, 보고서 본문은 영구 저장하거나 외부 분석·제3자에 공유하지
  않으며, 애플리케이션 로그에는 요청 메타데이터(메서드, 경로, 상태 코드, 콘텐츠 길이)만
  기록합니다.
- `default-src 'self'; connect-src 'self'` CSP를 적용해 동일 origin 통신만 허용하고 외부
  origin 연결을 차단합니다.
- 비밀값·API 키·외부 자격 증명을 요구하거나 저장하지 않습니다.
