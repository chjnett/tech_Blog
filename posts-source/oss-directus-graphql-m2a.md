---
slug: oss-directus-graphql-m2a
title: Directus GraphQL의 M2A 유니언 프래그먼트가 null로 풀리는 버그
excerpt: Directus가 GraphQL의 named fragment를 inline fragment로 감쌀 때 M2A 유니언 타입 조건을 잘못 다뤄 필드가 null로 풀리는 문제를 수정한 기여 기록.
tags: [oss, graphql, directus, typescript]
status: published
source_ref: https://github.com/directus/directus/pull/28092
---

GraphQL 스키마가 *generated union*을 만드는 프레임워크(Directus의 M2A 관계)에서는, 프래그먼트의 **type condition**이 개발자가 기대하는 수집 타입이 아니라 **생성된 유니언 타입**이 되는 함정이 생긴다. 이번 버그가 딱 그것이었다.

```figure
{"type":"flow","caption":"named fragment가 M2A 유니언에 선언되면 필드가 null로","nodes":[{"id":"frag","label":"fragment on ..._union","note":"타입 조건 = 생성된 유니언"},{"id":"inline","label":"replaceFragmentsInSelections","note":"inline fragment로 감쌈"},{"id":"parse","label":"parseFields","note":"M2A 분기를 잘못 탐"},{"id":"null","label":"필드 null","note":"연관 컬렉션 못 찾음","emphasis":true}],"edges":[{"from":"frag","to":"inline"},{"from":"inline","to":"parse"},{"from":"parse","to":"null"}]}
```

## 문제

`replaceFragmentsInSelections`가 named fragment를 **자기 타입 조건을 가진 inline fragment**로 감싼다. 그런데 M2A 유니언 위에 선언된 프래그먼트 —

```graphql
fragment sub on topCollection_items_item_union {
  ... on subCollection { name }
}
```

— 의 type condition은 실제 연관 컬렉션(`subCollection`)이 아니라 **생성된 유니언 타입**(`topCollection_items_item_union`)이다.

`parseFields`가 이걸 만나면 M2A 분기를 타서 필드 경로를 유니언 타입에서 만들었다:

```ts
if (isM2A) {
  current = `${parent}:${selection.typeCondition!.name.value}`;   // parent:…_union
  childCollection = selection.typeCondition!.name.value;
}
```

유니언 타입은 실제 컬렉션 스키마에 없으므로 필드가 **null**로 풀린다.

## 고친 것

M2A 여부를 `getRelationInfo(...).relationType === 'a2o'`로 판정할 때, **프래그먼트의 type condition이 유니언 타입 그 자체인 경우**를 걸러 연관 컬렉션을 바로 찾도록 수정했다. inline fragment의 spread에서 유니언 타입 조건이라면 실제 자식 컬렉션들을 대상으로 필드를 구축한다. 회귀 테스트(`parse-query.test.ts`)가 이를 검증한다.

## 교훈

- **스키마 코드젠이 만든 "타입"이 곧 "데이터 모델"이라고 단정하지 마라.** 유니언 타입은 관계이자 타입 레벨의 추상화로, 프래그먼트 배포 시 예상과 다르게 동작한다.
- 프래그먼트 확장/인라인화를 구현할 땐 **타입 조건이 "어떤 종류의 타입"인지**(리프 타입 vs 유니언 vs 컬렉션)를 먼저 구분해야 한다.

[전체 PR 보기 — directus/directus#28092](https://github.com/directus/directus/pull/28092)
