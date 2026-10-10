# CLAUDE.md

## 프로젝트
구글 공유 드라이브의 GLB를 AssetHub에 일괄 등록하는 Python CLI. 요구사항의 기준 문서는 `docs/SPEC.md`이며, 규칙이나 동작이 애매하면 SPEC을 따른다.

## 구조
- `assethub-importer/` — CLI 본체 (`cli.py`, `importer/` 모듈, `config.yaml`, `mapping.csv`)
- `docs/SPEC.md` — 요구사항, 규칙, 원장 스키마, 완료 기준

## 반드시 지킬 것
- 허브에 쓰는 명령(`apply`)은 `--yes` 없이 실행하면 할 일만 출력한다. `inventory`·`hub-snapshot`·`plan`·`verify`는 허브에 쓰지 않는다.
- 스크립트는 허브의 에셋·프로젝트를 삭제하지 않는다.
- 비밀값은 환경변수나 `.env`로만 받는다. 토큰·OAuth 파일·원장 DB·출력 CSV는 커밋하지 않는다(`.gitignore` 참고).
- 키워드와 상한값은 코드에 하드코딩하지 않고 `config.yaml`에서 읽는다.
- AssetHub 생성·업로드 API는 SPEC의 '개발팀 확인 필요' 항목이 채워질 때까지 인터페이스만 둔다. 추측으로 엔드포인트를 만들지 않는다.

## 개발
```bash
cd assethub-importer
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```
