---
slug: oss-vllm-tool-template-wheel
title: vLLM에서 잡은 Anthropic tool 템플릿 파손과 wheel 변형 폴백 2건
excerpt: vLLM 진입점에서 Anthropic tool_result의 tool_reference가 원시 dict로 새어 나와 Jinja 템플릿이 깨지는 문제와, setup.py가 CUDA 변형 wheel 조회 실패를 조용히 폴백하던 문제 2건을 정리한 기여 기록.
tags: [oss, ai-llm, backend]
status: published
source_ref: https://github.com/vllm-project/vllm
---

vLLM은 LLM 서빙에서 매우 넓은 지면을 커버한다. 그 넓은 표면적 덕에, "한 진입점만 다르게 취급하는" 버그가 숨어 있다. 이번에 두 건을 정리했다.

```figure
{"type":"compare","caption":"입력 경계 2곳에서 잡은 버그","nodes":[{"id":"api","label":"Anthropic API","note":"tool_reference 원시 전달"},{"id":"build","label":"setup.py 빌드","note":"CUDA 변형 wheel 폴백"}],"edges":[{"from":"api","to":"build"}]}
```

## #52610 — Anthropic tool_reference가 Jinja 템플릿을 깨뜨림
`AnthropicServingMessages._convert_user_tool_result`는 `tool_result` 안의 `text`/`image` 항목을 템플릿 안전한 OpenAI content로 변환하는데, `tool_reference` 항목은 **원시 dict**로 그대로 두었다 (`{"type":"tool_reference","name":...}`).

그 원시 dict가 `tool`-role 메시지의 `content`로 들어가면서, 엄격한 Jinja 채팅 템플릿(예: Qwen3)이 catch-all `raise_exception` 분기에 걸려 **`tool_reference` 하나만 있으면 대화가 통째로 깨졌다.** 툴 결과를 텍스트로 안전 변환하도록 고쳤다.

## #52609 — precompiled wheel vari변형 폴백
Python-only 빌드에서, 선택된 CUDA 변화형에 대한 precompiled-wheel 메타데이터 조회가 실패하면 `setup.py`가 **루트/기본 변형 인덱스로 폴백**했다. 그런데 어디서도 "폴백이 선택한 CUDA 변형과 맞는지"를 검증하지 않는다. PyTorch CUDA 12.9가 `cu129`를 선택했는데 그 메타데이터가 없다면, 다른 CUDA 변형 wheel을 조용히 받을 수도 있는 셈.

조회 실패를 폴백 대신 **전파**해서, "아무 wheel이나 조용히 받는" 일을 막도록 고쳤다.

## 교훈

- **입력 경계(API 진입점)에서 데이터 형태를 통일**하지 않으면, 하류 템플릿/렌더러가 엄격할수록 터진다. `text`/`image`는 변환하면서 `tool_reference`만 원시로 남긴 게 근본 원인.
- 빌드/설치 경로의 **"폴백이 곧 오염"** 이 되는 경우가 있다. 실패를 감추지 말고 명시적으로 전파해야, 엉뚱한 변형이 조용히 깔리는 사고를 막는다.

[전체 PR 보기 — vllm-project/vllm](https://github.com/vllm-project/vllm)
