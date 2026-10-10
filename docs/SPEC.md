# AssetHub GLB 일괄 등록 스크립트 개발 요구사항

2026-10-10 · Dr. Woo

## 개요

구글 공유 드라이브에 흩어진 GLB 3D 모델을 AssetHub(assethub.bigbenett.com)에 프로젝트별로 일괄 등록하는 스크립트를 Claude Code로 개발한다. 공유 드라이브의 GLB가 2,300개를 넘어 브라우저 자동 등록(모델당 약 1분, 30시간 이상)으로는 감당하기 어렵기 때문에 API 기반 스크립트로 전환한다.

### 확정된 결정 사항 (사용자 결정)

| 항목 | 결정 |
|---|---|
| 대상 범위 | 공유 드라이브의 모든 폴더 |
| 등록 포맷 | GLB만 |
| 같은 모델의 여러 파일 | 수정본은 대표 1개만, 용도가 다른 변형(예: `_dressed`, 원본·Unity·웹 경량본)은 별도 등록 |
| 애매한 중복 | 규칙대로 자동 결정하고 결과만 보고 |
| 등록 이름 | `분류_대상_변형_v번호` 규칙 적용, 원래 파일명은 원장에 보관 |
| 설명·태그 | 파일명과 폴더 정보로 자동 작성 |
| 원장 | 구글 드라이브의 구글 시트 |
| 프로젝트 단위 | 최상위 공유 드라이브 1개 = 허브 프로젝트 1개, 하위 폴더 이름은 태그 |
| 기존 허브 프로젝트 | 같은 과제의 프로젝트가 있으면 거기에 등록, 없으면 드라이브 폴더 이름으로 새로 생성 |
| 여러 드라이브에 있는 같은 모델 | 대표 프로젝트 하나에 등록하고 나머지 드라이브 이름은 태그 |

제외: 내 컴퓨터 백업(Desktop) 폴더의 GLB, GLB 이외 포맷(FBX·BLEND·STEP 등). 허브에 이미 등록된 모델은 대조해서 건너뛴다.

## 현황 조사 결과

공유 드라이브에는 GLB가 최소 2,347개(약 11.8GB) 있고, 허브에는 8개 프로젝트에 290개가 등록돼 있다. 드라이브 목록은 조사 중 25페이지에서 멈췄기 때문에 실제 파일 수는 더 많다.

| 항목 | 값 |
|---|---|
| 공유 드라이브 | 약 140개 (PJ_ 과제, PP_ 제안, TF_ 태스크포스, DP_ 부서, IGI_ 사내 등) |
| GLB 파일 (조사분) | 2,347개, 약 11.8GB |
| 이름·크기까지 같은 완전 중복을 뺀 수 | 2,088개 |
| 크기 분포 | 10MB 미만 2,108개 · 10MB 이상 239개 · 50MB 이상 36개 |
| 수정 연도 | 2025년 1,764개 · 2026년 583개 |
| GLB가 들어 있는 폴더 | 224개 이상 |
| 허브 프로젝트 | 8개 |
| 허브 등록 에셋 | 290개 (원본 파일명·크기 조회 가능) |

### 드라이브 구조의 특징

- GLB가 공유 드라이브 아래 6~8단계 깊이에 있다. 예: `<공유 드라이브>/방송대 제안작업/AED_실감형콘텐츠_S2/02_웹프로젝트/웹콘텐츠/_이전_v1.14/3D에셋/glb/emt.glb`
- `_이전_v1.x` 같은 이전 버전 폴더에 같은 이름의 파일이 여러 벌 있다.
- 같은 이름이어도 크기가 다른 경우가 많다. 예: `barista.glb` 952KB · 892KB · 5.8MB (웹 경량본, 원본, Unity용이 함께 있음)
- Drive 커넥터로는 공유 드라이브 루트 이름이 `Drive`로만 나온다. 드라이브 이름은 Drive API `drives.list`로 가져와야 한다.
- 맥 동기화 경로: `/Users/jywoo/Library/CloudStorage/GoogleDrive-jungyub.woo@ontwins.com/공유 드라이브/<드라이브명>/…`

### 허브 기존 등록분의 관례

