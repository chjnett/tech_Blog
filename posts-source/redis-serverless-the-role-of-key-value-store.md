---
slug: redis-serverless-the-role-of-key-value-store
title: Redis를 서버리스 블로그에 쓰려다 알게 된 것 — KV Store의 역할과 D1/KV/Redis 경계
excerpt: Cloudflare Workers 블로그에 Redis를 도입하려다, "왜 여기선 Redis가 정답이 아닐 수 있는지"를 통해 Redis(데이터 구조 서버)와 서버리스 KV/D1(바인딩)이 갈리는 지점을 정리한 학습 기록.
tags: [redis, caching, key-value, cloudflare, database, serverless]
status: published
---

서버리스 블로그(Cloudflare Workers + D1)를 운영하면서 "조회수는 Redis로"라는 말을 흔히 듣는다. 그런데 막상 Workers에서 돌아가는 서버리스 환경은 **자체 Redis 프로세스를 띄울 수 없어서**, Redis의 사촌인 KV 스토어나 D1을 쓰게 된다. 왜 그런가가 이 글의 출발점이다.

이 글은 Redis를 코드로 깊이 다루기보다, **Redis가 "무엇을 해결하는 시스템"인지 그리고 서버리스의 Cache/KV/D1과 어디서 갈리는지**를 정리한다.

```figure
{"type":"flow","caption":"요청이 데이터에 닿는 경로 vs 캐시/스토어","nodes":[{"id":"req","label":"HTTP 요청"},{"id":"cache","label":"에지/캐시 레이어","note":"KV, CDN 캐시"},{"id":"store","label":"데이터 스토어","note":"D1, Postgres"},{"id":"redis","label":"Redis(KV캐시)","note":"자체 서버 필요","emphasis":true}],"edges":[{"from":"req","to":"cache"},{"from":"req","to":"store"},{"from":"req","to":"redis"}]}
```

## 1. Redis는 단순한 캐시가 아니라 "데이터 구조 서버"다

흔히 "Redis = 캐시"로만 기억하기 쉽지만, 공식적으로는 **in-memory data structure store**다. 단순 `GET/SET`을 넘어서 리스트·해시·셋·정렬셋을 갖고 있고, 그걸로 풀 수 있는 것들이 있다.

- **카운터**: `INCR`로 조회수/좋아요 원자적 증가 (분산 서버 간 race 없이)
- **큐/스택**: 리스트 `LPUSH`/`RPOP`으로 태스크 큐
- **정렬랭킹**: `ZINCRBY`로 랭킹 보드
- **TTL 자동 만료**: 명시한 시간 뒤 자동 삭제

```terminal
$ redis-cli
127.0.0.1:6379> INCR post:42:views
(integer) 1
127.0.0.1:6379> INCR post:42:views
(integer) 2
127.0.0.1:6379> EXPIRE post:42:views 3600
(integer) 1
```

여기서 핵심은 **"원자적 연산 + TTL + 메모리 상주"**를 하나의 서버 프로세스가 책임**진다는 점이다. 그래서 Redis가 필요하려면 "이 상태를 공유하며 빨리 읽고 원자적으로 갱신해야 하는" 요구가 있어야 한다.

## 2. 서버리스 블로그엔 왜 Redis가 바로 안 닿나

Cloudflare Workers는 **호출 단위로 짧게 살아나는 실행 환경**이라, Redis(메모리 상주 프로세스)를 직접 띄울 수 없다. 그래서 서버리스 세계에서는 보통 **Upstash**(서버리스 Redis)처럼 호스팅된 Redis를 REST/잔여 연결로 부른다.

그런데 문제는, 서버리스 플랫폼이 이미 **"Redis가 하려는 일의 일부"를 자체적으로 제공**한다는 점이다.

| 기능 | Cloudflare KV | D1(SQLite) | Redis |
|---|---|---|---|
| 저장 위치 | 에지(전역) | 단일 SQLite | 메모리 (+옵션 디스크) |
| 읽기 속도 | 매우 빠름(에지) | 로컬 쿼리 | ms 단위(네트워크) |
| 원자 카운터 | 없음(래치 필요) | 쿼리로는 한계 | **INCR 지원** |
| TTL | 지원 | 없음 | **지원** |
| 자료구조 | 값-문자열 | SQL 테이블 | 리스트/해시/셋 |

