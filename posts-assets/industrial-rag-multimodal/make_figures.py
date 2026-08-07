"""
make_figures.py — results/real_results.json 하나만 읽어서 figure를 그린다.

하드코딩된 수치 없음. 그림에 나오는 모든 값은 run_real_clip.py의 실측 결과다.
블로그 디자인 원칙에 맞춰 무채색만 사용한다.
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

INK = "#10131A"
INK_SOFT = "#5B6270"
LINE = "#E7E9EE"

R = json.loads(Path("results/real_results.json").read_text())
OUT = Path("results/figures")
OUT.mkdir(parents=True, exist_ok=True)


def style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(LINE)
    ax.tick_params(colors=INK_SOFT, labelsize=9)
    ax.grid(axis="y", color=LINE, linewidth=0.8)
    ax.set_axisbelow(True)


# ── Figure 1: Recall@k ────────────────────────────────────────────────
ir = R["image_retrieval"]
fig, ax = plt.subplots(figsize=(7, 4.2))
ks = ["Recall@1", "Recall@5", "Recall@10"]
vals = [ir["recall_top1"], ir["recall_top5"], ir["recall_top10"]]
bars = ax.bar(ks, vals, color=[INK, "#4A505C", "#8A909C"], width=0.55)
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.0%}",
            ha="center", va="bottom", fontsize=12, fontweight="bold", color=INK)
ax.set_ylim(0, 1.15)
ax.set_ylabel("Recall", color=INK_SOFT, fontsize=10)
ax.set_title("Image-to-image retrieval  (CLIP ViT-B/32, n=20 synthetic)",
             fontsize=11, fontweight="bold", color=INK, pad=14)
style(ax)
fig.tight_layout()
fig.savefig(OUT / "01_image_retrieval_performance.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("✓ 01_image_retrieval_performance.png")

# ── Figure 2: 이미지-텍스트 유사도 분포 (실제 160개 값) ────────────────
hs = R["hybrid_search"]
sims = np.array(hs["raw_similarities"])
fig, ax = plt.subplots(figsize=(7, 4.2))
ax.hist(sims, bins=np.linspace(0, 1, 61), color="#8A909C",
        edgecolor="white", linewidth=0.6)
ax.axvline(hs["mean"], color=INK, linestyle="--", linewidth=1.8,
           label=f"mean {hs['mean']:.3f}")
ax.annotate(
    f"the entire distribution spans {hs['max'] - hs['min']:.3f}\n"
    f"(std {hs['std']:.3f}) — a useful retriever\nneeds this spread to be wide",
    xy=(hs["max"], ax.get_ylim()[1] * 0.5),
    xytext=(0.40, ax.get_ylim()[1] * 0.55),
    fontsize=9, color=INK_SOFT, va="center",
    arrowprops=dict(arrowstyle="->", color=INK_SOFT, linewidth=1),
)
ax.set_xlim(0, 1.0)
ax.set_xlabel("cosine similarity (image ↔ document query)", color=INK_SOFT, fontsize=10)
ax.set_ylabel("count", color=INK_SOFT, fontsize=10)
ax.set_title(f"All 160 image-document pairs collapse into "
             f"[{hs['min']:.2f}, {hs['max']:.2f}]",
             fontsize=11, fontweight="bold", color=INK, pad=14)
ax.legend(frameon=False, fontsize=9, labelcolor=INK)
style(ax)
fig.tight_layout()
fig.savefig(OUT / "02_similarity_distribution.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("✓ 02_similarity_distribution.png")

# ── Figure 3: 쿼리별 평균 유사도 — 순위가 갈리는가 ──────────────────────
queries = R["metadata"]["doc_queries"]
per_q = np.array(hs["per_query_mean"])
order = np.argsort(per_q)[::-1]
fig, ax = plt.subplots(figsize=(7.5, 4.6))
ypos = np.arange(len(queries))
ax.barh(ypos, per_q[order], color="#8A909C", height=0.6)
ax.set_yticks(ypos)
ax.set_yticklabels([queries[i] for i in order], fontsize=9, color=INK)
ax.invert_yaxis()
ax.set_xlim(0, 1.0)
for i, v in enumerate(per_q[order]):
    ax.text(v + 0.008, i, f"{v:.3f}", va="center", fontsize=9, color=INK_SOFT)
ax.set_xlabel("mean cosine similarity across 20 images", color=INK_SOFT, fontsize=10)
ax.set_title(f"Top-to-bottom gap is only {hs['per_query_spread']:.3f}  "
             f"— the ranking barely separates",
             fontsize=11, fontweight="bold", color=INK, pad=14)
for side in ("top", "right"):
    ax.spines[side].set_visible(False)
for side in ("left", "bottom"):
    ax.spines[side].set_color(LINE)
ax.tick_params(colors=INK_SOFT, labelsize=9)
ax.grid(axis="x", color=LINE, linewidth=0.8)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(OUT / "03_query_ranking_spread.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("✓ 03_query_ranking_spread.png")

# ── Figure 4: 실제로 돌린 파이프라인 ──────────────────────────────────
meta = R["metadata"]
fig, ax = plt.subplots(figsize=(8, 4.6))
ax.set_xlim(0, 10)
ax.set_ylim(0, 6)
ax.axis("off")


def box(x, y, w, h, lines, fill="white", text_color=INK):
    ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=fill,
                               edgecolor=INK, linewidth=1.5, zorder=2))
    ax.text(x + w / 2, y + h / 2, "\n".join(lines), ha="center", va="center",
            fontsize=9, color=text_color, zorder=3, linespacing=1.5)


def arrow(x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=1.3,
                                shrinkA=0, shrinkB=0))


box(0.2, 4.4, 4.3, 1.1, [f"{meta['num_images']} synthetic defect images",
                         f"({', '.join(meta['defect_types'])})"])
box(5.5, 4.4, 4.3, 1.1, [f"{len(meta['doc_queries'])} document queries",
                         '"surface defect detection", ...'])
box(0.2, 2.9, 4.3, 0.9, ["CLIP ViT-B/32 image encoder", "→ 20 x 512, L2-normalized"])
box(5.5, 2.9, 4.3, 0.9, ["CLIP ViT-B/32 text encoder", "→ 8 x 512, L2-normalized"])
box(2.9, 1.6, 4.2, 0.8, ["cosine similarity"])

arrow(2.35, 4.4, 2.35, 3.8)
arrow(7.65, 4.4, 7.65, 3.8)
arrow(2.35, 2.9, 4.2, 2.4)
arrow(7.65, 2.9, 5.8, 2.4)

ir_r1 = ir["recall_top1"]
box(0.2, 0.15, 4.3, 1.0,
    [f"image ↔ image:  Recall@1 {ir_r1:.0%}", "works"], fill=INK, text_color="white")
box(5.5, 0.15, 4.3, 1.0,
    [f"image ↔ text:  spread {hs['per_query_spread']:.3f}", "does not rank"],
    fill=INK, text_color="white")
arrow(4.2, 1.6, 2.35, 1.15)
arrow(5.8, 1.6, 7.65, 1.15)

ax.set_title("What was actually run  (seed=42, CPU, reproducible)",
             fontsize=11, fontweight="bold", color=INK, pad=10)
fig.tight_layout()
fig.savefig(OUT / "04_pipeline.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("✓ 04_pipeline.png")

print("\nall figures regenerated from results/real_results.json")