- 이름은 `[콘텐츠명] 대상` 형식의 한글이 많다. 예: `[AED S2] 바리스타`, `[IP19 의료 통역] 진찰대·칸막이 커튼`
- 같은 모델의 원본·Unity·웹 경량본을 별도 에셋으로 등록해 왔다. 예: `[AED S1 원본] 구급대원` 7.4MB, `[AED S1 Unity] 구급대원` 1.0MB, `[AED 공통] 구급대원` 515KB
- 태그 체계: 분류 `space` · `character` · `object` · `twin`, 세부 `npc` · `player` · `animation` · `parts`
- 50MB를 넘는 파일도 등록돼 있다(최대 `ConvenienceStore.glb` 173.8MB). 업로드 상한은 개발팀 확인이 필요하다.

## 실행 환경과 기술 구성

사용자 맥에서 Python CLI로 실행한다. 목록은 Google Drive API, 등록은 AssetHub API로 처리하고, 파일 본문은 Drive API로 내려받는다.

| 구분 | 선택 | 이유 |
|---|---|---|
| 언어 | Python 3.11+ | Drive·HTTP·GLB 라이브러리가 충분함 |
| 드라이브 목록 | Google Drive API v3 (`files.list`, `drives.list`) | `md5Checksum` · `size` · `parents` · `driveId`를 한 번에 받아 내려받기 없이 중복 판정 가능 |
| 파일 본문 | Drive API `files.get?alt=media` (대안: 맥 동기화 경로) | 동기화 경로는 클라우드 전용 파일을 열 때마다 내려받기가 생김 |
| 등록 | AssetHub REST API (`https://assethub-api.bigbenett.com`) | 브라우저 자동화의 10MB 제한·속도 문제가 없음 |
| GLB 분석 | `pygltflib` 또는 `trimesh` | 삼각형 수·메시 수·애니메이션 수를 설명에 기록 |
| 원장 | Google Sheets API + 로컬 SQLite | 팀 공유는 시트, 재실행 판단은 SQLite |
| 진행 표시 | `rich` | 배치 진행률과 오류 요약 |

### 인증

- Google: OAuth 데스크톱 클라이언트로 사용자 동의를 받는다(범위 `drive.readonly`, `spreadsheets`). 토큰 파일은 로컬에만 두고 저장소에 커밋하지 않는다.
- AssetHub: 웹은 쿠키 세션을 쓴다. 스크립트용 API 토큰 발급 방식은 개발팀 확인이 필요하다(미결 사항). 브라우저 쿠키를 복사해 쓰지 않는다.
- 비밀값은 환경변수(`ASSETHUB_TOKEN` 등)나 `.env`로만 받는다.

### 코드 구조(권장)

```
assethub-importer/
  config.yaml        # 제외 규칙, 이름 규칙, 동시성, 크기 상한
  mapping.csv        # 공유 드라이브 → 허브 프로젝트 (사용자 확인)
  importer/
    drive.py         # 목록, 폴더 경로, 다운로드
    hub.py           # AssetHub API 클라이언트
    rules.py         # 대상 선정, 중복·수정본·변형 판정
    naming.py        # 이름, 태그, 설명 생성
    glbinfo.py       # GLB 통계
    ledger.py        # SQLite 상태 + 구글 시트 동기화
  cli.py
```

### CLI

| 명령 | 하는 일 | 허브에 쓰기 |
|---|---|---|
| `inventory` | 공유 드라이브 GLB 전체 목록 → `inventory.csv` | 없음 |
| `hub-snapshot` | 허브 프로젝트·에셋·원본 파일명/크기 → `hub_assets.csv` | 없음 |
| `plan` | 매핑·중복·이름 결정 → `plan.csv` + 프로젝트별 요약 | 없음 |
| `apply --project <이름> --limit N` | 프로젝트 생성, 업로드, 원장 갱신 | 있음 (`--yes` 없이 실행하면 할 일만 출력) |
| `verify` | 원장과 허브 대조 | 없음 |

## AssetHub API

조회 API는 웹앱 동작에서 확인했지만, 생성·업로드 API는 아직 확인하지 못했다. 개발 착수 전에 개발팀에서 명세를 받거나, 웹에서 한 건을 수동 등록하면서 브라우저 개발자 도구의 Network 탭으로 요청을 기록해야 한다.

