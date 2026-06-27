from paper_plot_style import *
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

fig, ax = plt.subplots(1, 1, figsize=(10, 8))
ax.set_xlim(0, 12)
ax.set_ylim(0, 10)
ax.axis('off')

C_TEMP = '#2980B9'
C_SPEC = '#C0392B'
C_PHY = '#27AE60'
C_FUS = '#8E44AD'
C_META = '#D4AC0D'
C_DARK = '#2C3E50'
C_GRAY = '#95A5A6'
C_LIGHT = '#ECF0F1'

BOX_KW = dict(boxstyle="round,pad=0.12", linewidth=1.2, edgecolor='#2C3E50')

def draw_rounded(ax, x, y, w, h, color, text, subtext=None, fs=9, sfs=7, tc='white'):
    box = FancyBboxPatch((x, y), w, h, **BOX_KW, facecolor=color)
    ax.add_patch(box)
    ax.text(x + w/2, y + h/2 + (0.06 if subtext else 0), text,
            ha='center', va='center', fontsize=fs, color=tc, fontweight='bold')
    if subtext:
        ax.text(x + w/2, y + h/2 - 0.25, subtext,
                ha='center', va='top', fontsize=sfs, color=tc, alpha=0.9)

def arrow(ax, x1, y1, x2, y2, color='#555555', lw=1.8):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw))

# ===================== INPUT =====================
r = FancyBboxPatch((4.5, 9.1), 3.0, 0.55, **BOX_KW, facecolor=C_GRAY)
ax.add_patch(r)
ax.text(6.0, 9.375, 'Raw Vibration Signal $x^t$', ha='center', va='center',
        fontsize=10, color='white', fontweight='bold')

# ===================== BRANCH LABELS =====================
ax.text(1.5, 8.7, 'Temporal Branch (1D)', ha='center', fontsize=8,
        fontweight='bold', color=C_TEMP, style='italic')
ax.text(6.0, 8.7, 'Spectral Branch (2D)', ha='center', fontsize=8,
        fontweight='bold', color=C_SPEC, style='italic')
ax.text(10.5, 8.7, 'Physics Prior', ha='center', fontsize=8,
        fontweight='bold', color=C_PHY, style='italic')

# Arrows from input
arrow(ax, 6.0, 9.1, 1.5 + 2/2, 8.2)
arrow(ax, 6.0, 9.1, 6.0, 8.2)
arrow(ax, 6.0, 9.1, 10.5 - 2/2, 8.2)

# ===================== ROW 1: Feature Extraction =====================

# 1D Temporal Encoder
draw_rounded(ax, 0.3, 7.3, 2.4, 0.7, C_TEMP,
             '1D Temporal Encoder',
             'Dilated Conv (rates 1,2,4,8)')
draw_rounded(ax, 0.3, 6.4, 2.4, 0.6, C_TEMP,
             'BN + GELU + GAP',
             'Multi-scale temporal features')
arrow(ax, 1.5, 7.3, 1.5, 7.0)

# 2D Spectral Encoder
draw_rounded(ax, 4.8, 7.3, 2.4, 0.7, C_SPEC, 'Mel-Spectrogram', 'STFT  Mel  Log')
draw_rounded(ax, 4.8, 6.4, 2.4, 0.6, C_SPEC,
             '2D CNN + SE Attention',
             'Frequency band features')
arrow(ax, 6.0, 7.3, 6.0, 7.0)

# Physics Prior
draw_rounded(ax, 9.6, 7.3, 2.1, 0.7, C_PHY,
             'Statistical Metrics',
             'Var, Skew, Kurt, CLF')
draw_rounded(ax, 9.6, 6.4, 2.1, 0.6, C_PHY,
             'MLP Projection',
             'Physics bias vector')
arrow(ax, 10.65, 7.3, 10.65, 7.0)

