#!/usr/bin/env python3
"""
shopping-mall-image-worker 글용 차트 2장.
외주 쇼핑몰 이미지 처리 실무 데이터 기반(모노크롬, 블로그 팔레트).
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
    "font.family":"sans-serif",
    "font.sans-serif":["Apple SD Gothic Neo","DejaVu Sans"],
    "axes.edgecolor":LINE,"axes.labelcolor":INK_SOFT,
    "xtick.color":INK,"ytick.color":INK_SOFT,"text.color":INK,
})

# ── Fig 1: 원본 vs 최적화 예시 용량/크기 ──
# 실제 구현 가이드: 원본 4000px JPEG 수 MB, 브라우저 1차 최적화(1600px WebP q0.82), 파생본 detail(1200 q82)
fig,(ax1,ax2)=plt.subplots(1,2,figsize=(6.4,3.0),dpi=200)
orig_kb=5200; opt1_kb=650; detail_kb=420   # 예시: 원본 5.2MB → 1차 650KB → detail 420KB
bars1=["원본\nJPEG","1차 최적화\nWebP q=.82","detail\n1200px"]
v1=[orig_kb,opt1_kb,detail_kb]
ax1.bar(bars1,v1,color=[GRAY,INK_SOFT,INK],width=0.5)
for b,val in zip(ax1.patches,v1):
    ax1.text(b.get_x()+b.get_width()/2,val*1.02,f"{val/1000:.1f}MB" if val>=1000 else f"{val}KB",ha="center",va="bottom",fontsize=8,color=INK)
ax1.set_ylabel("파일 크기")
ax1.set_title("원본 대비 용량 절감",fontsize=10,color=INK,loc="left",fontweight="bold")
ax1.set_yticks([])
for s in ("top","right"): ax1.spines[s].set_visible(False)

# 절감 배율 라벨
red=orig_kb/detail_kb
ax1.text(0.02,0.8,f"≈ {red:.0f}배 감소",transform=ax1.transAxes,fontsize=9,color=INK,fontweight="bold")

# Fig1b: 파생본 저장 정책
states=["thumb\n400px\nq75","detail\n1200px\nq82","zoom\n2000px\nq88","original\nTTL 삭제"]
sizes=[90,420,1800,0]
ax2.bar(states,sizes,color=[INK_SOFT,INK,INK_SOFT,GRAY],width=0.5)
for b,val in zip(ax2.patches,sizes):
    if val: ax2.text(b.get_x()+b.get_width()/2,val*1.02,f"{val}KB",ha="center",va="bottom",fontsize=8,color=INK)
ax2.set_ylabel("저장 크기")
ax2.set_title("파생본 저장 정책",fontsize=10,color=INK,loc="left",fontweight="bold")
ax2.set_yticks([])
for s in ("top","right"): ax2.spines[s].set_visible(False)
ax2.axhline(0,color=LINE,lw=0)
fig.tight_layout()
fig.savefig(f"{OUT}/fig1_org_vs_optimized.png",facecolor="white")
plt.close(fig)

# ── Fig 2: 이미지 최적화 전/후 트래픽 추정 (월 전송량 감소) ──
# 트래픽 14.29k/day 가정, 이미지 비중 60%, 원본 평균 1.2MB → 최적화 평균 200KB
fig,ax=plt.subplots(figsize=(5.2,3.0),dpi=200)
days=30
daily_req=14290
img_ratio=0.6
imgs_per_day=daily_req*img_ratio   # 이미지 요청 수
mb_before=imgs_per_day*1.2        # 원본 평균 1.2MB
mb_after=imgs_per_day*0.20        # 최적화 평균 200KB
before=[mb_before*d/1000 for d in range(1,days+1)]   # GB
after=[mb_after*d/1000 for d in range(1,days+1)]
ax.plot(range(1,days+1),before,color=GRAY,lw=2.2,marker="o",ms=3,label="원본 전송 (≈1.2MB/장)")
ax.plot(range(1,days+1),after,color=INK,lw=2.2,marker="o",ms=3,label="최적화 전송 (≈200KB/장)")
ax.fill_between(range(1,days+1),after,before,color=INK,alpha=0.06)
ax.set_xlabel("일")
ax.set_ylabel("월 전송량 (GB, 누적)")
ax.legend(frameon=False,fontsize=8)
for s in ("top","right"): ax.spines[s].set_visible(False)
ax.set_title("이미지 최적화 시 전송량 절감 (추정치)",fontsize=10,color=INK,loc="left",fontweight="bold")
fig.tight_layout()
fig.savefig(f"{OUT}/fig2_traffic_savings.png",facecolor="white")
plt.close(fig)

print("saved:", f"{OUT}/fig1_org_vs_optimized.png", f"{OUT}/fig2_traffic_savings.png")
