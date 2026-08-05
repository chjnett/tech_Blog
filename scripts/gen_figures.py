"""
gen_figures.py — MLA 블로그 포스트용 matplotlib 차트 4개를 생성한다.
출력: pages/posts-assets/mla-article/*.png
"""

import os
import matplotlib
matplotlib.use('Agg')   # 헤드리스 환경
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ── 한국어 폰트 설정 (macOS Apple SD Gothic Neo) ─────────────
plt.rcParams['font.family'] = 'Apple SD Gothic Neo'
plt.rcParams['axes.unicode_minus'] = False

# ── 출력 경로 ────────────────────────────────────────────────
OUT_DIR = 'pages/posts-assets/mla-article'
os.makedirs(OUT_DIR, exist_ok=True)

# ── 블로그 디자인 토큰 ────────────────────────────────────────
INK       = '#10131A'
INK_SOFT  = '#5B6270'
LINE      = '#E7E9EE'
BG        = '#FFFFFF'
BG_SOFT   = '#F6F7F9'
ACCENT    = '#10131A'

# 4개 구성 색상 (단색 계열, 가독성 우선)
COLORS = {
    'MHA':   '#10131A',
    'GQA-4': '#4A6FA5',
    'GQA-2': '#70A37F',
    'MQA':   '#C87941',
    'MLA':   '#9B4DCA',
}

def style_ax(ax, title='', xlabel='', ylabel=''):
    """공통 축 스타일 적용"""
    ax.set_facecolor(BG)
    ax.spines[['top', 'right']].set_visible(False)
    ax.spines['left'].set_color(LINE)
    ax.spines['bottom'].set_color(LINE)
    ax.tick_params(colors=INK_SOFT, labelsize=10)
    ax.xaxis.label.set_color(INK_SOFT)
    ax.yaxis.label.set_color(INK_SOFT)
    if title:
        ax.set_title(title, color=INK, fontsize=12, fontweight='bold',
                     pad=12, loc='left')
    if xlabel:
        ax.set_xlabel(xlabel, labelpad=8)
    if ylabel:
        ax.set_ylabel(ylabel, labelpad=8)
    ax.grid(axis='y', color=LINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)

def save(fig, name):
    fig.patch.set_facecolor(BG)
    path = f'{OUT_DIR}/{name}'
    fig.savefig(path, dpi=160, bbox_inches='tight',
                facecolor=BG, edgecolor='none')
    plt.close(fig)
    print(f'  saved → {path}')


# ══════════════════════════════════════════════════════════════
# 1. KV 캐시 메모리 vs 컨텍스트 길이 (로그 스케일 선 그래프)
# ══════════════════════════════════════════════════════════════
seq_lens = [512, 4096, 32768, 131072]
kv_data = {
    'MHA':   [6.29, 50.33, 402.65, 1610.61],
    'GQA-4': [3.15, 25.17, 201.33,  805.31],
    'GQA-2': [1.57, 12.58, 100.66,  402.65],
    'MQA':   [0.79,  6.29,  50.33,  201.33],
}

fig, ax = plt.subplots(figsize=(7, 4.2))
style_ax(ax,
         title='KV 캐시 메모리 — 컨텍스트 길이에 따른 폭증',
         xlabel='시퀀스 길이 (tokens)',
         ylabel='KV 캐시 크기 (MB)')

for label, vals in kv_data.items():
    ax.plot(seq_lens, vals,
            color=COLORS[label], linewidth=2.2,
            marker='o', markersize=5,
            label=label, zorder=3)

ax.set_xscale('log')
ax.set_yscale('log')
ax.set_xticks(seq_lens)
ax.get_xaxis().set_major_formatter(
    mticker.FuncFormatter(lambda x, _: f'{int(x):,}'))
ax.yaxis.set_major_formatter(
    mticker.FuncFormatter(lambda y, _: f'{y:g} MB'))
ax.legend(frameon=False, labelcolor=INK, fontsize=10)
save(fig, 'fig1_kv_cache_vs_seqlen.png')


# ══════════════════════════════════════════════════════════════
# 2. 추론 속도 (tokens/sec) — 프롬프트 길이별 그룹 막대
# ══════════════════════════════════════════════════════════════
prompt_lens = [64, 256, 1024]
speed_data = {
    'MHA':   [1329.0, 1003.9,  649.5],
    'GQA-4': [1426.7,  893.9,  613.8],
    'GQA-2': [1450.2, 1066.6,  668.3],
    'MQA':   [1557.4, 1358.7,  824.0],
}

configs  = list(speed_data.keys())
x        = np.arange(len(prompt_lens))
n        = len(configs)
w        = 0.18
offsets  = np.linspace(-(n-1)/2*w, (n-1)/2*w, n)

