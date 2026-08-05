# 새 글 쓰는 법

이 디렉토리(`posts-source/`)에서 글을 직접 쓰고 편집합니다. 전체 디자인 원칙(왜
무채색인지, 컬러 토큰 등)은 [`docs/HANDOFF.md`](../docs/HANDOFF.md)가 기준 문서고, 이
파일은 "실제로 글 하나 쓸 때 뭘 어떻게 적으면 되는지"에 대한 실용 참고서입니다.

## 1. 새 글 만들기

1. `posts-source/<slug>.md` 파일을 새로 만듭니다 (slug는 영문 소문자+하이픈, URL에 그대로 씀).
2. 아래 frontmatter + 본문 형식으로 작성합니다.
3. 저장 후 동기화:
   ```bash
   python3 scripts/sync-post.py posts-source/<slug>.md
   ```
4. `wrangler dev`로 `http://localhost:8787/posts/<slug>`에서 바로 확인.
5. 진짜 배포된 사이트에 반영하려면 `--remote` 플래그 추가 (`wrangler deploy`로 Worker
   자체를 먼저 배포한 뒤에나 의미 있음 — 아직 도메인/배포 전이면 로컬에서만 확인).

## 2. Frontmatter

```markdown
---
slug: my-post-slug
title: 글 제목
excerpt: 목록/RSS에 보일 한두 문장 요약
tags: [transformer, attention]
status: draft
source_ref: https://github.com/chjnett/tech_Blog/tree/main/posts-assets/my-post-slug   # 선택
---
(본문 마크다운 — title은 페이지 템플릿이 따로 렌더링하므로 본문에 `# 제목`을 또 쓰지 않는다)
```

- `status`: `draft`면 홈/목록/RSS/개별 페이지 어디에도 안 보임(존재 자체가 노출 안 됨).
  `published`이어야 실제로 보임. **draft → published 전환은 사람이 직접 이 필드를 바꾸는
  것 자체가 승인 행위** — 자동으로 published가 되는 코드 경로는 절대 만들지 않는다
  (`CLAUDE.md` 비타협 규칙).
- `source_ref`: 첨부 코드/파일이 있으면 `posts-assets/<slug>/` 아래에 실제 파일을 넣고,
  그 GitHub 폴더 링크를 적는다. 글 상단/하단에 "전체 코드 보기" 버튼이 자동으로 뜬다.

## 3. 콘텐츠 컴포넌트

본문 밖 모든 곳은 **무채색**이다 — 색은 오직 code 블록의 신택스 하이라이팅에서만
쓴다. 강조는 굵기 · 테두리 · 흑백 반전으로 표현한다.

### 3.1 코드 블록

일반 fenced code block, 언어 태그 필수. 자동으로 신택스 하이라이팅되고, 길면
자동으로 접힌다.

````markdown
```python
def multiply(a, b):
    return a * b
```
````

지원 언어: `python`, `javascript`, `typescript`, `bash`, `json`. 새 언어가 필요하면
`worker/src/highlight.ts`의 `SUPPORTED_LANGUAGES`에 추가해야 함 (코드 작업 필요, 글
쓰는 것만으로는 안 됨).

### 3.2 터미널 블록

실행 결과를 보여줄 때. `$`로 시작하는 줄은 명령어, 나머지는 출력으로 자동 구분됨.

````markdown
```terminal
$ python train.py --epochs 10
epoch 1/10 | loss 4.21
```
````

### 3.3 Figure 블록 (개념 다이어그램)

JSON을 쓰면 자동으로 SVG로 배치해서 그려준다. 4가지 타입이 있다.

**flow** — 좌→우 흐름, fan-in/fan-out 자동 처리 (Kahn's algorithm 기반 레이어드 배치):

````markdown
```figure
{"type":"flow","caption":"설명","nodes":[{"id":"a","label":"Input A","note":"보조설명"},{"id":"b","label":"Input B"},{"id":"c","label":"Output","emphasis":true}],"edges":[{"from":"a","to":"c","label":"merge"},{"from":"b","to":"c"}]}
```
````

**compare** — 나란히 비교, 순서대로 한 줄:

```json
{"type":"compare","nodes":[{"id":"x","label":"방식 A"},{"id":"y","label":"방식 B"}]}
```

**stack** — 위→아래 (트랜스포머 블록 구조 등):

```json
{"type":"stack","nodes":[{"id":"l1","label":"Layer 1"},{"id":"l2","label":"Layer 2"}]}
```

**groups** — Query/KV 헤드 공유처럼 "그룹별로 여러 개가 하나를 공유하는" 비교 (MHA/GQA/MQA류):

```json
{
  "type": "groups",
  "caption": "설명",
  "groups": [
    { "label": "Multi-head (MHA)", "note": "KV heads: 4 (one each)", "queryCount": 4, "kvCount": 4 },
    { "label": "Grouped-query (GQA)", "note": "KV heads: 2 (shared in groups)", "queryCount": 4, "kvCount": 2 },
    { "label": "Multi-query (MQA)", "note": "KV heads: 1 (shared by all)", "queryCount": 4, "kvCount": 1 }
  ]
}
```
흰 사각형 = query 헤드, 검은 사각형 = KV 헤드. 각 그룹의 query들이 균등하게 KV에
연결선으로 묶인다. 색(원래 이런 다이어그램은 보통 파랑/초록) 대신 흑백 반전으로
구분한다는 점이 이 블로그 디자인 원칙의 핵심.

공통 규칙 (flow/compare/stack): 노드에 `emphasis: true`를 주면 검정 채우기+흰 글씨로
강조된다. `note`는 보조 설명. `edges`의 `label`은 화살표 중간에 표시.

**JSON이 깨지면** 예외를 던지지 않고 원문이 그대로 이스케이프된 코드블록으로
표시된다 — 발행이 막히지 않는다. 다만 그러면 다이어그램 대신 JSON 텍스트가 보이니,
`npx wrangler d1 execute ...`나 브라우저에서 한 번 확인하고 나서 published로
바꾸는 걸 권장.

### 3.4 표

일반 마크다운 표 문법 그대로 쓰면 된다. 숫자 컬럼은 `---:`로 오른쪽 정렬하면 보기
좋다 (`tabular-nums`로 자릿수 맞춰 렌더링됨).

```markdown
| 구성 | 값 |
|---|---:|
| A | 1.00 GB |
```

## 4. 체크리스트 (글 하나 쓸 때)

- [ ] `posts-source/<slug>.md` 작성, frontmatter 채움
- [ ] `python3 scripts/sync-post.py posts-source/<slug>.md`로 로컬 D1에 반영
- [ ] `wrangler dev`로 실제로 렌더링 확인 (특히 figure/표 — JSON 오타는 조용히
      코드블록으로 폴백되니 눈으로 봐야 함)
- [ ] 첨부 코드가 있으면 `posts-assets/<slug>/`에 실제 파일 커밋 + frontmatter의
      `source_ref`에 링크
- [ ] 확인 끝나면 frontmatter `status: published`로 바꾸고 다시 sync
