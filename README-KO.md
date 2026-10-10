![Motion Lab - motion and design for people and AI](docs/assets/og-repository.jpg)

# Motion Lab

[English](README.md) · **한국어**

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square)
![SQLite FTS5](https://img.shields.io/badge/SQLite-FTS5-003B57?style=flat-square)
![MCP stdio](https://img.shields.io/badge/MCP-stdio-222222?style=flat-square)
![KO / EN](https://img.shields.io/badge/UI-KO%20%2F%20EN-555555?style=flat-square)

사람과 AI 도구가 함께 활용하는 모션 코드, 디자인 에셋, 검토 레퍼런스 라이브러리입니다. 로컬 미리보기를 탐색하고 출처와 라이선스가 포함된 코드, 색상, 이미지를 가져올 수 있습니다.

<!-- motionlab:catalog-summary:start -->
**저장 에셋 11,603개 + 검토 레퍼런스 283개**, 등록된 출처 178개.
아래 수량은 2026-10-11 카탈로그 기준입니다. 현재 수량은 `python -m motionlab stats`로 확인하세요.

| 자료 모음 | 수량 | 내용 |
| --- | ---: | --- |
| 모션 | 3,417 | 애니메이션, 전환, 타이포그래피, 로더, 인터랙션 효과 |
| 디자인 | 8,186 | 패턴, 형상, 일러스트, 팔레트, 그라디언트, 소재 이미지 |
| 레퍼런스 | 283 | 검토한 예제, 라이브러리, 도구, 사례 연구, 학습 자료 |
<!-- motionlab:catalog-summary:end -->

[사이트](https://jtech-co.github.io/Motion-Lab/) · [GitHub 저장소](https://github.com/JTech-CO/Motion-Lab)

## 빠른 시작

Git, Python 3.10 이상, FTS5를 지원하는 SQLite가 필요합니다. 클론한 뒤 빌드를 실행해 전체 카탈로그를 생성하세요. API 키는 필요하지 않습니다.

```sh
git clone https://github.com/JTech-CO/Motion-Lab.git
cd Motion-Lab
python scripts/build.py
python -m motionlab serve --port 8787
```

[소개페이지](http://127.0.0.1:8787/) 또는 [라이브러리](http://127.0.0.1:8787/library.html)를 엽니다. 한국어/영어 전환, 필터, 페이지당 20/50/100개 보기를 지원합니다. 로컬 서버는 루프백 주소에서만 접속할 수 있습니다.

## 자료 구성

![Motion, Design, References 자료 비율](docs/assets/catalog-composition.svg)

`python scripts/build.py`로 카탈로그를 빌드하면 그래프와 두 README의 수량 요약이 함께 자동 갱신됩니다. 보존된 원본 변형은 별도 항목으로 중복 계산하지 않습니다.

## AI 도구 연결

[Motion Lab SKILL](skills/motion-lab/SKILL.md)과 [CLI, 로컬 MCP, HTTP 및 JSON 가이드](docs/interfaces.md)를 활용하세요. 사이트의 **AI 연결** 창에도 설정 예시가 있습니다. 로컬 API와 MCP는 읽기 전용이며, 정적 사이트는 원격 MCP 엔드포인트를 제공하지 않습니다.

## 재사용과 출처

라이선스는 **에셋별, 원본 변형별**로 적용되며, 필요한 출처 표시와 고지를 유지해야 합니다. 레퍼런스 미리보기에는 별도 조건이 적용되며 참조 작품의 사용 권한을 부여하지 않습니다. 출처 검토는 수집 코드의 실행 안전성을 보증하지 않습니다.

[수집, 재빌드 및 패키징](docs/collection.md) · [분류, 미리보기 및 권리](docs/asset-analysis.md)
