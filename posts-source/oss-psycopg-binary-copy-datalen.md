---
slug: oss-psycopg-binary-copy-datalen
title: psycopg에 binary COPY 길이 검증 기여 — 파이썬 슬라이싱이 조용히 버릇될 때
excerpt: PostgreSQL 드라이버 psycopg의 `_parse_row_binary`가 필드 길이를 초과하면 조용히 잘리던 버그를 찾아 DataError로 바꾸고, C 구현과 동작을 일치시킨 기여 기록.
tags: [oss, postgres, psycopg, python, database]
status: published
source_ref: https://github.com/psycopg/psycopg/pull/1383
---

오픈소스에 기여한다는 건, 가끔은 "이미 도는 코드"가 **왜 그렇게 도는지** 의심하는 데서 시작한다. 이번엔 내가 평소 잘 쓰는 PostgreSQL 드라이버 [psycopg](https://github.com/psycopg/psycopg)에 작은 수정을 넣었다. 트리거는 한 번의 바이너리 `COPY`였다.

```figure
{"type":"flow","caption":"문제 지점: 선언된 길이가 실제 데이터보다 길면 파이썬 슬라이싱이 조용히 자른다","nodes":[{"id":"buf","label":"바이너리 COPY 버퍼","note":"data[pos:pos+length]"},{"id":"slice","label":"Python 슬라이싱","note":"범위 초과해도 예외 안 냄 (자동 클램프)"},{"id":"trunc","label":"조용한 잘림","note":"컬럼 값이 은밀히 잘림","emphasis":true}],"edges":[{"from":"buf","to":"slice"},{"from":"slice","to":"trunc"}]}
```

## 무슨 문제였나

psycopg의 순수 파이썬(`pure-Python`) 경로에서 binary COPY 행을 파싱하는 `_parse_row_binary`는 각 필드의 길이를 4바이트로 읽고, 그 길이만큼 버퍼를 슬라이싱한다.

```python
length = _unpack_int4(data, pos)[0]
pos += 4
if length >= 0:
    row.append(data[pos : pos + length])  # ← 길이가 버퍼를 넘으면?
    pos += length
```

핵심은 **C에서 온 필드 길이(`length`)가 실제 남은 버퍼보다 길 때**다. 파이썬의 `data[pos : pos + length]`는 범위를 초과한 stop을 예외로 안 내고 **가능한 만큼만 잘라 반환**한다. 그래서 어떤 데이터가 손상됐든:
- 오류도 안 나고
- 침묵 속에 컬럼 값이 짤려 들어간다

즉 "잘못된 데이터가 **조용히** 서 있게" 되는 것. C 구현은 이런 경우 `DataError`를 던지는데, 순수 파이썬 경로는 그렇지 않았다. 이 불일치가 버그였다.

## 어떤 수정을 넣었나

```python
if length >= 0:
    if pos + length > len(data):
        raise e.DataError("bad copy data: length exceeding data")
    row.append(data[pos : pos + length])
    pos += length
```

`DataError`를 던져서 C 구현과 동작을 일치시켰고, `tests/test_copy.py`·`tests/test_copy_async.py`에 회귀 테스트를 추가했다. 테스트는 "길이 10을 선언했는데 실제로는 두 바이트(`6162`="ab")만 있는" 바이너리를 만들어 예외를 검증한다.

```terminal
$ python -c "
from psycopg.adapt import Transformer
from psycopg._copy_base import _parse_row_binary
tx = Transformer()
data = bytes.fromhex('00010000000a6162')  # 1필드, 길이 10, 실제 'ab'
try:
    _parse_row_binary(data, tx)
except Exception as e:
    print(type(e).__name__, ':', e)
"
DataError : bad copy data: length exceeding data
```

## 왜 실무에서 중요하냐면

`COPY ... FROM BINARY`는 대량 적재에 쓰이는 고속 경로다. 그런 경로에서 데이터가 손상되면 보통 "에러로 명확히 드러났으면 좋겠는데" 조용히 들어가버린다. 이후 쿼리 결과가 어딘가 미묘하게 틀어지고, 원인 추적은 몇 배 어려워진다. **빠르게 실패(fail fast)** 하는 게 데이터 무결성 문제에서 훨씬 안전하다.

## 오픈소스 기여가 준 것

이 수정은 크지 않다(단 두 줄 + 테스트). 하지만 좋은 교훈을 줬다:
- **이미 동작하는 코드도 "이론상 예외 케이스"를 의심해봐라.** 외부(네트워크, 파일, 라이브러리 경계)에서 들어오는 값은 항상 불신하자.
- 파이썬 슬라이싱의 자동 클램프 특성은 "유연하다"와 "조용히 망가진다"의 두 얼굴이다. **제약을 검증하는 곳**에서는 예외를 명시적으로 던지는 게 맞다.

psycopg는 PostgreSQL 16 쿼리할 때 자주 만나는 드라이버니, 내 코드가 실제로 아무도 안 부숴지길. 기여한 PR은 아래에서 볼 수 있다.

[전체 PR 보기 — psycopg/psycopg#1383](https://github.com/psycopg/psycopg/pull/1383)
