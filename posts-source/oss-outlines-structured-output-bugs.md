---
slug: oss-outlines-structured-output-bugs
title: outlines의 구조적 출력 백엔드에서 잡은 작은 일관성 버그 4가지
excerpt: 구조적 생성 라이브러리 outlines의 여러 백엔드(SGLang/MLXLM)와 DSL 타입에서, 제약 조건이 조용히 누락되거나 해시가 불가능한 문제 4건을 정리한 기여 기록.
tags: [oss, ai-llm, backend]
status: published
source_ref: https://github.com/dottxt-ai/outlines
---

구조적 LLM 생성(outlines)은 **"제약이 제대로 걸렸는지"** 가 품질이다. 그런데 4건의 버그가 전부 "작은 불일치" 때문에 제약이 조용히 사라지거나 사용 불가능해지는 문제였다.

```figure
{"type":"compare","caption":"같은 repo, 4개의 백엔드/타입 버그","nodes":[{"id":"sglang","label":"SGLang","note":"whitespace_pattern 누락"},{"id":"dsl","label":"DSL 타입","note":"JsonSchema/CFG unhashable"},{"id":"mlx1","label":"MLXLM","note":"falsy output_type 우회"},{"id":"mlx2","label":"MLXLM","note":"is None 대신 not"}],"edges":[{"from":"sglang","to":"mlx2"}]}
```

## #2011 — SGLang이 whitespace_pattern을 버림
`SGLangTypeAdapter.format_output_type`이 `json.loads(term.schema)`를 OpenAI 어댑터에 넘겨 `whitespace_pattern`을 조용히 떨궜다. vLLM 백엔드는 이미 전달하는데 SGLang만 빼먹어, 사용자는 오류 없이 공백 제약을 못 얻었다. JsonSchema 분기를 `structured_outputs`를 직접 구성하도록 고쳐 포함하게 했다.

## #2012 — JsonSchema/CFG가 unhashable
`JsonSchema`와 `CFG`가 `__eq__`만 정의하고 `__hash__`를 안 해서, 파이썬 데이터 모델상 `__hash__ = None`이 되어 `set`/`dict` 키로 못 쓴다. `__hash__`를 normalised schema(정렬된 키)+`whitespace_pattern` 기반으로 추가했다.

## #2013 / #2014 — MLXLM의 `if output_type:` falsy 함정
`MLXLMModel.generate_batch`와 `MLXLMTypeAdapter.format_output_type`가 `if output_type:`/`if not output_type`를 썼다. `__bool__`가 `False`를 반환하는 logits processor(진짜로 유효한 객체)가 **조용히 무시**되고, 제약 없이 생성이 진행됐다. `if output_type is not None` / `if output_type is None`으로 고쳐, 진짜 유효한 객체를 걸러내지 않게 했다.

## 교훈

- **제약/가드 지점에서 truthiness는 위험하다.** "객체 존재"는 `is not None`으로 판단하라 (outlines의 `__bool__` 사례).
- **백엔드별로 동일 제약을 각자 전달**하는 코드는 한쪽이 빠지기 쉽다. 공용 경로로 묶거나, 전달 누락을 테스트로 잡아야 한다.

[전체 PR 보기 — dottxt-ai/outlines](https://github.com/dottxt-ai/outlines)
