---
slug: oss-litellm-langfuse-redis-docs
title: litellm에서 잡은 통합·캐시·문서 버그 3건
excerpt: litellm의 langfuse OTel rerank Output 누락, Redis cluster 종료 시 None 역참조 크래시, 문서에 없는 함수 참조(litellm-docs)까지 — 프록시 계층에서 잡은 버그 3건 정리.
tags: [oss, ai-llm, backend]
status: published
source_ref: https://github.com/BerriAI/litellm
---

LLM 게이트웨이(litellm)는 수많은 백엔드·통합·캐시를 한 지붕에 모은다. 그래서 **한 경로만 빼먹는 실수**가 자주 난다. 이번에 3건을 정리했다.

```figure
{"type":"compare","caption":"litellm 계열 3건","nodes":[{"id":"otel","label":"langfuse_otel","note":"rerank Output 누락"},{"id":"redis","label":"Redis cluster","note":"None 역참조 크래시"},{"id":"docs","label":"litellm-docs","note":"없는 함수 참조"}],"edges":[{"from":"otel","to":"docs"}]}
```

## #37164 — langfuse_otel이 rerank Output을 안 채움
`success_callback: ["langfuse_otel"]`일 때 `/v1/rerank` 스팬은 Input·metadata만 있고 **Output은 항상 비어** 있었다 (기존 `langfuse` 콜백은 채웠다). `LangfuseOtelLogger._set_observation_output`가 `choices`(chat)와 `output`(Responses)은 다뤘지만 rerank 응답(`RerankResponse.results`)을 안 다뤘다. rerank 분기를 추가해 `{index, relevance_score, document}`를 직렬화했다.

## #37163 — Redis cluster 종료 시 None 역참조
Redis **cluster 모드**면 `get_redis_connection_pool()`이 의도적으로 `None`을 반환하는데, `RedisCache.disconnect()`가 이걸 상속받아 **`None.disconnect()` AttributeError**로 프로시 셧다운을 죽였다. 풀이 `None`일 때 가드하고, cluster 클라이언트도 닫도록 고쳤다.

## #912(litellm-docs) — 없는 함수를 문서에 참조
로그 문서가 `litellm.turn_on_message_logging`을 인용했는데 그 함수는 없다. 실존하는 `litellm.turn_off_message_logging`(윗절 "Disable" 참조)이 맞다. 문서를 따라가면 `AttributeError`를 만나는 것. 실제 설정 이름으로 고쳤다.

## 교훈

- **통합 콜백은 "응답 형태마다" 분기한다** (choices/output/results). 새 API 추가 때마다 Output 채우는 경로를 회귀 테스트로 고정하자.
- **설계상 `None`을 반환하는 경로**(cluster mode)는 하위 코드가 반드시 방어해야 한다. 셧다운 같은 중요한 경로에서 크래시가 가장 나쁘다.
- 문서가 실제 API를 따라가게 하려면, **문서 코드 조각을 참조로 검증**하거나 최소한 오타를 확인하자.

[전체 PR 보기 — BerriAI/litellm](https://github.com/BerriAI/litellm)
