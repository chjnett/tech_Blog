---
slug: oss-dlt-incremental-zero-lag
title: dlt가 커서 last_value=0일 때 전진을 잊는 버그
excerpt: dlt의 증분 로딩이 last_value가 정확히 0(epoch-0)이면 falsy로 판단해 lag로 커서를 한 칸 되감던 버그를, truthiness 대신 is not None 비교로 고친 기여 기록.
tags: [oss, backend, database]
status: published
source_ref: https://github.com/dlt-hub/dlt/pull/4367
---

데이터 파이프라인에서 **커서가 0에서 시작**하면 생각보다 많은 버그가 생긴다. 파이썬의 falsy 때문에 0은 다른 숫자와 다르게 취급받아서다. dlt의 증분 로딩 `lag` 가드가 딱 그 버그였다.

```figure
{"type":"flow","caption":"last_value=0(epoch-0)이 falsy로 취급돼 lag가 되감는다","nodes":[{"id":"v","label":"cached last_value=0","note":"epoch-0 커서"},{"id":"truthy","label":"if self.lag and last_value","note":"0은 falsy → 가드 스킵","emphasis":true},{"id":"rewind","label":"lag로 되감기","note":"0 → -5 (max, lag=5)"}],"edges":[{"from":"v","to":"truthy"},{"from":"truthy","to":"rewind"}]}
```

## 문제

`lag`의 forward-only 가드가 truthiness 검사를 썼다:

```python
if self.lag and (cached_last_value := cached_state.get("last_value")):
```

커서가 **정확히 `0`** 이면 파이썬에서 falsy라서 조건이 거짓이 되어 **가드가 스킵**된다. 그 결과 다음 실행에서 `lag`가 커서를 한 칸 되감아, `max` 커서에 `lag=5`면 `0 → -5`처럼 역행했다. epoch-0인 숫자 커서가 피해자 (이슈 리포터는 epoch-0 datetime은 truthy라 영향 없음을 언급).

## 고친 것

truthiness 대신 **`is not None`** 비교로 바꿔, 유효한 0도 엄밀히 전진을 유지하게 했다.

```python
if self.lag and cached_state.get("last_value") is not None:
```

## 교훈

- **"값이 있나"는 `is not None`으로,** "값이 참이냐"는 truthiness로 판단을 분리하라. 숫자 커서에서 `0`은 완전히 유효한 값이다.
- 파이프라인 증분 로직에서 커서의 **전진-전용(forward-only)** 성질은 데이터 누락과 직결되므로, falsy 함정을 특히 조심해야 한다.

[전체 PR 보기 — dlt-hub/dlt#4367](https://github.com/dlt-hub/dlt/pull/4367)