### 확인된 엔드포인트

기준 URL `https://assethub-api.bigbenett.com`, 웹은 쿠키 인증.

| 메서드·경로 | 응답·비고 |
|---|---|
| `GET /projects?status=all` | 프로젝트 목록 (보관 포함) |
| `GET /tags` | 태그 목록 |
| `GET /assets?page=N` | `{items, total, page, pageSize}`, pageSize 25 고정 (`pageSize=100`은 400 오류) |
| `GET /assets/{id}` | `description`, `project{id,name,status}`, `tags[]`, `currentVersion{id, version, comment, totalSizeBytes, files[{id, fileName, format, sizeBytes}]}`, `nextVersion{minor, major}` |
| `GET /versions/{versionId}/thumbnail/{file}.webp` | 썸네일 이미지 |

목록 항목 필드: `id`, `name`, `project{id,name,status}`, `tags[]`, `version`, `sizeBytes`, `formats[]`, `hasGlb`, `thumbnailUrl`, `updatedBy`, `updatedAt`, `status`, `trashedAt`.

### 웹 등록 화면(`/upload`)의 입력 항목

- GLB 파일: 한 번에 최대 10개, 권장 50MB 이하
- 프로젝트: 필수, 하나만 선택 (에셋 1개 = 프로젝트 1개)
- 이름, 설명(선택), 태그(선택, 자유 입력), 변경 메모(기본값 `최초 등록`)
- 버전은 `1.0`으로 시작하고, 수정본은 `1.1`(minor) 또는 `2.0`(major)으로 올린다

### 개발팀 확인 필요

- 스크립트용 인증 방식 (API 토큰, 서비스 계정 등)
- 프로젝트 생성 API (웹의 `새 프로젝트` 버튼)
- 에셋 생성·파일 업로드 API: multipart인지 사전 서명 URL(presigned)인지, 파일 크기 상한
- 썸네일 생성 주체: 썸네일 파일명이 클라이언트 타임스탬프 형식이라 웹에서 렌더링해 올리는 것으로 보인다. 그렇다면 스크립트도 렌더링해서 함께 올려야 한다
- 호출 속도 제한과 동시 업로드 허용 수
- 기존 에셋에 새 버전을 올리는 API

## 처리 흐름

허브에 쓰는 일은 사용자 확인 뒤 apply 단계에서만 일어난다. 1~3단계와 6단계는 읽기만 한다.

```
Google 공유 드라이브 ──▶ 1. inventory      공유 드라이브 GLB 목록·경로·md5 → inventory.csv
AssetHub API ─────────▶ 2. hub-snapshot   허브 프로젝트·에셋·원본 파일명·크기 → hub_assets.csv
                         3. plan           선정·중복·매핑·이름 규칙 적용 → plan.csv · 프로젝트별 요약
                         4. 사용자 확인     mapping.csv와 요약을 검토하고 승인 (파일럿은 드라이브 1개 · 20개 이하)
AssetHub API ◀──(쓰기)── 5. apply          프로젝트 생성 → 업로드 → 결과 확인, 실패는 3회 재시도 후 failed로 기록
                         6. verify         원장과 허브를 대조, 불일치 0건이면 완료 (불일치·실패는 apply로 다시 처리)
원장(구글 시트) ◀─────── apply 결과 기록 / verify 대조 (SQLite 상태와 동기화, 파일 1개 = 1행)
```

읽기 단계의 결과를 사람이 확인한 뒤에만 허브에 쓰고, 결과는 원장에 남겨 재실행 때 건너뛴다.

