#!/usr/bin/env python3
"""
이미지 Worker 개선 답안 글용 차트 — 파생본/캐시 최적화 효과.
모노크롬, 블로그 팔레트.
"""
import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager
import matplotlib.pyplot as plt

for _p in ("/System/Library/Fonts/AppleSDGothicNeo.ttc",):
    try: font_manager.fontManager.addfont(_p)
    except: pass

INK="#10131A"; INK_SOFT="#5B6270"; LINE="#E7E9EE"; GRAY="#AEB4BD"
OUT="pages/posts-assets/shopping-mall-image-worker"

plt.rcParams.update({
    "font.family":"sans-serif","font.sans-serif":["Apple SD Gothic Neo","DejaVu Sans"],
    "axes.edgecolor":LINE,"axes.labelcolor":INK_SOFT,"xtick.color":INK,"ytick.color":INK_SOFT,"text.color":INK,
})

# ── Fig3: 파생본 요청별 전송량 (thumb만 쓸 때 vs detail까지) ──
fig,(ax1)=plt.subplots(figsize=(5.6,3.0),dpi=200)
# 시나리오: 목록 10개, 상세 1개 요청
scenarios=["원본만\n(전부 전송)","최적화+thumb\n(목록은 썸네일)","전부 파생본\n(thumb+detail+zoom)"]
mb=[10*1.2+1*1.2, 10*0.09+1*0.42, 10*0.09+1*0.42+ ((0.42)*0)]   # 목록에 detail을 안 쓰는 게 핵심
# 정확한 수치: 목록에서 detail(420KB) 대신 thumb(90KB) 쓰면 절감
mb_all_original=(10+1)*1.2          # 전부 원본 1.2MB
mb_thumb=(10*0.09)+(1*0.42)         # 목록 thumb 90KB, 상세 detail 420KB
ax1.bar(scenarios,[mb_all_original,mb_thumb,mb_thumb],color=[GRAY,INK,INK],width=0.5)
for b,val in zip(ax1.patches,[mb_all_original,mb_thumb,mb_thumb]):
    ax1.text(b.get_x()+b.get_width()/2,val*1.03,f"{val:.2f}MB",ha="center",va="bottom",fontsize=9,color=INK)
# 절감 라벨
saving=(1-mb_thumb/mb_all_original)*100
ax1.text(0.05,0.85,f"목록 전송량 {saving:.0f}% 절감",transform=ax1.transAxes,fontsize=10,color=INK,fontweight="bold")
ax1.set_ylabel("페이지 요청 전송량")
ax1.set_title("thumb를 목록에 쓰면 전송량이 줄어든다",fontsize=11,color=INK,loc="left",fontweight="bold")
ax1.set_yticks([])
for s in ("top","right"): ax1.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig(f"{OUT}/fig3_thumb_savings.png",facecolor="white")
plt.close(fig)

# ── Fig4: 캐시 히트율 개선에 따른 오리진 부하 ──
fig,ax=plt.subplots(figsize=(5.6,3.0),dpi=200)
cache_rate=[0.1,0.25,0.5,0.75,0.9]
# 오리진 히트 비율 = 1 - cache_rate. 트래픽 14,290 req/day, 이미지 60%
daily=14290*0.6
origin_load=[daily*(1-r)/1000 for r in cache_rate]   # K req/day
ax.plot([str(int(r*100))+"%" for r in cache_rate], origin_load, color=INK, lw=2.2, marker="o", ms=5)
ax.fill_between(range(len(cache_rate)),origin_load,color=INK,alpha=0.06)
ax.set_ylabel("오리진 이미지 요청 (천/day)")
ax.set_xlabel("캐시 히트율")
for s in ("top","right"): ax.spines[s].set_visible(False)
ax.set_title("캐시 히트율이 오리진 부하를 좌우한다",fontsize=11,color=INK,loc="left",fontweight="bold")
ax.set_yticks([])
fig.tight_layout()
fig.savefig(f"{OUT}/fig4_cache_hit_origin.png",facecolor="white")
plt.close(fig)

print("saved fig3_fig4")
