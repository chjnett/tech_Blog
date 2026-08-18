---
slug: oss-llama-index-mcp-cohere-dispatcher
title: llama-index 통합 패키지에서 잡은 흩어진 버그 3가지
excerpt: Bedrock Cohere 임베딩 추가 파라미터 누락, mcp 2.x 스트리밍 튜플 변화, Dispatcher 가변 기본 인자 — llama-index 통합에서 잡은 버그 3건 정리.
tags: [oss, ai-llm, backend]
status: published
source_ref: https://github.com/run-llama/llama_index
---

llama-index는 "통합 패키지"가 많아서, 각각이 독립 SDK 버전과 맞물려 **버전 이동 시 깨지기 쉽다.** 이번에 세 개의 통합에서 버그를 잡았다.

```figure
{"type":"compare","caption":"3개 통합 버그","nodes":[{"id":"bed","label":"Bedrock Cohere","note":"additional_kwargs 누락"},{"id":"mcp","label":"MCP tools","note":"mcp 2.x 2-tuple"},{"id":"disp","label":"Dispatcher","note":"가변 기본 인자"}],"edges":[{"from":"bed","to":"disp"}]}
```

## #22723 — Bedrock Cohere가 additional_kwargs를 버림
`BedrockEmbedding._get_request_body`는 Amazon/Titan 모델엔 `self.additional_kwargs`(`dimensions`, `normalize`)를 읽지만, **Cohere 모델엔 조용히 놓쳤다.** 그 결과 `cohere.embed-v4:0`에 `output_dimension`을 못 넘겨 항상 기본 차원을 반환했다. Cohere 요청 body에 `additional_kwargs`를 병합하도록 고쳤다.

## #22724 — mcp 2.x의 스트리밍 2-tuple
`llama-index-tools-mcp` 0.5.0이 mcp 2.x SDK로 갈아탔는데 `client.py`는 여전히 `streamable_http_client(...)`를 **3-tuple**로 풀었다. mcp 2.0.0은 컨텍스트 매니저가 **2-tuple** `(read, write)`를 주므로, 모든 스트리밍 HTTP 세션이 언패킹 ValueError로 죽었다. 2-tuple로 맞췄다.

## #22725 — Dispatcher의 가변 기본 인자
`Dispatcher.__init__`가 `event_handlers=[]`, `span_handlers=[]`라는 파이썬 `B006` 푸트건을 썼다. 인스트루멘테이션에서 이벤트/스팬 핸들러는 **디스패처 인스턴스마다 격리**돼야 하므로 특히 위험하다. 기본값을 `None`으로 바꾸고 body에서 새 리스트를 만들었다.

## 교훈

- **통합 패키지의 "백엔드별 분기"는 한 모델군만 빼먹기 쉽다** (Cohere). 공통 파라미터 전달을 한 경로로 묶자.
- **의존성 SDK가 반환 타입/튜플을 버전 간 바꾸면** 이전 코드가 조용히 깨진다. 마이그레이션 후 **튜플 길이·시그니처**를 회귀 테스트로 고정하자.
- **가변 기본 인자**는 모든 파이썬 코드의 금기. 상태가 인스턴스 간 공유되면 격리가 깨진다.

[전체 PR 보기 — run-llama/llama_index](https://github.com/run-llama/llama_index)
