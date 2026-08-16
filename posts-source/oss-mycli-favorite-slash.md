---
slug: oss-mycli-favorite-slash
title: 문서의 `/fs`가 실제 명령(`\fs`)과 다른 버그 — mycli
excerpt: MySQL 클라이언트 mycli의 즐겨찾기 명령이 백슬래시(\fs)로 등록돼 있는데 README·help는 슬래시(/fs)로 보여, 문서를 따라가면 SQL 문법 오류가 났던 것을 고친 기여 기록.
tags: [oss, mycli, docs, python, mysql]
status: published
source_ref: https://github.com/dbcli/mycli/pull/2142
---

문서가 실제 동작과 한 글자 틀리면, 그 한 글자가 사용자를 길로 데려간다. mycli의 즐겨찾기 명령은 `\fs`(백슬래시)로 등록돼 있는데, README와 help는 `/fs`(슬래시)로 표시돼 있었다.

```figure
{"type":"compare","caption":"문서 vs 실제 명령","nodes":[{"id":"doc","label":"문서/help","note":"/fs /f /fd (슬래시)","emphasis":true},{"id":"real","label":"실제 등록","note":"\\fs \\f \\fd (백슬래시)"}],"edges":[{"from":"doc","to":"real","label":"불일치"}]}
```

## 문제

mycli의 `iocommands.py`에 즐겨찾기 명령이 백슬래시(`"\fs"`)로 등록되어 있음에도, README와 `\fs`/`\f`/`\fd`의 help 텍스트는 **슬래시(`/fs`)** 로 표시했다. 문서대로 `/fs alias query`를 입력하면 SQL 문법 오류가 났다.

## 고친 것

- `README.md`: `/fs` → `\fs`, `/f` → `\f`
- `mycli/packages/special/favoritequeries.py`: usage 예시를 슬래시 → 백슬래시로
- `changelog.md`: Documentation 항목 추가

실제 등록(`iocommands.py`의 `"\\f"`, `"\\fs"`, `"\\fd"`)과 대조해 일치시켰다.

## 교훈

- **CLI의 특수 접두어(백슬래시/슬래시) 하나는 소문자별 의미가 크다.** 문서와 실제 등록을 대조하는 리뷰로 잡아낼 수 있는 아주 전형적인 불일치.
- 문서 버그도 "기능 버그"만큼 사용자에게 실질적 — 문서를 따라간 사용자가 그대로 실패하므로.

[전체 PR 보기 — dbcli/mycli#2142](https://github.com/dbcli/mycli/pull/2142)
