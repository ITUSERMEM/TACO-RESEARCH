from paper_plot_style import *
import numpy as np

data = load_data()['comparison']

fig, ax = plt.subplots(1, 1, figsize=(5, 3.2))
methods = data['methods']
acc = data['accuracy']
std = data['std']

bar_colors = [COLORS[i] for i in range(len(methods))]
bar_colors[-1] = OUR_COLOR

bars = ax.bar(methods, acc, yerr=std, capsize=3, color=bar_colors,
              width=0.6, linewidth=0.8, edgecolor='white')

for bar, val in zip(bars, acc):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
            f'{val:.1f}', ha='center', va='bottom', fontsize=8)

ax.set_ylabel('Accuracy (%)')
ax.set_xticks(range(len(methods)))
ax.set_xticklabels(methods, rotation=15, ha='right', fontsize=8)
ax.set_ylim(0, 100)

fig.tight_layout()
save_fig(fig, 'fig3_comparison')
