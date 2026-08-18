---
slug: redis-data-structures-and-production-patterns
title: Redis 자료구조의 내부를 이해하는 게 실무에서 왜 강력한가 — String부터 Streams, 안티패턴까지
excerpt: Redis의 String/List/Hash/Set/ZSet/Bitmap/HyperLogLog/Streams 각각의 내부 자료구조(동적 문자열·압축 목록·해시 테이블·skip list)와, 그걸 아는 것이 세션·캐시 일관성·Rate Limit·큐·랭킹 같은 실무 패턴에서 어떻게 통찰로 이어지는지 정리.
tags: [redis, backend, database]
status: published
---

방금 다룬 [서버리스 Redis 글](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-serverless-the-role-of-key-value-store)과 [Semantic Cache 글](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-semantic-cache-llm-cost)에서 Redis가 "자료구조 서버"라는 점을 짚었다. 이번엔 그 **자료구조를 내부 구현까지** 파고들고, 그 지식이 실무 패턴에서 어떤 통찰을 주는지 보여주려 한다.

Redis의 진짜 힘은 "어떤 자료구조를 어떤 명령으로 쓰느냐"가 아니라, **그 자료구조가 내부에서 어떻게 저장되는지**를 알고 선택하는 데서 나온다.

```figure
{"type":"stack","caption":"Redis는 하나의 키에 8가지 타입을 저장한다","nodes":[{"id":"s","label":"String","note":"동적 버퍼(SDS)","emphasis":true},{"id":"l","label":"List","note":"listpack·quicklist"},{"id":"h","label":"Hash","note":"listpack·hashtable"},{"id":"z","label":"ZSet","note":"skip list + hash"},{"id":"e","label":"Stream","note":"radix trie"}],"edges":[]}
```

## 1. 핵심 5가지 — 그리고 내부 구현

### String (SDS)
가장 단순하지만 내부는 `SDS`(Simple Dynamic String): **C 문자열이 아니라 길이를 아는 동적 버퍼**. 그래서 `APPEND`나 `GET` 길이 계산이 `O(1)`이고, 뒤에 공간 여유를 두면 재할당 없이 붙인다. 이것만으로도 "Redis는 바이너리 안전하게 어떤 값이든 문자열로 저장"한다는 걸 이해한다.

### List / Hash / Set — "작으면 압축, 크면 진짜 구조"
Redis는 **작은 데이터는 압축 자료구조(listpack)** 로, 커지면 **진짜 구조(list / hashtable / skip list)** 로 승격한다. 예를 들어 작은 List는 인접한 배열처럼 압축돼 **캐시 라인에 붙어** 읽기·쓰기가 빠르다. 이 "작으면 압축" 설계가 메모리 효율의 비밀이다.

### ZSet — skip list + hash (이중 구조)
**skip list(순서로 탐색)** 와 **해시(멤버→score 조회)** 를 함께 써서, "멤버로 점수 조회"와 "순위로 범위 조회"를 둘 다 빠르게 한다. 이 **두 관점을 동시에** 제공하는 게 랭킹/리더보드의 근거.

```terminal
$ redis-cli
127.0.0.1:6379> ZADD leaderboard 100 alice
(integer) 1
127.0.0.1:6379> ZINCRBY leaderboard 25 alice
"125"
127.0.0.1:6379> ZREVRANGE leaderboard 0 -1 WITHSCORES
1) "alice"
2) "125"
```

## 2. 그 외 강력한 것들

| 타입 | 명령 예 | 쓰임 |
|---|---|---|
| **Bitmap** | `SETBIT`/`BITCOUNT` | 활성 사용자 카운트(존재 여부가 비트), 한 달 출석 |
| **HyperLogLog** | `PFADD`/`PFCOUNT` | 대략적 유니크 카운트 (메모리 아주 적음) |
| **Stream** | `XADD`/`XREADGROUP` | 이벤트 로그, 소비자 그룹(원본은 XADD 가재기) |
| **Geospatial** | `GEOADD` | 반경 검색 |

```terminal
$ redis-cli
127.0.0.1:6379> PFADD visits:2026-08-01 user:1 user:2 user:1
(integer) 1
127.0.0.1:6379> PFCOUNT visits:2026-08-01
(integer) 2        # 유니크 방문자, 메모리 ~12KB로
```

HyperLogLog의 핵심 통찰: **"정확한 유니크 수"가 꼭 필요하지 않고 "대략 + 적은 메모리"로 충분한 측정(DAU 등)** 이 있으면, 정확한 Set 대신 이걸 쓴다.

## 3. 자료구조 지식이 실무 패턴에 주는 통찰

### 3a. 캐시 일관성 — "캐시 지움"과 "TTL"의 균형
자료구조적 사고로 보면, 캐시 일관성 문제는 **"키를 언제 지우고 언제 TTL로 다뉘어야 하는가"** 의 최적화다.