1. **inventory**: Drive API `files.list`를 `corpora=allDrives`, `includeItemsFromAllDrives=true`, `supportsAllDrives=true`로 호출한다. 조건은 `(mimeType='model/gltf-binary' or name contains '.glb') and trashed=false`, 필드는 `id, name, size, md5Checksum, modifiedTime, parents, driveId`이고, 결과는 확장자로 한 번 더 거른다. 드라이브 이름은 `drives.list`로 받고, 폴더 경로는 드라이브별 폴더 목록을 한 번에 받아 메모리에서 조립한다. 파일마다 부모 폴더를 하나씩 거슬러 올라가며 조회하지 않는다(이번 조사에서 가장 느렸던 방식).
2. **hub-snapshot**: `GET /assets?page=N`으로 전체 목록을 받고, `GET /assets/{id}`를 동시 요청 8개 정도로 돌려 원본 파일명·크기를 채운다.
3. **plan**: 규칙 섹션대로 파일마다 `decision`과 이름·태그·설명을 정하고, `plan.csv`와 프로젝트별 요약(등록·건너뜀 건수, 새로 만들 프로젝트)을 출력한다.
4. **사용자 확인**: 요약과 `mapping.csv`를 보고 승인한다. 승인 전에는 허브에 아무것도 쓰지 않는다.
5. **apply**: 프로젝트 단위로 진행한다. 없는 프로젝트 생성 → 파일 내려받기 → GLB 통계 계산 → 업로드 → `GET /assets/{id}`로 확인 → 원장 갱신 순서이고, `--project`와 `--limit`으로 범위를 좁힌다.
6. **verify**: 원장의 `uploaded` 행과 허브 에셋을 파일명·크기로 대조하고 불일치를 보고한다.

## 규칙

대상 선정 → 중복 판정 → 프로젝트 매핑 → 이름·태그·설명 순서로 적용하고, 파일마다 판정 결과와 이유를 원장에 남긴다. 키워드와 상한값은 모두 `config.yaml`에서 바꿀 수 있게 한다.

### 1. 대상 선정

- 공유 드라이브의 `.glb` 파일(`mimeType = model/gltf-binary` 또는 이름이 `.glb`로 끝남), 휴지통 제외
- 경로에 다음 폴더명이 있으면 제외: `_이전*`, `이전`, `old`, `backup`, `bak`, `archive`, `temp`, `tmp`
- 허브에 이미 있는 파일: 원본 파일명과 크기가 모두 같으면 `skip-existing`
- 업로드 상한(개발팀 확인 전 기본 200MB)을 넘으면 `too-large`로 원장에만 기록

### 2. 중복·수정본·변형 판정

| 경우 | 판정 기준 | 처리 |
|---|---|---|
| 완전 중복 | `md5Checksum`이 같음 | 1개만 등록, 나머지 `skip-duplicate` |
| 수정본 | 같은 콘텐츠 폴더 안에서 이름이 같고 내용이 다름, 또는 `_v1.2` → `_v1.4`처럼 버전 표기만 다름 | 가장 최근 수정본 1개 등록, 나머지 `skip-older` |
| 변형 | 접미사(`_dressed`, `_lite`, `_anim`, `_asbuilt`, `_raw`)나 용도 폴더(`원본`, `Unity`, `realistic`)가 다름 | 각각 별도 에셋, 이름에 변형 표기 |
| 여러 드라이브의 같은 파일 | `md5Checksum`이 같고 드라이브가 다름 | 가장 최근 파일이 있는 드라이브의 프로젝트에 1개 등록, 나머지 드라이브 이름은 태그 |

대표본 선택 순서: ① 제외 키워드가 없는 경로 ② 가장 최근 `modifiedTime` ③ 경로가 짧은 것.

### 3. 프로젝트 매핑

- 최상위 공유 드라이브 1개 = 허브 프로젝트 1개. 등록할 GLB가 1개 이상 있는 드라이브만 만든다.
- `mapping.csv`에 드라이브 → 허브 프로젝트를 적는다. 같은 과제의 기존 프로젝트가 있으면 그 이름을, 없으면 드라이브 이름 그대로(앞뒤 공백 제거) 새로 만든다.
- 매핑 초안 (사용자 확인 필요):

