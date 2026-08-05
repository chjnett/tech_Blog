---
slug: writing-with-code-terminal-figure-blocks
title: code / terminal / figure 블록 쓰는 법
excerpt: 이 블로그에 글을 쓸 때 code/terminal/figure 세 가지 컴포넌트를 어떻게 쓰는지 실제 예시로 정리.
tags: [meta, guide]
status: published
---

이 블로그 글에는 세 가지 콘텐츠 컴포넌트가 있다 — 코드, 터미널, 개념 다이어그램. 세 개를 한 글 안에서 어떻게 쓰는지 실제 예시로 정리해둔다.

## 코드 블록

언어 태그만 붙이면 자동으로 신택스 하이라이팅된다.

```python
# multiply two numbers
def multiply(a, b):
    return a * b
```

## 터미널 블록

실행 결과를 그대로 붙이고 싶을 때는 `terminal`로 태그한다. `$`로 시작하는 줄은 명령어로, 나머지는 출력으로 구분된다.

```terminal
$ python demo.py
result: 42
```

## Figure 블록

개념 간 흐름을 그림으로 보여주고 싶을 때는 `figure`로 태그하고 JSON으로 노드/엣지를 적으면 자동으로 배치된다. 아래는 두 입력이 하나로 합쳐지는 예시.

```figure
{"type":"flow","caption":"A와 B가 합쳐져 C가 되는 예시","nodes":[{"id":"a","label":"Input A","note":"첫 번째 입력"},{"id":"b","label":"Input B","note":"두 번째 입력"},{"id":"c","label":"Combined Output","emphasis":true}],"edges":[{"from":"a","to":"c","label":"merge"},{"from":"b","to":"c"}]}
```

이 세 가지면 대부분의 기술 글을 표현할 수 있다.