---
slug: oss-mem0-valkey-doc-delete
title: mem0가 Valkey 인덱스만 지우고 문서는 남기던 버그
excerpt: mem0의 컬렉션 삭제가 FT.DROPINDEX(DD 없음)로 인덱스만 제거하고 mem0:<collection>:* 해시를 남겨, reset() 시 인덱스가 그 해시를 다시 채택해 "지운 메모리가 부활"하던 문제 2건을 정리한 기여 기록.
tags: [oss, ai-llm, backend]
status: published
source_ref: https://github.com/mem0ai/mem0
---

벡터 저장소에서 "인덱스 지움"과 "데이터 지움"이 다르다는 걸 의식하지 않으면, **지운 데이터가 부활**하는 골치아픈 버그가 생긴다. mem0의 Valkey 백엔드가 정확히 그랬다.

```figure
{"type":"flow","caption":"인덱스만 삭제 → 해시가 남아 재인덱스","nodes":[{"id":"del","label":"FT.DROPINDEX(DD 없음)"},{"id":"left","label":"해시 mem0:col:* 생존","note":"keyspace에 남음","emphasis":true},{"id":"recreate","label":"reset으로 인덱스 재생성","note":"같은 prefix 재채택"},{"id":"revive","label":"지운 데이터 부활"}],"edges":[{"from":"del","to":"left"},{"from":"left","to":"recreate"},{"from":"recreate","to":"revive"}]}
```

## 문제

`ValkeyDB._drop_index`(및 `delete_col`/`reset`)가 **`FT.DROPINDEX <name>`을 DD 플래그 없이** 실행했다. 이는 검색 인덱스만 제거하고, `mem0:<collection>:*` 해시는 keyspace에 그대로 남긴다.

그런데 `reset()`은 **같은 키 prefix 위에 인덱스를 재생성**한다. 그럼 valkey-search가 생존한 해시를 다시 채택·재인덱싱해서, 지웠던 메모리가 "부활"하는 현상이 생겼다. `#7013`(drop 시 문서 삭제)과 `#7023`(컬렉션 삭제 시 문서 삭제, `DD` 사용) 두 PR로 정리했다.

## 고친 것

`FT.DROPINDEX`에 **`DD`(DELETE_DOCUMENTS) 플래그**를 붙여, 인덱스와 문서를 함께 지우도록 했다. 이렇게 하면 reset/delete 후 재생성해도 남은 해시가 없어 메모리가 부활하지 않는다.

```
FT.DROPINDEX idx DD
```

## 교훈

- **벡터 검색 인덱스의 삭제는 "구조(DROPINDEX)"와 "문서("DD")"가 분리**돼 있다. 지운 줄 알았던 데이터가 남아 부활하는 버그의 전형.
- 저장소 삭제 시 **"인덱스 vs 데이터 vs keyspace"** 를 모두 비우는지 확인해야 한다. reset이 같은 prefix를 재사용한다면 특히.

[전체 PR 보기 — mem0ai/mem0](https://github.com/mem0ai/mem0)