## 3. 스스로에게 부딪힌 질문 — "조회수는 정말 Redis가 필요한가?"

조회수 카운터를 Redisis로 만들고 싶다고 했을 때, 실제 요구를 따져보면:

- **누가 조회수를 증가시키는가?** → 서버리스 워커(에지에서 실행)
- **원자적으로 증가해야 하는가?** → 동시 요청이 있을 때 잃으면 안 됨
- **몇 개의 글?** → 이 블로그는 수백 개 미만 (다른 스케일)
- **정확성이 필수인가?** → "약간의 카운터 손실"이 치명적이지 않을 수 있음

여기서 중요한 깨달음: **스케일이 작으면 KV의 "원자 증가 없음"이 실용 문제가 되기 어렵다.** 글 수가 적고 조회수가 낮은 블로그에서, 조회수를 정확히 -1 하지 않아도 문제가 없다면 Redis는 오버엔지니어링이 될 수 있다.

하지만 **"원자 카운터 + TTL"이 진짜로 필요한** 기능(예: 속도 제한, 세션, 랭킹)이 생기면 그때 Redis/Upstash가 딱 들어맞는다. 이 선택 기준을 정리하면:

```
Redis/Upstash를 고려할 때
  ├─ 원자적인 카운터/증감이 필요한가?        → Yes
  ├─ 짧은 TTL로 자동 만료되는 상태인가?      → Yes
  ├─ 여러 인스턴스가 공유해야 하는 상태인가?  → Yes
  └─ (셋 다 아니라면) KV/에지 캐시로 충분
```

## 4. 그래도 쓴다면 — Upstash (서버리스 Redis)

자체 서버를 못 띄우니 서버리스 Redis를 쓴다면, Workers에서는 **Upstash**가 표준이다. REST API를 제공해 Workers의 `fetch`로 호출한다.

```js
// Workers로 Upstash(서버리스 Redis) 호출 — 원자 카운터
const url = `https://${UPSTASH_URL}/incr/post:${slug}:views`;
const res = await fetch(url, { headers: { Authorization: `Bearer ${UPSTASH_TOKEN}` } });
```

이렇게 하면 `INCR`의 원자성을 그대로 얻으면서 자체 서버 없이 Workers에서 쓸 수 있다. 블로그에서는 이로서 **조회수 카운터**가 자연스럽게 설계된다.

## 5. 이 블로그에 내린 결론

- 이 블로그의 현재 데이터(글 목록, PR 상태)는 **변경이 드물고 정적**이라, D1 + 에지 캐시로 충분하다. Redis를 억지로 끌어들일 필요가 없다.
- **카프카**는 더 오버스택이다. 이벤트 소비자/스트림이 없으면 도입 이유가 없다.
- **Redis가 빛나는 곳**은 원자 카운터/빠른 랭킹/TTL 상태 공유 같은 요구가 **실제로** 있을 때다.
- 만약 조회수를 만들면, 정확성보다 "간단함 + 원자성"이 필요한 카운터에 한해 Upstash로. 학습·기록 목적이면 그것만으로 충분한 가치가 있다.

```figure
{"type":"compare","caption":"KV / D1 / Redis — 어디에 쓰는가","nodes":[{"id":"kv","label":"KV","note":"읽기 빠른 부트스트랩·빌드 캐시·플래그"},{"id":"d1","label":"D1","note":"쿼리 필요한 정규화 데이터"},{"id":"redis","label":"Redis","note":"원자 카운터 · TTL · 랭킹"}],"edges":[{"from":"kv","to":"redis"},{"from":"d1","to":"redis"}]}
```

## 마무리

기술 선택은 "최신이니까"가 아니라 **"이 시스템이 실제로 겪는 문제를 해결하는가"** 여부다. 이 블로그처럼 변경이 드문 콘텐츠 블로그에서 Redis가 "꼭 필요"하진 않지만, 정작 그 **필요성 판단의 프레임워크**(원자성 / TTL / 공유 상태)를 익히는 게 이 학습의 진짜 가치였다. 다음 글에선 더 깊이, Redis 자료구조 하나씩을 서버리스 환경의 사례와 함께 풀어볼 수 있다.