| 공유 드라이브 | 허브 프로젝트 |
|---|---|
| PJ_2026 광진 아메리카 | [광진 아메리카] Smart Factory 구축 (기존) |
| PJ_2026 국립중앙의료원 지속적 신대체요법(CRRT) 시뮬레이션 실감형 콘텐츠 개발 | [국립중앙의료원] CRRT 시뮬레이션 (기존) |
| PJ_2026 실감형콘텐츠 수정 및 변환_KERIS | [실감형] 실감형 콘텐츠 수정 및 변환 (기존) |
| PJ_2026년 장애학생 정보화 교육자료 개발 | [특수교육원] 장애학생 정보화 교육자료 개발 (기존) |
| PJ_신성이엔지 | [디지털트윈] 신성이엔지 (기존) |
| TF_LangoSpace | [LangoSpace] (기존) |
| PJ_2026 가상실험실습 학습콘텐츠 제작 5종_방송대 | [방송대] 가상실험학습 학습 콘텐츠 (기존) |
| PP_2026 가상실험실습 학습콘텐츠 공유 플랫폼 구축 2차_방송대 또는 PP_2026 가상실험실습 학습콘텐츠 제작(6종)_9월과제 | 2026 방송대 하반기 제안 (기존, 어느 드라이브인지 확인 필요) |
| 그 밖의 드라이브 | 드라이브 이름으로 새 프로젝트 |

### 4. 이름·태그·설명

- 이름: `분류_대상_변형_v번호`
  - 분류: `char`(캐릭터) · `obj`(사물) · `space`(공간) · `anim`(동작 클립) · `parts`(부품) · `twin`(설비 트윈)
  - 대상: 파일명에서 확장자와 버전 표기를 뺀 값 (예: `barista`)
  - 변형: 접미사나 용도 폴더(`dressed`, `lite`, `unity`, `raw` 등), 없으면 생략
  - 번호: 대표본이 몇 번째 수정본인지 (수정본이 하나면 `v1`)
  - 예: `char_barista_v2`, `char_patient2_dressed_v1`, `twin_fastening_asbuilt_v1`
- 분류 추정: 폴더·파일명 키워드로 정한다. `캐릭터` · `character` · `npc` · `player` · `hair` · `body` → `char`, `clips` · `anim` · `동작` → `anim`, `room` · `scene` · `씬` · `map` · `ground` · `city` → `space`, `asbuilt` · `설비` · `factory` → `twin`, 나머지 `obj`. 애매하면 `obj`로 두고 원장에 표시한다.
- 태그: 허브 분류 태그(`space` · `character` · `object` · `twin`) + 추정 가능한 세부 태그(`npc` · `player` · `animation` · `parts`) + 콘텐츠 폴더 이름(예: `AED_실감형콘텐츠_S2`) + 추적용 `drive-import-2026-10`
- 설명 템플릿: `{공유 드라이브} › {하위 경로}에서 가져온 GLB. 원본 파일 {파일명}, {크기}MB, 수정 {날짜}. 삼각형 {n}개, 애니메이션 {k}개. Drive ID {fileId}`
- 변경 메모: `최초 등록 (드라이브 일괄 등록)`

## 원장·재실행·오류 처리·되돌리기

원장은 Drive 파일 1개당 한 행이다. 같은 명령을 다시 실행해도 이미 등록된 파일은 건너뛰고, 중간에 멈춰도 이어서 실행할 수 있어야 한다.

### 원장 열

구글 시트 `AssetHub 등록 원장`, 로컬 SQLite와 같은 내용.

| 열 | 내용 |
|---|---|
| `drive_file_id` | Drive 파일 ID (기본 키) |
| `shared_drive` · `path` | 최상위 공유 드라이브 이름, 드라이브 안 경로 |
| `file_name` · `size_bytes` · `md5` · `modified_time` | 원본 정보 |
| `group_id` | 같은 모델 묶음 ID (중복·수정본·변형 판정) |
| `decision` | `register` · `skip-existing` · `skip-duplicate` · `skip-older` · `skip-excluded` · `too-large` |
| `reason` | 판정 이유 한 줄 |
| `hub_project` · `asset_name` · `tags` | 등록할 값 |
| `hub_asset_id` · `hub_version` | 등록 결과 |
| `status` | `planned` · `uploaded` · `verified` · `failed` |
| `error` · `updated_at` | 실패 사유, 갱신 시각 |

### 재실행과 오류

