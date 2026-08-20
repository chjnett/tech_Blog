---
slug: blog-mobile-responsive-optimization
title: 내 블로그를 모바일 반응형으로 최적화한 기록 — 3D는 숨기고 터치는 키우고
excerpt: 데스크톱 위주로 만들던 기술 블로그를 모바일에서 다시 봤더니, 3D 아바타가 배터리를 잡고 터치 타겟이 좁았다. 모바일이면 3D를 접고 터치 크기를 키우고 폰트/성능을 조정하는 반응형 최적화를 어떻게 적용했는지 기록.
tags: [cloudflare, meta, security]
status: published
---

이 블로그는 처음부터 모바일 반응형을 염두에 두고 만들었다. `@media (max-width:760px)`으로 그리드를 한 줄로 접는 정도. 그런데 **실제로 폰에서 다시 보니**, 데스크톱 확인으론 놓치던 문제들이 눈에 들어왔다.

이 글은 이 블로그를 모바일에서 제대로 보이도록 최적화한 과정을 정리한다. 디자인 시스템(모노크롬, 라벨·테두리·흑백 반전)은 그대로 유지하면서다.

```figure
{"type":"flow","caption":"모바일 최적화 체크리스트","nodes":[{"id":"m","label":"모바일 진단"},{"id":"3d","label":"3D 성능","note":"배터리/GPU"},{"id":"t","label":"터치 타겟","note":"≥40px"},{"id":"f","label":"폰트/로딩","note":"display=swap"}],"edges":[{"from":"m","to":"3d"},{"from":"3d","to":"t"},{"from":"t","to":"f"}]}
```

## 1. 문제 — 데스크톱에선 안 보이던 것

모바일(폰)에서 홈을 다시 보니 세 가지가 거슬렸다:

1. **3D 아바타가 배터리를 잡는다** — hero의 three.js 아바타가 폰에서 WebGL을 계속 렌더링.
2. **터치 타겟이 좁다** — 카테고리 필터 pill이 손가락으로 누르기 애매하게 작았다.
3. **글자/카드가 밀린다** — 좁은 화면에서 요약이 2줄로 잘려 부족할 때.

```terminal
$ inspect-mobile (폰에서 점검)
1) 3D WebGL → reduced-motion 없으면 계속 애니메이션
2) .pill → 터치 타겟 ~35px (Apple은 44px 권장)
3) .post-excerpt → 2줄 요약이 좁은 폭에서 부족
```

## 2. 어떻게 고쳤나

### 2a. 모바일이면 3D 아바타를 접고 배지로 대체

데스크톱의 3D 아바타는 재밌지만, **폰에선 성능·배터리 낭비**다. `max-width:760px` 또는 터치 기기(`pointer: coarse`)를 감지해 3D canvas를 숨기고, 대신 모노크롬 "코딩 중" 배지를 보여준다.

```css
@media (max-width:760px){
  .hero-3d-wrap, .hero-3d{ display:none; }        /* 3D 끔 */
  .hero-badge-mobile{ display:inline-flex; }        /* 배지로 대체 */
}
```

게다가 three-avatar.js에서도 `pixelRatio`를 모바일이면 1로 제한해(데스크톱은 2), **렌더 비용을 반으로** 줄였다.

```js
const isMobile = matchMedia('(max-width:760px), (pointer:coarse)').matches;
renderer.setPixelRatio(Math.min(devicePixelRatio||1, isMobile ? 1 : 2));
```

### 2b. 터치 타겟 키우기

Apple HIG는 최소 **44px**, 범용 권장은 40px. 모바일에서 `pill`과 GitHub 아이콘을 최소 터치 크기로 넓혔다.

```css
@media (max-width:760px){
  .pill{ min-height:40px; display:inline-flex; align-items:center; }
  .github-icon-link{ min-height:44px; min-width:44px; display:inline-flex;
                     align-items:center; justify-content:center; }
}
```

클릭 영역이 넓어져서 **엄지로 안 맞고 누르는 실수가 줄었다.**

### 2c. 카드 요약을 모바일에선 3줄로

좁은 폭에서 2줄 요약은 부족해 보여, 모바일에선 `line-clamp`를 3으로 늘렸다. 내용이 더 잘 읽힌다.

```css
@media (max-width:760px){ .post-card .post-excerpt{ -webkit-line-clamp:3; } }
```

## 3. 그대로 둔 것 — 디자인 시스템 원칙

- **모노크롬 유지** — 배지·터치 요소도 기존 팔레트(`--ink`/`--line`/`--ink-soft`)만 썼다.
- **폰트 로딩** — 이미 `display=swap`이라 폰트가 늦게 떠도 로딩을 막지 않는다. 그래도 모바일 폰트 최적화는 계속 확인했다.
- **표/코드 가로스크롤** — `table-wrap`/code-block은 이미 `overflow-x:auto`라 폰에서도 내용 접근 보장.

## 4. 결과

| 항목 | Before | After |
|---|---|---|
| 3D 아바타 (모바일) | 계속 렌더 → 배터리 | **숨김** + 배지 |
| 아바타 픽셀 비율 | 모바일도 2 | 모바일 **1** (렌더 반) |
| 카테고리 pill 터치 | ~35px | **40px** |
| GitHub 아이콘 터치 | ~40px | **44px** |
| 카드 요약 | 2줄 (좁은 폭에서 부족) | 모바일 **3줄** |

모바일에서 "3D가 배터리를 먹는다, 터치가 애매하다"는 불만이 모두 사라졌다. 그리고 이 개선들은 기존 디자인 시스템 토큰만으로, 색이나 새 컴포넌트 추가 없이 이뤄졌다.

## 마무리

반응형은 "그리드를 한 줄로 접는 것"으로 끝나지 않는다. 모바일 특유의 **성능(배터리/GPU), 터치(크기), 정보 밀도(줄 수)** 까지 고려해야 한다. 이 블로그는 이번에 그 세 축을 실제 폰에서 확인하며 다듬었다.

> 이 글은 스스로의 [Worker 개선기](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/worker-refactor-sanitize-hardening) 류의 "이 블로그 자체를 고치며 쓴 메타 포스팅" 이다.
