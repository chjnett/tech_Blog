---
slug: oss-grafana-shortlink-orgid
title: Grafana short URL이 org ID를 네임스페이스로 쓰던 버그
excerpt: Grafana의 카피 short URL이 Kubernetes 리소스의 namespace(default/org-<id>/stacks-<id>)를 orgId 쿼리 파라미터로 잘못 넣어 링크가 깨지던 문제를 config.bootData.user.orgId로 고친 기여 기록.
tags: [oss, grafana, typescript, kubernetes]
status: published
source_ref: https://github.com/grafana/grafana/pull/130614
---

"복사한 링크가 가끔 동작을 안 한다"는 버그 한 줄의 원인은, 때로 **네임스페이스와 ID를 혼동**한 데 있다. Grafana의 short URL 생성 코드가 그랬다.

```figure
{"type":"flow","caption":"문제 지점: namespace를 orgId로","nodes":[{"id":"url","label":"복사한 short URL"},{"id":"param","label":"orgId 쿼리 파라미터","note":"= namespace (예: org-5)"},{"id":"ctx","label":"잘못된 컨텍스트","note":"org-5로 진입 실패/오염","emphasis":true}],"edges":[{"from":"url","to":"param"},{"from":"param","to":"ctx"}]}
```

## 무슨 문제였나

Grafana의 `buildShortUrl`이 short URL의 `orgId` 쿼리 파라미터를, short URL 리소스의 **Kubernetes namespace**에서 채워 넣고 있었다.

```ts
const orgId = k8sShortUrl.metadata.namespace;   // 'default' | 'org-<id>' | 'stacks-<id>'
return `${hostUrl}/goto/${key}?orgId=${orgId}`;
```

namespace는 org ID가 아니라 `default`, `org-5`, `stacks-<id>` 형태다. 그래서 복사한 링크가 `?orgId=org-5`처럼 나오고, 올바른 `?orgId=5`가 아니었다. **멀티 org 인스턴스**에서 이 잘못된 파라미터는 링크가 엉뚱한 컨텍스트로 들어가거나 깨지게 만들었다.

## 고친 것

`orgId`를 현재 사용자가 short URL을 만든 org, 즉 `config.bootData.user.orgId`에서 가져오도록 바꿨다. (`config`는 이미 그 파일에 import돼 있었다.)

```ts
const orgId = config.bootData.user.orgId;
```

테스트에서도 `config.bootData.user.orgId = 1`을 셋업해, 생성된 링크가 올바른 숫자 orgId를 담는지 검증한다.

## 교훈

- **리소스 메타데이터(namespace)와 비즈니스 ID(org id)는 다르다.** 데브옵스/쿠버네티스 뒷단을 추상화할수록 "이름/경로"와 "실제 식별자"를 헷갈리는 실수가 잦다.
- 링크/URL을 만들 때 디버그 픽스쳐가 아니라 **실제 사용자 컨텍스트**에서 orgId를 파생해야 동작한다.

[전체 PR 보기 — grafana/grafana#130614](https://github.com/grafana/grafana/pull/130614)
