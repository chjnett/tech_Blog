#!/usr/bin/env python3
"""
worker-refactor-sanitize-hardening 글의 figure 2장을 생성한다.

내용: GET /api/posts가 D1에서 읽는 바이트를 SELECT *(개선 전)와 컬럼 명시(개선 후)로
비교한 차트. 수치는 로컬 D1의 published 글 5편을 실측한 값이다:

    SELECT length(content_md) ...  (개선 전, 본문 포함)
    SELECT length(title)+length(excerpt)+length(tags)+8  (개선 후, 요약 컬럼만)

디자인 시스템 규칙에 맞춰 전부 무채색(ink/ink-soft/line 그레이스케일)으로 그린다.
"""
import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager
import matplotlib.pyplot as plt

# macOS 시스템 한글 폰트 등록 (기본 DejaVu Sans는 한글 글리프가 없어 깨진다)
for _path in ("/System/Library/Fonts/AppleSDGothicNeo.ttc",):
    try:
        font_manager.fontManager.addfont(_path)
    except Exception:
        pass

INK = "#10131A"       # --ink
INK_SOFT = "#5B6270"  # --ink-soft
LINE = "#E7E9EE"      # --line
GRAY = "#AEB4BD"

OUT = "pages/posts-assets/worker-refactor-sanitize-hardening"

# ── 실측 데이터 (로컬 D1, published 5편) ──────────────────────────────
POSTS = [
    ("attention-is-all-you-need-kv-cache-gqa", 19370, 245),
    ("mla-article", 15717, 226),
    ("industrial-rag-multimodal", 6572, 258),
    ("worker-refactor-sanitize-hardening", 6270, 235),
    ("writing-with-code-terminal-figure-blocks", 753, 121),
]
TOTAL_BEFORE = sum(c for _, c, _ in POSTS)   # 48,682 B
TOTAL_AFTER = sum(s for _, _, s in POSTS)    #  1,085 B
AVG_BEFORE = TOTAL_BEFORE / len(POSTS)
AVG_AFTER = TOTAL_AFTER / len(POSTS)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Apple SD Gothic Neo", "DejaVu Sans"],
    "axes.edgecolor": LINE,
    "axes.labelcolor": INK_SOFT,
    "xtick.color": INK,
    "ytick.color": INK_SOFT,
    "text.color": INK,
})

# ── Fig 1: 현재 5편 기준 D1 읽기 바이트 (bar) ─────────────────────────
fig, ax = plt.subplots(figsize=(5.2, 3.2), dpi=200)
labels = ["SELECT *\n(개선 전)", "컬럼 명시\n(개선 후)"]
values = [TOTAL_BEFORE, TOTAL_AFTER]
colors = [GRAY, INK]
bars = ax.bar(labels, values, width=0.5, color=colors)

for bar, v in zip(bars, values):
    if v >= 1000:
        ax.text(bar.get_x() + bar.get_width() / 2, v * 1.02, f"{v/1000:.1f} KB",
                ha="center", va="bottom", fontsize=10, color=INK, fontweight="bold")
    else:
        ax.text(bar.get_x() + bar.get_width() / 2, v * 1.9, f"{v:,} B",
                ha="center", va="bottom", fontsize=10, color=INK, fontweight="bold")

ax.set_ylabel("D1에서 읽는 바이트 (5개 글 합계)")
ax.set_ylim(0, TOTAL_BEFORE * 1.25)
ax.set_yticks([])
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.set_title("GET /api/posts — D1 읽기 바이트", fontsize=11, color=INK, pad=10, loc="left", fontweight="bold")
fig.tight_layout()
fig.savefig(f"{OUT}/fig1_d1_read_bytes.png", facecolor="white")
plt.close(fig)

# ── Fig 2: 글 수 증가에 따른 예측 (line) ──────────────────────────────
fig, ax = plt.subplots(figsize=(5.2, 3.2), dpi=200)
n_posts = [5, 10, 20, 40, 80, 100]
before = [AVG_BEFORE * n for n in n_posts]
after = [AVG_AFTER * n for n in n_posts]

ax.plot(n_posts, before, color=GRAY, lw=2.2, marker="o", ms=4, label="SELECT * (개선 전)")
ax.plot(n_posts, after, color=INK, lw=2.2, marker="o", ms=4, label="컬럼 명시 (개선 후)")
ax.set_yscale("log")
ax.set_xlabel("발행 글 수")
ax.set_ylabel("D1 읽기 바이트 (log)")
ax.set_ylim(1e2, 2e6)
ax.legend(frameon=False, fontsize=9)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.set_title("글 수가 늘수록 벌어지는 격차 (현재 평균 기준 예측)", fontsize=11, color=INK, pad=10, loc="left", fontweight="bold")
fig.tight_layout()
fig.savefig(f"{OUT}/fig2_scaling.png", facecolor="white")
plt.close(fig)

print(f"fig1: {TOTAL_BEFORE:,}B → {TOTAL_AFTER:,}B ({TOTAL_BEFORE/TOTAL_AFTER:.1f}x)")
print("saved:", f"{OUT}/fig1_d1_read_bytes.png", f"{OUT}/fig2_scaling.png")
