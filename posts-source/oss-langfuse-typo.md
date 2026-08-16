---
slug: oss-langfuse-typo
title: 오타 하나의 가치 — "a a"를 "a"로 고친 langfuse 기여
excerpt: 오픈소스 기여가 항상 커야 하는 건 아니다. langfuse entitlements README의 중복 단어 오타("a a" → "a")를 고친, 작지만 유효한 문서 기여 기록.
tags: [oss, langfuse, docs, typescript]
status: published
source_ref: https://github.com/langfuse/langfuse/pull/12400
---

오픈소스 기여는 반드시 대형 기능이어야 할 필요는 없다. 문서의 오타 하나도, 그 문서를 미래에 읽을 수천 명에게는 유효한 개선이다. 이번엔 langfuse의 entitlements README에서 중복 단어를 정리했다.

```
# before
- `Plan`: A plan is a a tier of features. Eg. `oss`, ...

# after
- `Plan`: A plan is a tier of features. Eg. `oss`, ...
```

## 왜 이런 기여도 의미가 있나

- **점진적 커밋의 연습**: 작은 diff는 리뷰가 쉽고 병합 부담이 적다. 오픈소스 뉴비가 첫 기여로 시작하기에 적합.
- **문서 품질 = 사용자 경험**: README의 오타는 기능 버그보다 못하다고 여겨지지만, 독자가 지식을 흡수하는 걸 조금씩 방해한다.
- **커밋 메시지·PR 규율 연습**: 작은 PR에서도 좋은 PR 제목, 설명, self-review 체크리스트를 연습할 수 있다.

## 교훈

- "이 정도는 너무 사소해서 올리기도 뭐한데"라는 생각은 오픈소스 기여를 막는 대표적 장벽이다. **작고 정확한 개선**은 여전히 환영받는 기여다.
- 다만 작은 PR도 **문서에 맞는 형식·self-review**는 지켜서, 리뷰어의 부담을 최소화해야 한다.

[전체 PR 보기 — langfuse/langfuse#12400](https://github.com/langfuse/langfuse/pull/12400)
