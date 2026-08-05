"""
gen_figures_gqa.py — GQA 블로그 포스트용 matplotlib 차트 4개 생성
출력: pages/posts-assets/attention-is-all-you-need-kv-cache-gqa/*.png
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ── 한국어 폰트 ───────────────────────────────────────────────
plt.rcParams['font.family'] = 'Apple SD Gothic Neo'
plt.rcParams['axes.unicode_minus'] = False

OUT_DIR = 'pages/posts-assets/attention-is-all-you-need-kv-cache-gqa'
os.makedirs(OUT_DIR, exist_ok=True)

# ── 디자인 토큰 ───────────────────────────────────────────────
INK      = '#10131A'
INK_SOFT = '#5B6270'
LINE     = '#E7E9EE'
BG       = '#FFFFFF'
BG_SOFT  = '#F6F7F9'

COLORS = {
    'MHA':    '#10131A',
    'GQA-8':  '#2563EB',
    'GQA-4':  '#4A6FA5',
    'GQA-2':  '#70A37F',
    'MQA':    '#C87941',
}

def style_ax(ax, title='', xlabel='', ylabel=''):
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
    if xlabel: ax.set_xlabel(xlabel, labelpad=8)
    if ylabel: ax.set_ylabel(ylabel, labelpad=8)
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
# 1. LLaMA-7B KV 캐시 폭증 — 컨텍스트 길이별 (2부 표 데이터)
#    계산: 2 × 32 레이어 × seq_len × KV헤드 × head_dim(128) × 2bytes(fp16) / 1e9
# ══════════════════════════════════════════════════════════════
seq_lens   = [2048, 8192, 32768, 128000]
seq_labels = ['2K', '8K', '32K', '128K']

def llama_cache_gb(seq, n_kv):
    return 2 * 32 * seq * n_kv * 128 * 2 / 1e9

kv_configs = {'MHA (32)': 32, 'GQA-8': 8, 'GQA-4': 4, 'MQA (1)': 1}
kv_colors  = ['#10131A', '#2563EB', '#4A6FA5', '#C87941']

fig, ax = plt.subplots(figsize=(7, 4.2))
style_ax(ax,
         title='LLaMA-7B 기준 KV 캐시 크기 — 컨텍스트 길이에 따른 폭증',
         xlabel='시퀀스 길이',
         ylabel='KV 캐시 크기 (GB)')

for (label, n_kv), col in zip(kv_configs.items(), kv_colors):
    vals = [llama_cache_gb(s, n_kv) for s in seq_lens]
    ax.plot(seq_labels, vals,
            color=col, linewidth=2.2,
            marker='o', markersize=5, label=label, zorder=3)

# 128K 기준 주석
for (label, n_kv), col in zip(kv_configs.items(), kv_colors):
    val = llama_cache_gb(128000, n_kv)
    ax.annotate(f'{val:.1f} GB',
                xy=(3, val),
                xytext=(3.05, val),
                color=col, fontsize=9,
                va='center')

ax.axhline(y=80, color='#E74C3C', linewidth=1, linestyle='--', alpha=0.6, zorder=2)
ax.text(0.01, 80 + 0.5, 'A100 80GB VRAM', color='#E74C3C',
        fontsize=8.5, transform=ax.get_yaxis_transform())

ax.legend(frameon=False, labelcolor=INK, fontsize=10)
ax.set_xlim(-0.3, 3.6)
save(fig, 'fig1_llama7b_kv_cache.png')


# ══════════════════════════════════════════════════════════════
# 2. numpy 복사 시간 프록시 (4부 표 데이터)
# ══════════════════════════════════════════════════════════════
proxy_configs = ['MHA\n(n_kv=32)', 'GQA-8\n(n_kv=8)', 'GQA-4\n(n_kv=4)', 'MQA\n(n_kv=1)']
proxy_times   = [27.64, 5.88, 0.92, 0.17]
proxy_colors  = ['#10131A', '#2563EB', '#4A6FA5', '#C87941']

fig, ax = plt.subplots(figsize=(6.5, 4))
style_ax(ax,
         title='numpy 복사 시간 프록시 — KV 헤드 수에 거의 선형 비례',
         xlabel='구성',
         ylabel='스텝당 평균 복사 시간 (ms, seq=4096)')

bars = ax.bar(proxy_configs, proxy_times,
              color=proxy_colors, alpha=0.9, width=0.5, zorder=3)

for bar, val in zip(bars, proxy_times):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
            f'{val} ms', ha='center', va='bottom',
            fontsize=10, color=INK, fontweight='600')

ax.set_ylim(0, 33)
save(fig, 'fig2_numpy_proxy_timing.png')


# ══════════════════════════════════════════════════════════════
# 3. 추론 속도 비교 (5-2부 표 데이터, 모든 프롬프트 길이)
# ══════════════════════════════════════════════════════════════
speed_configs = {'MHA': [186.2, 133.6, 67.6],
                 'GQA-4': [174.6, 132.9, 56.2],
                 'GQA-2': [197.1, 158.2, 70.3],
                 'MQA':   [182.1, 174.5, 110.5]}
prompt_labels = ['64', '256', '1024']

x       = np.arange(len(prompt_labels))
n_bars  = len(speed_configs)
w       = 0.18
offsets = np.linspace(-(n_bars-1)/2*w, (n_bars-1)/2*w, n_bars)
sp_colors = [COLORS['MHA'], COLORS['GQA-4'], COLORS['GQA-2'], COLORS['MQA']]

fig, ax = plt.subplots(figsize=(7, 4.2))
style_ax(ax,
         title='추론 속도 (tokens/sec) — 컨텍스트 1024에서 MQA가 MHA 대비 1.6×',
         xlabel='프롬프트 길이 (tokens)',
         ylabel='Tokens / sec')

for i, (label, vals) in enumerate(speed_configs.items()):
    ax.bar(x + offsets[i], vals, width=w,
           color=sp_colors[i], label=label, alpha=0.9, zorder=3)

# 1024 기준 화살표로 MQA vs MHA 강조
ax.annotate('', xy=(x[2] + offsets[-1], 110.5), xytext=(x[2] + offsets[0], 67.6),
            arrowprops=dict(arrowstyle='<->', color='#E74C3C', lw=1.5))
ax.text(x[2] + 0.08, 90, '1.6×', color='#E74C3C', fontsize=10, fontweight='bold')

ax.set_xticks(x)
ax.set_xticklabels(prompt_labels)
ax.legend(frameon=False, labelcolor=INK, fontsize=10)
save(fig, 'fig3_inference_speed.png')


# ══════════════════════════════════════════════════════════════
# 4. 학습 sanity check Loss 비교 (5-3부)
# ══════════════════════════════════════════════════════════════
sanity_labels = ['MHA\n(n_kv=4)', 'GQA-2\n(n_kv=2)', 'MQA\n(n_kv=1)']
start_losses  = [2.323, 2.334, 2.329]
final_losses  = [1.034, 1.207, 1.091]
sanity_colors = ['#10131A', '#70A37F', '#C87941']

x2 = np.arange(len(sanity_labels))
w2 = 0.32

fig, ax = plt.subplots(figsize=(6.5, 4.2))
style_ax(ax,
         title='300 스텝 학습 sanity check — 모두 정상 수렴',
         xlabel='구성',
         ylabel='Cross-Entropy Loss')

bars_s = ax.bar(x2 - w2/2, start_losses, width=w2,
                color='#E2E5EB', label='시작 Loss (30-step avg)', zorder=3)
bars_f = ax.bar(x2 + w2/2, final_losses, width=w2,
                color=sanity_colors, label='최종 Loss (마지막 30-step avg)', alpha=0.9, zorder=3)

for bar, val in zip(bars_f, final_losses):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
            f'{val:.3f}', ha='center', va='bottom',
            fontsize=10, color=INK, fontweight='600')

# 이론 Loss 기준선
ax.axhline(y=2.303, color=INK_SOFT, linewidth=1, linestyle='--', alpha=0.7)
ax.text(0.01, 2.32, 'ln(10) ≈ 2.303  (무작위 예측 수준)',
        color=INK_SOFT, fontsize=8.5, transform=ax.get_yaxis_transform())

ax.set_xticks(x2)
ax.set_xticklabels(sanity_labels)
ax.set_ylim(0, 2.8)
ax.legend(frameon=False, labelcolor=INK, fontsize=10, loc='upper right')
save(fig, 'fig4_loss_sanity.png')


print('\n모든 GQA 차트 생성 완료.')
