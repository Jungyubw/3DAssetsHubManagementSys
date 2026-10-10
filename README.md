# 3DAssetsHubManagementSys

구글 공유 드라이브의 GLB 3D 모델을 AssetHub(assethub.bigbenett.com)에 프로젝트별로 일괄 등록하는 도구.

- 요구사항: [docs/SPEC.md](docs/SPEC.md)
- 일괄 등록 CLI: [assethub-importer/](assethub-importer/)

## 진행 상태

| 명령 | 상태 |
|---|---|
| `inventory` | 구현 완료 (맥에서 Google 로그인 후 실행) |
| `hub-snapshot` | 구현 완료, AssetHub 스크립트용 토큰 발급 대기 |
| `plan` | 구현 완료 |
| `apply` | 개발팀 생성·업로드 API 명세 대기 |
| `verify` | 개발팀 API 명세 대기 |

## 맥에서 실행하기

### 1. 설치 (최초 1회)

```bash
git clone https://github.com/Jungyubw/3dassetshubmanagementsys
cd 3dassetshubmanagementsys/assethub-importer
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env
```

### 2. Google OAuth 클라이언트 (최초 1회)

1. Google Cloud Console에서 프로젝트를 고르고 **Google Drive API**와 **Google Sheets API**를 사용 설정한다.
2. API 및 서비스 → 사용자 인증 정보 → **OAuth 클라이언트 ID 만들기** → 애플리케이션 유형 **데스크톱 앱**.
3. 내려받은 JSON을 `assethub-importer/client_secret.json`으로 저장한다(커밋되지 않음).
4. 처음 `inventory`를 실행하면 브라우저가 열려 로그인·동의를 받고, `token.json`이 로컬에 저장된다.

### 3. 실행

```bash
python cli.py inventory        # -> output/inventory.csv
python cli.py hub-snapshot     # -> output/hub_assets.csv, hub_projects.csv (.env의 ASSETHUB_TOKEN 필요)
python cli.py plan             # -> output/plan.csv, plan_summary.csv
python cli.py plan --without-hub   # 허브 토큰이 없을 때 규칙만 미리 확인 (이 결과로 등록하면 안 됨)
```

모든 결과는 `assethub-importer/output/`에 생기며 저장소에는 커밋되지 않는다.