- **Cache-aside**: 읽기 미스 시 DB 읽고 캐시에 씀, 업데이트 시 캐시 무효화
- **TTL**: 정합성이 허용되는 데이터는 `EXPIRE`로 자동 만료 — "항상 싱크" 대신 "언젠가 만료"로 비용을 낮춘다
- **캐시 스탬피드(캐시가 한 번에 죽어 DB로 몰림)**: 락 또는 재계산 직렬화로 방어

```python
# 세션(또는 캐시)에 TTL을 붙이면 "만료"를 직접 안 지우고 시스템에 맡긴다
r.setex("user:cache:"+uid, 3600, json.dumps(profile))
```

### 3b. Rate Limiting — INCR + EXPIRE + 원자성
"초당 N 요청" 제한은 Redis의 **원자적 INCR**이 딱 맞는 문제다. (앞선 글에서 Redis가 "원자 카운터"에 강하다고 한 이유.)

```python
key = f"rl:{ip}:{int(time.time()//60)}"   # 1분 버킷
count = r.incr(key)
if count == 1:
    r.expire(key, 60)                       # 약간의 race지만 TTL로 안전
if count > 100:
    reject()
```

자료구조적 포인트: **버킷 키에 타임스탬프를 넣으면** TTL로 자동 리셋되므로 별도 스케줄러가 필요 없다.

### 3c. 분산 락 — "원자적 SET NX + 만료"
여러 인스턴스가 하나의 자원을 수정할 때 분산 락이 필요하다. `SET key val NX PX 30000`(존재 안 하면 설정 + TTL)은 생성과 만료를 한 명령으로 원자적으로 한다. 단, 진짜 정합성이 극도로 중요하면 **Redlock은 논쟁적** — 단순한 경합 보호로 충분한지 고민해야 한다.

```terminal
127.0.0.1:6379> SET lock:job1 "worker-A" NX PX 30000
OK        # 성공 = 락 획득
```

### 3d. 랭킹/리더보드 — ZSet
`ZINCRBY`로 점수 누적, `ZREVRANGE`로 순위 조회 — 내부 skip list 덕에 "정렬된 상태로" 유지되어 순위 계산이 선형 스캔이 아니다.

### 3e. 메시지 큐 / 이벤트 — Stream
작업 큐가 필요한데 영속·소비자 그룹·ack가 필요하면 Stream이 `RPOPLPUSH` 같은 제한된 리스트 패턴보다 강력하다. 단, "업무에 이벤트 스트림이 정말 있는가"를 먼저 물어야 한다 (카프카 오버스택 논의와 같은 맥락 — [이전 글](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-serverless-the-role-of-key-value-store)).

## 4. 실무 안티패턴 — 유용함의 그림자

| 안티패턴 | 왜 나쁜가 |
|---|---|
| **모든 걸 Redis에** | 데이터 정합성·영속 요구는 RDB가 낫다. Redis는 cache/timing/카운터용 |
| **KEYS `*`** | 전체 키 블로킹(명령이 글로벌 스캔). `SCAN`으로 배치 |
| **큰 value 하나** | 메모리·네트워크·직렬화 비용. 큰 값은 분할/압축 고려 |
| **TTL 없는 캐시** | 영원히 낡은 데이터가 남아 부정합 |
| **키 설계 없는 만능 ZIP** | 접근 패턴에 맞는 자료구조를 골라야 (문자열 파서로 리스트 흉내 금지) |

## 5. 이 블로그 관점 — 어디가 실무에서 진짜인가

앞서 [Semantic Cache](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-semantic-cache-llm-cost)에서 벡터 검색을, [KV Cache vs KV Store](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/kv-cache-vs-kv-store-same-name-different-world)에서 컴퓨트/데이터 캐시의 차이를 다뤘다. 이번 글을 합치면 Redis의 전체 그림이 잡힌다:

- **자료구조**: String~Stream, 작으면 압축되는 내부
- **패턴**: 캐시 일관성·Rate Limit·분산 락·랭킹·큐
- **확장**: 벡터(Vector Set), Semantic Cache

그리고 "업무에 정말 필요한가"를 묻는 판단(원자성/TTL/공유 상태 프레임워크)은 지금까지 읽은 글들에서 반복되는 주제다.

```figure
{"type":"compare","caption":"자료구조 선택 = 트레이드오프","nodes":[{"id":"set","label":"Set","note":"정확한 유니크, 메모리 큼"},{"id":"hll","label":"HyperLogLog","note":"대략 유니크, 메모리 적음"},{"id":"zset","label":"ZSet","note":"정렬+순위, 메모리 중간"}],"edges":[]}
```

## 마무리

Redis를 "자료구조적으로" 이해하면, 실무에서 **왜 이 타입을 이 명령으로 고르는지**가 명령 암기가 아니라 이유로 바뀐다. "작으면 압축", "ZSet은 두 관점", "INCR은 원자" 같은 원리 하나가 캐시·Rate Limit·랭킹 같은 수많은 패턴에 동시에 적용된다. 그게 이 학습의 실용적 가치다.

> 참고: [Redis 공식 데이터 타입 문서](https://redis.io/docs/latest/develop/data-types/) · [Redis Essentials](https://redis.io/ebook/redis-essentials/)