fig, ax = plt.subplots(figsize=(7, 4.2))
style_ax(ax,
         title='추론 속도 (tokens/sec) — 컨텍스트가 길어질수록 차이 확대',
         xlabel='프롬프트 길이 (tokens)',
         ylabel='Tokens / sec')

for i, (label, vals) in enumerate(speed_data.items()):
    bars = ax.bar(x + offsets[i], vals, width=w,
                  color=COLORS[label], label=label,
                  alpha=0.9, zorder=3)

ax.set_xticks(x)
ax.set_xticklabels([str(p) for p in prompt_lens])
ax.legend(frameon=False, labelcolor=INK, fontsize=10)
ax.yaxis.set_major_formatter(
    mticker.FuncFormatter(lambda y, _: f'{int(y):,}'))
save(fig, 'fig2_inference_speed.png')


# ══════════════════════════════════════════════════════════════
# 3. GQA-4 vs MLA Loss 수렴 비교 (선 그래프)
# ══════════════════════════════════════════════════════════════
# 100-step 구간 평균값을 구간 중앙(50, 150, 250)에 배치
steps_mid = [50, 150, 250]
loss_gqa  = [2.3232, 2.2227, 1.6234]
loss_mla  = [2.3190, 1.9628, 1.3068]

# 시작점(step=0, ≈2.35) 포함
steps_plot = [0] + steps_mid
gqa_plot   = [2.353] + loss_gqa
mla_plot   = [2.356] + loss_mla

fig, ax = plt.subplots(figsize=(7, 4.2))
style_ax(ax,
         title='학습 Loss 수렴 비교 — 동일 KV 캐시 예산',
         xlabel='학습 스텝',
         ylabel='Cross-Entropy Loss')

ax.plot(steps_plot, gqa_plot,
        color=COLORS['GQA-4'], linewidth=2.2,
        marker='o', markersize=6, label='GQA-4')
ax.plot(steps_plot, mla_plot,
        color=COLORS['MLA'],   linewidth=2.2,
        marker='s', markersize=6, label='MLA (Pure)')

# 최종 값 주석
ax.annotate(f'GQA-4: {loss_gqa[-1]:.4f}',
            xy=(250, loss_gqa[-1]),
            xytext=(210, loss_gqa[-1] + 0.08),
            color=COLORS['GQA-4'], fontsize=9,
            arrowprops=dict(arrowstyle='->', color=COLORS['GQA-4'], lw=1.2))
ax.annotate(f'MLA: {loss_mla[-1]:.4f}',
            xy=(250, loss_mla[-1]),
            xytext=(190, loss_mla[-1] - 0.15),
            color=COLORS['MLA'], fontsize=9,
            arrowprops=dict(arrowstyle='->', color=COLORS['MLA'], lw=1.2))

ax.set_xlim(-10, 310)
ax.set_xticks([0, 50, 100, 150, 200, 250, 300])
ax.legend(frameon=False, labelcolor=INK, fontsize=10)
save(fig, 'fig3_loss_convergence.png')


# ══════════════════════════════════════════════════════════════
# 4. GQA-4 vs MLA KV 캐시 크기 직접 비교 (가로 막대)
# ══════════════════════════════════════════════════════════════
cache_labels = ['GQA-4\n(n_kv_head=4)', 'MLA\n(latent_dim=32)']
cache_vals   = [131072, 32768]   # bytes (seq_len=64)
bar_colors   = [COLORS['GQA-4'], COLORS['MLA']]

fig, ax = plt.subplots(figsize=(6, 2.8))
style_ax(ax,
         title='KV 캐시 크기 직접 비교 (seq_len=64, float32)',
         xlabel='KV 캐시 크기 (bytes)')

bars = ax.barh(cache_labels, cache_vals,
               color=bar_colors, alpha=0.9,
               height=0.45, zorder=3)

# 수치 레이블
for bar, val in zip(bars, cache_vals):
    ax.text(val + 1500, bar.get_y() + bar.get_height()/2,
            f'{val:,} bytes',
            va='center', ha='left',
            fontsize=10, color=INK)

ax.set_xlim(0, 165000)
ax.xaxis.set_major_formatter(
    mticker.FuncFormatter(lambda x, _: f'{int(x):,}'))
# 감소율 텍스트
ax.text(0.98, 0.08,
        f'MLA = GQA-4의 {cache_vals[1]/cache_vals[0]*100:.0f}%\n(4배 절감)',
        transform=ax.transAxes,
        ha='right', va='bottom',
        fontsize=10, color=COLORS['MLA'],
        fontweight='bold')
ax.grid(axis='x', color=LINE, linewidth=0.8, zorder=0)
ax.grid(axis='y', visible=False)
save(fig, 'fig4_cache_comparison.png')

print('\n모든 차트 생성 완료.')
