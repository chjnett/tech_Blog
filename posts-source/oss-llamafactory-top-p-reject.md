---
slug: oss-llamafactory-top-p-reject
title: LlamaFactory에서 top_p=0이 1.0으로 조용히 뒤집히던 버그
excerpt: LLaMA-Factory가 top_p=0.0을 아무 경고 없이 1.0으로 재작성해, 사용자가 요구한 "최소 샘플링"을 "최대 다양성"으로 뒤집던 문제를 config 파싱 시점에 검증하도록 고친 기여 기록.
tags: [oss, ai-llm, backend]
status: published
source_ref: https://github.com/hiyouga/LlamaFactory/pull/10759
---

"설정을 그대로 믿는다"는 것은 소프트웨어에서 가장 위험한 가정 중 하나다. LLaMA-Factory에서 `top_p = 0.0`이 조용히 `1.0`으로 바뀌는 걸 발견하고, 이를 파싱 시점에서 거부하도록 고쳤다.

```figure
{"type":"flow","caption":"top_p=0이 사용자 의도와 정반대로 뒤집힌다","nodes":[{"id":"cfg","label":"사용자 설정","note":"top_p=0 (최대 제약)"},{"id":"rewrite","label":"or 1.0 재작성","note":"0은 falsy → 1.0","emphasis":true},{"id":"llm","label":"LLM 생성","note":"최대 다양성 (반대!)"}],"edges":[{"from":"cfg","to":"rewrite"},{"from":"rewrite","to":"llm"}]}
```

## 무슨 문제였나

`top_p = 0.0`을 설정하면 vLLM에 도달하기 전에 **`or 1.0` 가드**가 이를 `1.0`으로 바꿔버렸다. `0.0`은 파이썬에서 falsy라서 `or`의 피연산자로 쓰이면 뒤의 `1.0`이 채택된다.

```python
top_p=top_p or 1.0   # top_p=0.0 → 1.0 (falsy라 뒤로 점프)
```

문제는 의도 방향이 **정반대**가 된다는 것. 사용자가 `top_p=0`을 준 건 "최대한 제약된 샘플링"을 원한 것이지, "최대 다양성(1.0)"이 아니다. 게다가 아무 로그도 없다. 같은 줄의 `temperature=0.0`은 충실히 0을 전달하는데, `top_p`만 홀수였다.

## 고친 것

이슈 리포터가 제안한 방향대로, **config 파싱 시점에 `top_p <= 0`을 거부**하는 검증을 넣었다. (`GeneratingArguments.__post_init__`에서)

```python
if top_p <= 0:
    raise ValueError("top_p must be > 0")
```

잘못된 값이 생성 단계까지 몰래 흘러가지 않도록 **초기에 실패(fail fast)** 한다. `temperature`와 달리 `top_p`는 0이 의미 없는 값이므로 거부가 맞다.

## 교훈

- **`or` 기본값 가드는 "0 / 빈 값"이 유효한 값이면 쓰지 마라.** falsy인 실제 값이 조용히 대체된다.
- 환경·설정 경계에서 들어오는 값은 **"유효하더라도 의도인지"** 확인하고, 이상하면 초기 검증으로 거른다. 조용한 재작성은 디버깅을 최악으로 만든다.

[전체 PR 보기 — hiyouga/LlamaFactory#10759](https://github.com/hiyouga/LlamaFactory/pull/10759)
