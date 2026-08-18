---
slug: oss-urfave-cli-mutex-flag
title: urfave/cli 상호배타 플래그 에러가 alias 이름을 못 알려주던 문제
excerpt: Go CLI 라이브러리 urfave/cli의 상호배타 플래그 체크가 primary 이름 대신 사용자가 실제 입력한 alias를 에러에 담지 못하던 문제를, setFlags를 map[Flag]string으로 바꿔 해결한 기여 기록.
tags: [oss, backend]
status: published
source_ref: https://github.com/urfave/cli/pull/2409
---

CLI 에러 메시지 하나가 요구되면 답답하다. "`option i cannot be set along with option t`" — 그런데 사용자는 `-ai`를 썼는데 `-t`로 표시? 이건 alias 때문에 벌어진 이름 손실이었다.

```figure
{"type":"flow","caption":"플래그 별칭이 에러 문구를 헷갈리게 만든다","nodes":[{"id":"set","label":"사용자가 -ai 로 설정","note":"alias"},{"id":"track","label":"setFlags","note":"값(쓰인 이름) 저장"},{"id":"err","label":"상호배타 에러","note":"primary 이름(-t) 노출","emphasis":true}],"edges":[{"from":"set","to":"track"},{"from":"track","to":"err"}]}
```

## 문제

urfave/cli의 상호배타 플래그 검사가 `flg.Names()[0]` — 즉 **primary 이름** — 을 에러에 보고했다. 그래서 어떤 플래그를 **alias로** 설정했어도 에러는 "그 플래그의 primary 이름"을 참조했다.

예: `-ai`(alias)로 설정한 플래그 충돌 시 `option i cannot be set along with option t`처럼, 사용자가 실제 입력한 `-ai`가 아니라 `-t`(primary)를 보여준다. 사용자는 헷갈린다.

## 고친 것

플래그가 "설정됐는지"만 담던 `setFlags`를 `map[Flag]struct{}`에서 **`map[Flag]string`**으로 바꿔, **설정에 쓰인 실제 이름**을 함께 저장하도록 했다. `Command.set`에서 파싱된 이름을, env-var 설정 플래그는 primary 이름을 저장하고, `MutuallyExclusiveFlags.findSetFlag`가 그 저장된 이름을 에러에 보고한다.

```go
// command.go
setFlags map[Flag]string

// 이제 충돌 시 "사용자가 입력한 별칭"을 보고
```

## 교훈

- **에러 메시지는 "무엇"을 알려줄 뿐 아니라 "사용자가 그걸 뭐라고 불렀는지"까지 반영해야** 명확하다.
- **상태를 담는 자료구조를 확장**해(불리언 셋 → 이름 값 맵) "설정됨" 너머 "어떤 이름으로 설정됨"을 보존할 수 있다.

[전체 PR 보기 — urfave/cli#2409](https://github.com/urfave/cli/pull/2409)
