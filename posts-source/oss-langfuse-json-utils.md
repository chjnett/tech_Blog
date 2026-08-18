---
slug: oss-langfuse-json-utils
title: 지우면 코드가 술술 — langfuse JSON 유틸 추출 리팩터
excerpt: CodeJsonViewer와 PrettyJsonView에 중복돼 있던 stringifyJsonNode를 공용 util로 추출해 유지보수 비용을 줄인 langfuse 리팩터 기여 기록.
tags: [oss, backend]
status: published
source_ref: https://github.com/langfuse/langfuse/pull/12402
---

중복 코드는 자주 "지금은 괜찮지만"으로 미뤄진다. 코드베이스에 `TODO: deduplicate` 주석이 두 번 보이면, 이제 그때는 리팩터 타이밍이다. langfuse 웹 쪽의 JSON 직렬화 로직을 공용 util로 묶었다.

```figure
{"type":"compare","caption":"중복 → 공용 util","nodes":[{"id":"A","label":"CodeJsonViewer","note":"고유 stringify 로직"},{"id":"B","label":"PrettyJsonView","note":"동일 로직 중복"},{"id":"U","label":"jsonUtils.ts","note":"stringifyJsonNode 공용","emphasis":true}],"edges":[{"from":"A","to":"U","label":"추출"},{"from":"B","to":"U","label":"추출"}]}
```

## 무슨 리팩터였나

두 컴포넌트가 JSON 값을 사람이 읽기 좋게 문자열로 바꾸는 같은 로직을 각자 들고 있었다. 추출한 공용 함수는 "값이 문자열이면 따옴표 없이 그대로, 아니면 JSON 직렬화" 같은 규칙을 담는다.

```ts
// web/src/utils/jsonUtils.ts
export function stringifyJsonNode(node: unknown): string {
  if (typeof node === "string") {
    return node;      // bare string: quotes 없이
  }
  // ... JSON 직렬화 + 예외/순환 처리
}
```

- 두 컴포넌트가 모두 이 util을 쓰도록 교체.
- `CodeJsonViewer.tsx`에서 재-export해 **하위 호환성 유지**(다른 컴포넌트(`IOTableCell` 등)가 기존 import를 그대로 쓰게).

## 좋은 리팩터의 조건

1. **동작은 그대로**(순수한 코드 이동/추출, 기능 변화 없음)
2. **하위 호환성**(재-export로 기존 소비자 유지)
3. **병합 부담 낮음**(로직 공용화 후 중복 삭제)

## 교훈

- "같은 코드가 두 번 보이면" 그 순간이 추출 시점이다 — 세 번이 아니어도.
- 리팩터는 **기능 무변경 + 하위 호환**을 지키는 게 리뷰어 신뢰를 얻는 핵심이다.

[전체 PR 보기 — langfuse/langfuse#12402](https://github.com/langfuse/langfuse/pull/12402)
