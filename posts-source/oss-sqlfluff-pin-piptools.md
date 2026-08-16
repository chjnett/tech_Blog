---
slug: oss-sqlfluff-pin-piptools
title: SQLFluff Dockerfile에 pip-tools 버전 고정 — 되던 빌드가 잠들었다가 깨진 이유
excerpt: SQLFluff의 DockerHub 발행이 unpinned pip-tools가 Python 3.14에서 삭제된 pip 내부를 import하다 깨진 버그를 찾아, 재발 방지로 pip-tools>=7.6.1을 고정한 기여 기록.
tags: [oss, sqlfluff, python, docker, pip]
status: published
source_ref: https://github.com/sqlfluff/sqlfluff/pull/8350
---

"어제까지 되던 빌드"가 캄캄하게 깨졌을 때, 원인은 종종 **버전이 고정되지 않은 의존성**에 있다. 이번엔 SQLFluff의 DockerHub 발행이 그 이유로 실패해서, 버전 고정으로 고쳤다.

```figure
{"type":"flow","caption":"재현 흐름: unpinned 의존성이 시간이 지나며 깨진다","nodes":[{"id":"venv","label":"Dockerfile","note":"pip-tools 고정 없이 설치"},{"id":"resolve","label":"build 시점 최신 pip-tools","note":"환경마다 다름"},{"id":"import","label":"pip 내부 import","note":"Python 3.14에서 stdlib_pkgs 제거","emphasis":true},{"id":"fail","label":"pip-compile 실패","note":"DockerHub publish 중단"}],"edges":[{"from":"venv","to":"resolve"},{"from":"resolve","to":"import"},{"from":"import","to":"fail"}]}
```

## 무슨 문제였나

SQLFluff 4.3.0 발행 중 `pip-compile` 단계가 실패했다. 에러 메시지는 이랬다:

```terminal
$ pip-compile
ImportError: cannot import name 'stdlib_pkgs' from 'pip._internal.utils.compat'
```

원인: Dockerfile이 `pip-tools`를 **버전 없이(unpinned)** 설치했다.

```dockerfile
RUN pip install --no-cache-dir --upgrade pip setuptools wheel pip-tools
```

`pip-tools` 7.6.1 이하는 Python 3.14에서 사라진 `pip._internal.utils.compat.stdlib_pkgs`를 import해서 깨진다. 그런데 도커 빌드가 해석하는 시점에 따라 최신(python 3.14 호환) 또는 이전 버전이 깔릴 수 있어서 **간헐적으로** 실패했다. 당시엔 이전 버전이 설치돼 깨진 것.

## 고친 것

린트/발행 단계를 못 쓰게 만든 의존성 파손을 막으려면, 최소 호환 버전을 명시해야 한다.

```dockerfile
# Pin pip-tools >= 7.6.1: earlier versions import a removed pip internal
# (stdlib_pkgs) on Python 3.14, breaking the pip-compile step (see #8316).
RUN pip install --no-cache-dir --upgrade pip setuptools wheel pip-tools>=7.6.1
```

`pip-tools>=7.6.1`로 고정해, 해석 시점이 언제든 Python 3.14와 호환되는 버전이 깔리게 했다.

## 교훈

- **의존성 상한/하한은 라이브러리 내부에 대한 불신의 표현이다.** 특히 `pip` 같은 인프라 의존성은 파이썬 버전이 올라가며 내부가 바뀌기 쉽다.
- 간헐적 빌드 실패(이번엔 됐다 저번엔 됐다)는 **비결정적 의존성 해석**을 의심하라. 고정은 그 치명적인 비결정성을 제거한다.

[전체 PR 보기 — sqlfluff/sqlfluff#8350](https://github.com/sqlfluff/sqlfluff/pull/8350)
