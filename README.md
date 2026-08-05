# chjnett.dev

[![Cloudflare Pages](https://img.shields.io/badge/Hosted%20on-Cloudflare%20Pages-orange?logo=cloudflare)](https://pages.cloudflare.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Node.js 18+](https://img.shields.io/badge/Node.js-18+-green.svg)
![Status: Active](https://img.shields.io/badge/Status-Active-brightgreen.svg)

**Live**: [chjnett.dev](https://chjnett.dev)

개인 기술 블로그 + 포트폴리오. Cloudflare 생태계(Pages, Workers, D1, R2)로 구축한 풀스택 블로깅 플랫폼입니다.

## Overview

전통적인 블로깅 플랫폼의 한계를 벗어나, 다음을 직접 구현한 블로그:

- ✅ **완전한 디자인 시스템** — 모노크롬 기반, 재사용 가능한 컴포넌트
- ✅ **자동화 콘텐츠 파이프라인** — GitHub, arXiv, 논문 크롤링 → 자동 드래프트 생성
- ✅ **수동 승인 제어** — 절대 자동 발행 금지, 리뷰 대시보드에서만 발행
- ✅ **API 기반 인프라** — Workers에서 동적 렌더링, D1 데이터베이스, R2 스토리지
- ✅ **오픈 소스 준비** — 코드 자산, 학습 자료, 구현 예제 포함

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Hosting** | Cloudflare Pages (Edge) |
| **Backend** | Cloudflare Workers (Serverless Functions) |
| **Database** | Cloudflare D1 (SQLite) |
| **Storage** | Cloudflare R2 (Object Storage) |
| **Frontend** | React 18+ (SSG + Edge Rendering) |
| **Content** | Markdown + YAML Frontmatter |
| **CLI** | Wrangler (Cloudflare CLI) |
| **Version Control** | Git + GitHub |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    chjnett.dev                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐      ┌──────────────────┐               │
│  │   Markdown   │      │  GitHub / arXiv  │               │
│  │  Posts       │      │  Crawlers        │               │
│  └──────┬───────┘      └────────┬─────────┘               │
│         │                       │                          │
│         └───────────┬───────────┘                          │
│                     ↓                                       │
│         ┌─────────────────────┐                            │
│         │  Content Pipeline   │                            │
│         │  (Draft Creation)   │                            │
│         └────────────┬────────┘                            │
│                      ↓                                      │
│         ┌─────────────────────┐                            │
│         │  Review Dashboard   │                            │
│         │  (Manual Approval)  │  ← 절대 자동 발행 금지    │
│         └────────────┬────────┘                            │
│                      ↓                                      │
│    ┌────────────────────────────────────┐                 │
│    │    D1 Database (Post Metadata)     │                 │
│    └──────┬──────────────────────┬──────┘                 │
│           │                      │                         │
│     ┌─────↓──────┐        ┌──────↓──────┐                │
│     │ Workers    │        │  R2 Storage │                │
│     │ (API/Edge) │        │ (Figures)   │                │
│     └─────┬──────┘        └──────┬──────┘                │
│           │                      │                         │
│           └──────────┬───────────┘                        │
│                      ↓                                     │
│         ┌─────────────────────┐                           │
│         │  Cloudflare Pages   │                           │
│         │  (Static + Edge)    │                           │
│         └─────────────────────┘                           │
│                      ↓                                     │
│              🌍 chjnett.dev                               │
│                                                            │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
.
├── posts-source/               # 블로그 포스트 마크다운 소스
│   ├── attention-is-all-...md  # 기술 포스트
│   └── README.md               # 포스트 작성 가이드
│
├── posts-assets/               # 포스트별 자산 (코드, 데이터, 문서)
│   └── attention-is-all-.../
│       ├── model.py            # 구현 코드
│       ├── benchmark.py        # 벤치마크
│       └── README.md           # 자산 설명서
│
├── worker/                     # Cloudflare Workers 코드
│   ├── src/
│   │   ├── index.ts           # 메인 핸들러
│   │   ├── api/               # API 엔드포인트
│   │   └── utils/             # 공유 유틸리티
│   ├── schema/                # D1 스키마 마이그레이션
│   ├── wrangler.toml          # Wrangler 설정
│   └── package.json
│
├── docs/
│   ├── HANDOFF.md             # 📖 완전한 아키텍처 & 파이프라인 명세
│   ├── TODO.md                # 진행 중인 작업
│   ├── superpowers/
│   │   ├── specs/             # 기능 사양서
│   │   └── plans/             # 구현 계획
│   └── references/            # 참고 자료
│
├── CLAUDE.md                  # 프로젝트 규칙 & 스킬 가이드
├── README.md                  # 이 파일
├── .gitignore
└── wrangler.toml              # Wrangler 설정 (프로젝트 루트)
```

## Key Features

### 1. 콘텐츠 파이프라인
- **자동 드래프트 생성**: GitHub 커밋, arXiv 논문 등에서 자동으로 포스트 생성
- **수동 승인 필수**: 리뷰 대시보드에서만 `draft` → `published` 전환 가능
- **메타데이터 관리**: 작성자, 태그, 카테고리, 발행 상태를 D1에서 추적

### 2. 디자인 시스템
- **모노크롬 설계**: 코드 블록만 색상 사용, 나머지는 검은색/흰색 + 가중치
- **재사용 가능 컴포넌트**: 
  - `code-block` — 문법 강조
  - `terminal-block` — 터미널 출력
  - `figure-block` — 차트/다이어그램
- **다크 모드**: CSS 변수로 테마 전환

### 3. 저장소 및 CDN
- **D1 Database** — 포스트 메타데이터, 통계
- **R2 Storage** — 이미지, 차트, 코드 자산 (CDN 캐싱)
- **Pages** — 정적 사이트 + Edge Functions

### 4. 개발 경험
- 로컬 개발: `wrangler dev`
- 마이그레이션: `wrangler d1 migrations apply`
- 배포: `wrangler deploy` (자동 Pages 연동)

## Getting Started

### Prerequisites
- Node.js 18+
- Cloudflare account (Free tier 이상)
- Git

### Local Development

```bash
# 저장소 클론
git clone https://github.com/chjnett/tech_Blog.git
cd tech_Blog

# 의존성 설치
npm install

# 로컬 개발 서버 시작
wrangler dev

# 브라우저에서 http://localhost:8787 접속
```

### D1 마이그레이션 (필요한 경우)

```bash
# 마이그레이션 작성
wrangler d1 migrations create <database-name> <description>

# 마이그레이션 적용
wrangler d1 migrations apply <database-name>

# 상태 확인
wrangler d1 query <database-name> "SELECT * FROM posts LIMIT 5"
```

### 포스트 작성

```bash
# 1. 마크다운 파일 생성
vim posts-source/my-post.md

# 예시 frontmatter:
# ---
# slug: my-post-title
# title: "포스트 제목"
# excerpt: "한 줄 요약"
# tags: [tag1, tag2]
# status: draft  # ← 처음은 항상 draft
# ---

# 2. 자산(코드, 이미지)이 있으면 posts-assets에 폴더 생성
mkdir -p posts-assets/my-post-title
cp *.py posts-assets/my-post-title/

# 3. 로컬에서 미리보기
wrangler dev

# 4. 커밋 및 푸시
git add posts-source/my-post.md posts-assets/my-post-title/
git commit -m "draft: add my-post-title"
git push

# 5. 리뷰 대시보드에서 승인 후 발행
# (자동 발행 절대 금지 - 수동 승인만 가능)
```

## Content Pipeline Details

### Automatic Draft Generation (예정)

세 가지 소스에서 자동으로 드래프트 생성:

```
GitHub Commits
      ↓
   [Parser] → Extract metadata, code
      ↓
   [Draft Creator] → Generate post + asset links
      ↓
   D1 (status: draft)
      ↓
   Review Dashboard
      ↓
   Manual Approval → published
```

자세한 사양은 [`docs/superpowers/specs/2026-08-02-papers-pipeline-design.md`](docs/superpowers/specs/2026-08-02-papers-pipeline-design.md) 참고.

## Design System

### Color Palette
- **Background**: #ffffff (light) / #000000 (dark)
- **Text**: #000000 (light) / #ffffff (dark)
- **Accents**: 흑백 반전, 테두리, 가중치만 사용
- **Code Syntax**: 4가지 역할 (keyword, string, comment, function)

### Typography
- **Heading**: 가중치(bold) + 크기로 계층 표현
- **Body**: 선명성을 위해 한정된 폰트 스택
- **Monospace**: 코드 블록 전용

자세한 가이드는 [`docs/HANDOFF.md` §1.1](docs/HANDOFF.md) 참고.

## Deployment

### Production Deploy

```bash
# 모든 변경사항 커밋
git add .
git commit -m "feat: add new feature"

# main 브랜치에 푸시
git push origin main

# Cloudflare Pages가 자동 배포
# https://chjnett.dev에서 확인 가능
```

### Manual Deploy (Emergency)

```bash
wrangler deploy
```

## Important Rules

⚠️ **Non-Negotiable**:

1. **절대 자동 발행 금지** — 모든 발행은 리뷰 대시보드에서 수동 승인 필수
2. **모노크롬 외부** — 코드 블록 밖에서는 색상 사용 금지
3. **D1 마이그레이션 확인** — 적용 전 기존 데이터 파괴 여부 확인

자세한 규칙은 [`CLAUDE.md`](CLAUDE.md) 참고.

## Documentation

| 문서 | 목적 |
|------|------|
| [`CLAUDE.md`](CLAUDE.md) | 프로젝트 규칙, 스킬 라우팅, 승인 체크리스트 |
| [`docs/HANDOFF.md`](docs/HANDOFF.md) | 📖 **완전한 아키텍처**, 디자인 시스템, 파이프라인 (필독) |
| [`docs/TODO.md`](docs/TODO.md) | 진행 중인 작업 및 이슈 |
| [`posts-source/README.md`](posts-source/README.md) | 포스트 작성 가이드 |
| [`posts-assets/*/README.md`](posts-assets) | 각 포스트의 코드 자산 설명 |

## Recent Posts

- **[Attention Is All You Need: KV Cache & GQA](https://chjnett.dev/posts/attention-is-all-you-need-kv-cache-gqa)** (2024-08)  
  Transformer 자기회귀 디코딩의 KV 캐시 병목 분석, GQA 미니 구현 및 벤치마크

더 많은 포스트는 [chjnett.dev](https://chjnett.dev)에서 확인.

## Tech Blog Features

### Implemented ✅
- Post metadata 관리 (D1)
- Markdown 렌더링 + 문법 강조
- 다크 모드 지원
- 반응형 레이아웃
- 태그 기반 필터링

### In Progress 🚀
- 자동 콘텐츠 파이프라인 (GitHub/arXiv 크롤러)
- 리뷰 대시보드 (Manual Approval)
- 방문자 통계 (익명화)
- 검색 기능 (전문 검색)

### Planned 📋
- 구독 시스템 (RSS)
- 코멘트 (GitHub Discussions 연동)
- 소셜 공유 (Open Graph 메타데이터)

## Related Projects

- **[HuggingFace](https://huggingface.co)** — 모델 & 논문 호스팅 영감
- **[Obsidian Publish](https://obsidian.md/publish)** — 지식 기반 발행 아이디어
- **[Notion API](https://developers.notion.com)** — 데이터베이스 구조 참고
- **[Wrangler Docs](https://developers.cloudflare.com/workers)** — Workers 개발 참고

## Performance

- **Page Load**: < 1s (Edge caching)
- **TTFB**: < 200ms (Cloudflare CDN)
- **Lighthouse**: 90+ (Performance, Accessibility)

상세한 성능 메트릭은 [Cloudflare Dashboard](https://dash.cloudflare.com/)에서 확인.

## Contributing

이 프로젝트는 개인 블로그이므로 직접 기여는 받지 않지만, 다음은 환영합니다:

- **Issues**: 버그 리포트, 아이디어 제안
- **Discussions**: 기술 논의, 피드백

또는 [`posts-assets/`](posts-assets/) 의 코드 예제에서 영감을 얻어 자신만의 구현을 만들어보세요!

## License

MIT License — 포스트 콘텐츠 및 코드 자산을 자유롭게 사용, 수정, 배포 가능합니다.

## Contact

- **Website**: [chjnett.dev](https://chjnett.dev)
- **GitHub**: [@chjnett](https://github.com/chjnett)
- **Email**: cheonhyeonjun583@gmail.com

---

**Last Updated**: 2024-08-05  
**Status**: 🟢 Actively Maintained  
**Commits**: [GitHub](https://github.com/chjnett/tech_Blog)