- `status`가 `uploaded`나 `verified`인 행은 다시 올리지 않는다.
- 실패하면 지수 백오프로 3회 재시도하고, 그래도 안 되면 `failed`로 남긴 뒤 다음 파일로 넘어간다.
- 업로드 직후 `GET /assets/{id}`로 파일·크기를 다시 확인해야 `uploaded`로 바꾼다.
- 원장의 구글 시트 동기화는 배치(예: 20건)마다 하고, 기준 상태는 로컬 SQLite에 둔다.

### 되돌리기

- 이번 일괄 등록분에는 모두 `drive-import-2026-10` 태그를 단다. 문제가 생기면 이 태그와 원장의 `hub_asset_id`로 대상만 골라낼 수 있다.
- 스크립트는 허브의 에셋이나 프로젝트를 자동으로 삭제하지 않는다. 삭제가 필요하면 목록을 만들어 사람이 확인한 뒤 처리한다.

## 완료 기준과 파일럿 테스트

공유 드라이브 1개로 파일럿을 돌려 아래 기준을 모두 통과한 뒤 전체를 실행한다.

1. `plan` 요약의 프로젝트별 등록·건너뜀 건수가 원장 합계와 일치한다.
2. 파일럿은 공유 드라이브 1개, 20개 이하로 `apply`를 실행하고, 허브 화면에서 이름·태그·설명·썸네일·3D 뷰어를 사람이 확인한다.
3. 같은 `apply`를 다시 실행하면 새로 만들어지는 에셋이 0개다.
4. 허브에 이미 있던 290개와 겹치는 파일은 하나도 다시 올라가지 않는다.
5. 등록된 모든 에셋이 설명의 Drive ID와 원장의 `hub_asset_id`로 원본 파일까지 추적된다.
6. 실패 건은 원장에 사유가 남고, 재실행으로 해결되거나 수동 처리 목록에 오른다.
7. 전체 실행 후 `verify`가 원장과 허브 사이 불일치 0건을 보고한다.

## 미결 사항

개발팀 확인 4건이 풀려야 `apply`를 완성할 수 있다. 그 전에도 `inventory` · `hub-snapshot` · `plan`은 만들어 돌릴 수 있다.

- [ ] 개발팀: AssetHub 스크립트용 인증 방식 (API 토큰 등)
- [ ] 개발팀: 프로젝트 생성·에셋 생성·파일 업로드·새 버전 API 명세와 파일 크기 상한
- [ ] 개발팀: 썸네일을 서버가 만드는지, 클라이언트가 만들어 올려야 하는지
- [ ] 개발팀: 호출 속도 제한과 동시 업로드 허용 수
- [ ] 사용자: `mapping.csv` 초안 확인, 특히 방송대 관련 드라이브와 기존 프로젝트의 대응
- [ ] 사용자: 2025년 파일(1,764개)도 이번에 등록할지, 2026년 과제부터 할지
- [ ] 사용자: 이름에 `v번호`를 계속 붙일지, 허브 자체 버전(1.0 → 1.1)만 쓸지
- [ ] 사용자: 제외 폴더 키워드 목록 보완
- [ ] 사용자·개발팀: 50MB 이상 파일(조사분 36개) 처리 방식

## Claude Code 작업 지침

1. 먼저 `inventory`와 `hub-snapshot`만 구현해서 읽기 전용으로 돌려 보고, 결과 건수를 보고한다.
2. 다음으로 `plan`을 구현해서 SPEC의 규칙(대상 선정, 중복·수정본·변형 판정, 프로젝트 매핑, 이름·태그·설명)대로 `plan.csv`와 프로젝트별 요약을 만든다. 이 단계까지는 허브에 아무것도 쓰지 않는다.
3. AssetHub 생성·업로드 API는 SPEC의 '개발팀 확인 필요' 항목이 채워질 때까지 인터페이스만 만들어 두고, 명세를 받으면 `apply`와 `verify`를 완성한다.
4. 허브에 쓰는 명령은 `--yes` 없이 실행하면 할 일만 출력한다.
5. 비밀값은 환경변수로만 받고, 토큰·인증 파일은 `.gitignore`에 넣는다.
6. 첫 실제 등록은 공유 드라이브 1개, 20개 이하로 하고, 사용자가 허브 화면을 확인한 뒤에 전체를 실행한다.
