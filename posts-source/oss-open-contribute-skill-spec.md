---
slug: oss-open-contribute-skill-spec
title: 내 에이전트 스킬 저장소가 패키징 안 되는 이유 — SKILL.md 스펙 컴플라이언스
excerpt: Agent Skills 저장소 open_contribute의 SKILL.md frontmatter에 스펙에 없는 version 키가 있어 공식 packager가 거부했던 문제를 찾아 스펙에 맞게 고치고 CI를 강화한(머지됨) 기여 기록.
tags: [oss, agents]
status: published
source_ref: https://github.com/chjnett/open_contribute/pull/1
---

내가 만든 Agent Skills 저장소가 "패키징이 안 된다"며 실패했다. 원인은 나 스스로 심은 스펙 미준수 필드와, 그걸 놓치게 만든 CI였다. 그 걸음을 고치고 CI까지 강화해 머지까지 받은 기록이다.

```figure
{"type":"flow","caption":"미준수 필드가 패키저를 막는다","nodes":[{"id":"md","label":"SKILL.md frontmatter","note":"버전 키를 최상위에 심음"},{"id":"pack","label":"공식 packager","note":"스펙 외 키 거부"},{"id":"ci","label":"CI validator","note":"같은 키를 오히려 요구","emphasis":true},{"id":"dead","label":"배포 경로 막힘","note":"packaged skill 불가"}],"edges":[{"from":"md","to":"pack"},{"from":"pack","to":"dead"},{"from":"ci","to":"pack"}]}
```

## 문제

Agent Skills 스펙에서 **`SKILL.md` frontmatter에 `version:` 키는 허용되지 않는다.** 그런데:
- 저장소의 `SKILL.md` frontmatter에 최상위 `version:` 을 넣어둠.
- 공식 packager가 그걸 발견하고 빌드를 거부: `Validation failed: Unexpected key(s) in SKILL.md frontmatter: version`
- 반면 내 `scripts/validate_skill.py`는 그 `version:` 을 **요구**하고 있어서, CI는 빌드 불가능한 상태를 "통과"로 만들었다. README는 패키징된 `.skill`로 설치하라고 안내해 놓았기에 **그 설치 경로는 죽어 있었다.**

## 고친 것

- **스펙 준수**: `version` 을 최상위 `SKILL.md` frontmatter에서 제거하고, 스펙이 허용하는 `metadata.version` 로 이동.
- **CI 강화**: `validate_skill.py` 를 첫 스킬 하나만 검증하던 것에서 **`*/SKILL.md` 전부**를 검증하도록 확장. 이로써 "CI는 파란불, 실제 배포는 실패"하는 헛점을 막았다.

```yaml
- name: Validate SKILL.md frontmatter
  run: |
    for skill in */SKILL.md; do
      python scripts/validate_skill.py "$skill"
    done
```

## 머지(false로 표시됐던) 기록

이 PR은 제 저장소(open_contribute)의 것을 스펙 컴플라이언스로 바로잡은 셀프 기여이고, 실제로 머지되어 배포 경로가 복구되었다.

## 교훈

- **하나의 검증 도구가 스펙과 어긋나면**, CI가 "잘못된 것을 표준으로 굳혀" 놀리게 한다. validator는 **스펙을 기준**으로 검증해야지, "내가 심은 필드"를 요구하면 안 된다.
- 배포 스크립트/CI가 바라보는 대상과 **실제 사용자가 쓰는 설치 경로**가 일치하는지 자주 점검하라(둘이 어긋나면 죽은 경로가 방치된다).

[전체 PR 보기 — chjnett/open_contribute#1](https://github.com/chjnett/open_contribute/pull/1)
