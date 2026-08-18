---
slug: oss-langfuse-seeder-idempotency
title: langfuse 시더를 멱등하게 — 다시 돌려도 꺼지지 않게
excerpt: langfuse의 seed-postgres 스크립트가 두 번째 실행부터 Prisma upsert 문법 오류와 중복으로 터지던 문제를, upsert 전환 + skipDuplicates + 중복 체크로 멱등하게 고친 기여 기록.
tags: [oss, backend]
status: published
source_ref: https://github.com/langfuse/langfuse/pull/12459
---

로컬 개발을 위해 시드 스크립트를 "여러 번 돌려야" 하는 순간이 온다. 그런데 만들어진 시더가 **두 번째 실행에서부터 터지면** 멱등성(idempotency) 문제다. langfuse의 `seed-postgres.ts`가 딱 그랬다.

```figure
{"type":"flow","caption":"시더 멱등성: create를 upsert로","nodes":[{"id":"1st","label":"1회 실행","note":"데이터 생성"},{"id":"2nd","label":"2회 실행"},{"id":"issue","label":"중복/upsert 문법 오류","note":"Prisma 검증 실패","emphasis":true},{"id":"fix","label":"upsert + skipDuplicates","note":"재실행 안전"}],"edges":[{"from":"1st","to":"2nd"},{"from":"2nd","to":"issue"},{"from":"issue","to":"fix"}]}
```

## 문제

`seed-postgres.ts`의 몇 가지 문제가 두 번째 실행부터 실패하게 만들었다:
- `Prompt`·`DatasetItem` upsert의 `where` 절에 쓸데없는 `id` 필드가 있어 **Prisma 검증 오류**를 일으킴.
- `TraceSession`·`JobExecution`을 `create`로 해서 중복 실행 시 PK 충돌.
- `llmApiKeys`도 중복 키 허용이 없어 재실행 시 실패.

## 고친 것

- **Redundant `id` 제거**: upsert `where`에서 불필요한 `id` 필드를 빼 문법 오류 수정.
- **create → upsert**: `TraceSession`·`JobExecution`을 `create` 대신 `upsert`로 바꿔 멱등하게.
- **skipDuplicates**: `llmApiKeys` 생성에 `skipDuplicates: true` 추가.

```ts
await prisma.llmApiKeys.upsert({
  where: { projectId_provider: { projectId: project1.id, provider: "openai" } },
  update: {},
  create: { projectId: project1.id, provider: "openai", /* ... */ },
});
```

## 교훈

- **시더는 개발자들이 자주 재실행한다.** 멱등성이 없으면 "첫 실행 OK → 두 번째 실패"가 개발자 경험을 망가뜨린다.
- `upsert`의 `where`는 **유니크 제약에 해당하는 키만** 담아야 한다. 거기에 관계/생성 ID를 집어넣으면 Prisma가 검증 오류를 낸다.

[전체 PR 보기 — langfuse/langfuse#12459](https://github.com/langfuse/langfuse/pull/12459)