# ===================== ROW 2: Encoding =====================
draw_rounded(ax, 0.5, 5.3, 2.0, 0.5, C_TEMP,
             'Temporal Feature $f_t$', fs=9)
draw_rounded(ax, 5.0, 5.3, 2.0, 0.5, C_SPEC,
             'Spectral Feature $f_s$', fs=9)
draw_rounded(ax, 9.6, 5.3, 2.1, 0.5, C_PHY,
             'Physics Prior $p$', fs=9)

arrow(ax, 1.5, 6.4, 1.5, 5.8)
arrow(ax, 6.0, 6.4, 6.0, 5.8)
arrow(ax, 10.65, 6.4, 10.65, 5.8)

# ===================== FUSION =====================
# Fusion box
r2 = FancyBboxPatch((2.0, 3.4), 8.0, 1.0, **BOX_KW, facecolor=C_FUS)
ax.add_patch(r2)
ax.text(6.0, 4.15, 'Physics-Guided Cross-Modal Fusion', ha='center', va='center',
        fontsize=10, color='white', fontweight='bold')
ax.text(6.0, 3.75, 'Cross-Attention(Q, K_t, K_s) x V  +  Physics Bias Injection',
        ha='center', va='center', fontsize=8, color='white', alpha=0.9)

# Fusion arrow connections
arrow(ax, 1.5, 5.3, 3.5, 4.4)
arrow(ax, 6.0, 5.3, 6.0, 4.4)
arrow(ax, 10.65, 5.3, 8.5, 4.4)

# ===================== FUSED FEATURE =====================
draw_rounded(ax, 4.3, 2.6, 3.4, 0.5, C_DARK,
             'Fused Representation $f_{fus}$', fs=10)
arrow(ax, 6.0, 3.4, 6.0, 3.1)

# ===================== META-LEARNING =====================
r3 = FancyBboxPatch((1.0, 1.0, 6.0, 0.9), **BOX_KW, facecolor=C_META)
ax.add_patch(r3)
ax.text(4.0, 1.65, 'Entropy-Regularized Meta-Learning', ha='center', va='center',
        fontsize=10, color='white', fontweight='bold')
ax.text(4.0, 1.25, 'Prototypical Network  +  $\\mathcal{L}_{total} = \\mathcal{L}_{CE} + \\lambda \\cdot H(P(y|x))$',
        ha='center', va='center', fontsize=8, color='white')

arrow(ax, 6.0, 2.6, 4.5, 1.9)

# ===================== OUTPUT =====================
r4 = FancyBboxPatch((8.5, 1.0, 3.0, 0.9), **BOX_KW, facecolor=C_DARK)
ax.add_patch(r4)
ax.text(10.0, 1.65, '6-Class Diagnosis', ha='center', va='center',
        fontsize=10, color='white', fontweight='bold')
ax.text(10.0, 1.25, 'NO / IR / OR / BF / CF / CM',
        ha='center', va='center', fontsize=8, color='white', alpha=0.9)

arrow(ax, 7.0, 1.45, 8.5, 1.45)

# ===================== ACC =====================
ax.text(10.0, 0.5, 'Accuracy: 92.1%', ha='center', fontsize=12,
        fontweight='bold', color=C_DARK)

# ===================== LEGEND =====================
legends = [
    mpatches.Patch(color=C_TEMP, label='Temporal'),
    mpatches.Patch(color=C_SPEC, label='Spectral'),
    mpatches.Patch(color=C_PHY, label='Physics Prior'),
    mpatches.Patch(color=C_FUS, label='Fusion'),
    mpatches.Patch(color=C_META, label='Meta-Learning'),
]
ax.legend(handles=legends, loc='lower right', frameon=True,
          edgecolor=C_GRAY, fontsize=8, ncol=3,
          bbox_to_anchor=(0.98, 0.02))

fig.tight_layout()
plt.subplots_adjust(left=0.01, right=0.99, top=0.98, bottom=0.02)
save_fig(fig, 'fig1_architecture')
