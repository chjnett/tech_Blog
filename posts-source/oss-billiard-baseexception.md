---
slug: oss-billiard-baseexception
title: billiard pool worker가 SystemExit을 삼키던 버그 — BaseException 전파
excerpt: Celery의 저수준 풀 구현인 billiard가 worker에서 발생한 BaseException(SystemExit/KeyboardInterrupt)을 잡지 못해 WorkerLostError를 던지던 문제를 except BaseException으로 고친 기여 기록.
tags: [oss, backend]
status: published
source_ref: https://github.com/celery/billiard/pull/452
---

예외 처리에서 `except Exception`은 "대부분"을 잡지만, 전부는 아니다. 파이썬의 `BaseException`(예: `SystemExit`, `KeyboardInterrupt`)은 `Exception`의 하위가 아니라서 그 아랫자락을 빠져나간다. 풀 워커에서는 그게 치명적인 버그가 됐다.

```figure
{"type":"flow","caption":"워커가 BaseException을 던지면 예전엔 프로세스가 죽었다","nodes":[{"id":"task","label":"워커가 작업 실행"},{"id":"raise","label":"BaseException 발생","note":"SystemExit, KeyboardInterrupt 등"},{"id":"catch","label":"except Exception","note":"BaseException은 안 잡힘","emphasis":true},{"id":"die","label":"워커 조기 종료","note":"호출자는 WorkerLostError"}],"edges":[{"from":"task","to":"raise"},{"from":"raise","to":"catch"},{"from":"catch","to":"die"}]}
```

## 문제

billiard는 Celery가 쓰는 파이썬 프로세스 풀이다. 풀 워커가 테스크를 실행하다 `BaseException`(그냥 `BaseException`, `SystemExit`, `KeyboardInterrupt`…) 을 던지면, worker의 결과 마샬링 코드가 `Exception`만 잡고 있었기 때문에 그 예외가 worker 밖으로 새어 나갔다. 그 결과:
- worker가 예외로 조기 종료되고
- 호출자에게는 실제 예외 대신 **`WorkerLostError`** — 혼란스러운 "워커가 사라졌다"가 전달

## 고친 것

`billiard/pool.py`의 worker 태스크 실행 catch를 `Exception` → `BaseException`으로 바꿔, 어떤 예외든 결과로 마샬링되어 `ApplyResult.get()`에서 재기 되게 했다.

```python
try:
    result = (True, prepare_result(fun(*args, **kwargs)))
except BaseException:          # was: except Exception
    result = (False, ExceptionInfo())
```

테스트로 `raise BaseException("base exception test")`를 던지는 워커가 예외를 정상 전달하는지 확인했다.

## 교훈

- **`BaseException`을 잡아야 하는 곳**은 "실행 흐름 제어(SytemExit, KeyboardInterrupt)"를 프로세스/스레드 경계에서 삼키면 안 되는 곳이다. 워커가 받은 예외를 결과로 되돌려야 하는 프로세스 경계가 그 대표 지점.
- 실무에서 `except Exception`이 충분해 보여도, **프로세스/스레드 경계**에서는 `BaseException`까지 고려해야 예외가 은밀히 프로세스를 죽이고 `WorkerLostError`처럼 가려지는 사고를 막는다.

[전체 PR 보기 — celery/billiard#452](https://github.com/celery/billiard/pull/452)
