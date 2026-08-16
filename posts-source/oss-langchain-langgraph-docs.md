---
slug: oss-langchain-langgraph-docs
title: deprecated initialize_agent를 LangGraph로 교체하는 문서 기여 (langchain)
excerpt: langchain 문서 곳곳에 남은 deprecated API initialize_agent를, 권장 패턴인 create_react_agent 등 LangGraph 코드로 교체해 최신 권장 사항을 반영한 문서 기여 기록.
tags: [oss, langchain, llm, langgraph, docs]
status: published
source_ref: https://github.com/langchain-ai/langchain/pull/39608
---

프레임워크가 발전하면서 예전 코드 예제는 "동작은 하지만 권장 방식이 아니"게 된다. langchain의 `initialize_agent`는 deprecated 됐고, 문서의 해당 예제를 최신 권장(LangGraph)로 교체하는 기여를 했다.

```figure
{"type":"compare","caption":"deprecated → LangGraph 권장 패턴","nodes":[{"id":"old","label":"initialize_agent","note":"deprecated"},{"id":"new","label":"create_react_agent 외","note":"LangGraph 권장 패턴","emphasis":true}],"edges":[{"from":"old","to":"new","label":"문서 교체"}]}
```

## 무슨 기여였나

langchain 문서의 `initialize_agent` 사용 예제를, 권장되는 LangGraph 패턴(예: `create_react_agent`)으로 교체했다. 이 기여는 특정 이슈(`#29277`)를 해결했다.

```python
# before (deprecated)
from langchain.agents import initialize_agent
agent = initialize_agent(...)

# after (LangGraph 권장)
from langchain.agents import create_react_agent
agent = create_react_agent(llm, tools)
```

## 왜 필요한지

- **문서는 라이브러리의 "얼굴"** — deprecated API가 예제로 남아 있으면 새 사용자가 그걸 배워서 유지보수 비용이 커진다.
- 프레임워크 마이그레이션 시 **문서를 최신 권장 사항으로 동기화**하는 게 사용자 온보딩의 핵심.

## 교훈

- 코드 변경만큼 **예제/문서의 deprecation 동기화**도 오픈소스 품질의 일부다.
- 프레임워크를 학습하는 관점에서도, "이 API 왜 deprecated?"를 문서 PR로 푸는 건 아주 좋은 기여 진입점이다.

[전체 PR 보기 — langchain-ai/langchain#39608](https://github.com/langchain-ai/langchain/pull/39608)
