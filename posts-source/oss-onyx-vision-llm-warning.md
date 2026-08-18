---
slug: oss-onyx-vision-llm-warning
title: onyx가 이미지 없는 배치에도 vision LLM 경고를 매번 뱉던 버그
excerpt: onyx의 인덱싱이 이미지가 없는 텍스트 전용 배치에서도 "vision LLM 없음" 경고를 모든 실행마다 로그로 남기던 것을, 배치에 이미지가 있을 때만 경고하도록 고친 기여 기록.
tags: [oss, ai-llm, backend]
status: published
source_ref: https://github.com/onyx-dot-app/onyx/pull/14011
---

"경고를 항상 뱉으면 경고의 의미가 사라진다." onyx의 인덱싱 파이프라인은 이미지가 하나도 없는 텍스트 전용 배치에서도 vision LLM 경고를 매번 출력했다.

```figure
{"type":"flow","caption":"조건이 잘못 걸려 무죄 이미지 배치까지 경고","nodes":[{"id":"batch","label":"텍스트 전용 배치","note":"ImageSection 없음"},{"id":"warn","label":"vision LLM 경고","note":"매 실행마다 노이즈","emphasis":true},{"id":"img","label":"이미지 배치","note":"실제로 vision 필요"}],"edges":[{"from":"batch","to":"warn"},{"from":"warn","to":"img"}]}
```

## 문제

`process_image_sections()`는 배치에 `ImageSection`이 없으면 `llm = None`으로 설정한다. 그런데 "vision-capable LLM이 없다"는 경고는 **이미지 분석이 전역적으로 켜졌는지만** 보고 뱉었다. 그래서 텍스트 전용 배치(요약할 이미지 없음)에서도 매 실행마다 같은 경고가 로그에 쌓였다. 진짜로 vision LLM이 필요한 이미지 배치에서만 의미가 있는 경고인데.

## 고친 것

경고 조건을 **"이미지 분석 활성 + 이 배치에 이미지가 실제로 있을 때"** 로 좁혀, 무죄인 텍스트 배치에서는 경고를 뱉지 않게 했다.

```python
if image_analysis_enabled and has_image_section and llm is None:
    logger.warning("no vision-capable LLM ...")   # 이미지 배치에서만
```

## 교훈

- **로그 경고의 조건은 "실제로 문제가 되는 상태"여야** 한다. 전역 기능 플래그만으로 경고하면 정상 상태가 노이즈로 가득 찬다.
- 인덱싱같이 반복 실행되는 파이프라인에서 **항상 나오는 경고**는 결국 무시된다. 빈도가 높을수록 조건을 세밀하게 걸어야 의미가 살아난다.

[전체 PR 보기 — onyx-dot-app/onyx#14011](https://github.com/onyx-dot-app/onyx/pull/14011)
