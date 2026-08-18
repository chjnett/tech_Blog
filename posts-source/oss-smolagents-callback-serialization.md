---
slug: oss-smolagents-callback-serialization
title: smolagents MultiStepAgent의 콜백 직렬화 지원
excerpt: HuggingFace smolagents의 에이전트 save()/from_folder()가 step_callbacks와 final_answer_checks 같은 콜러블을 저장·복원하지 못하던 문제를, 안전한 path 기반 직렬화로 해결한 기여 기록.
tags: [oss, ai-llm, agents]
status: published
source_ref: https://github.com/huggingface/smolagents/pull/2146
---

LLM 에이전트 프레임워크를 쓰다 보면, "여기 콜백도 저장하고 불러와야 되는데" 하는 순간이 온다. 하지만 콜백은 함수라서 JSON으로 못 직렬화한다. smolagents의 `MultiStepAgent`가 `save()`를 호출할 때 이 콜백들을 잃는 문제를 고쳤다.

```figure
{"type":"flow","caption":"저장 경로: 콜백은 path 문자열로","nodes":[{"id":"save","label":"agent.save()"},{"id":"info","label":"콜백 정리","note":"함수 → 안전한 path 문자열"},{"id":"json","label":"저장 폴더","note":"JSON 메타데이터"},{"id":"load","label":"from_folder()","note":"path → 호출가능 객체 복원"}],"edges":[{"from":"save","to":"info"},{"from":"info","to":"json"},{"from":"json","to":"load"}]}
```

## 문제

`MultiStepAgent`에 `step_callbacks`나 `final_answer_checks` 같은 콜백을 넣고 `save()`하면, 이 콜러블들은 통상 직렬화가 안 된다. 그래서 저장 후 `from_folder()`로 복원하면 콜백이 사라지거나 잘못 처리됐다. 에이전트를 파일로 영속화하는 기능(save/from_folder)이 콜백을 포함한 전체 설정을 복원하지 못하는 상태였다.

## 고친 것

`save()` 시 콜백을 함수 객체 그대로 JSON에 넣는 대신, **안전한 path 문자열**로 정리하고, `from_folder()`에서 그 path를 다시 실제 callable로 복원하도록 구현했다.

- `CALLBACK_REGISTRY`: 콜백 path 문자열 → callable 매핑 (역직렬화 시 먼저 조회)
- `ALLOWED_CALLBACK_NAMESPACES`: 역직렬화가 허용하는 네임스페이스(보안: 임의 경로 로딩 방지)
- `MEMORY_STEP_MAP`: memory step 타입을 안전하게 복원

```python
CALLBACK_REGISTRY = {
    "smolagents.monitoring.OpenTelemetrySpan": OpenTelemetrySpan,
    # ... 등록된 콜백
}
```

`tests/test_callable_serialization.py`가 `CodeAgent`로 콜백을 저장→복원 후 실행되는지를 검증한다.

## 디자인 포인트

안전하게 하려면 "함수를 아무 경로에서 재현"하는 게 아니라 **명시적으로 등록된 소스만** 역직렬화하도록 허용 목록(allowlist)을 둔다. 이는 콜백 직렬화의 교과서적 보안 패턴이다.

## 교훈

- 콜러블은 본질적으로 파일 직렬화 대상이 아니다. **레퍼런스를 문자열로 저장하고, 로딩 시 안전한 레지스트리에서 복원**하는 방식이 정공법.
- 함수 직렬화 기능을 만들면 **보안(코드 인젝션)** 을 항상 고려해야 한다 — 신뢰 안 되는 경로에서 대한 호출을 막는 네임스페이스/레지스트리 장치가 필수.

[전체 PR 보기 — huggingface/smolagents#2146](https://github.com/huggingface/smolagents/pull/2146)
