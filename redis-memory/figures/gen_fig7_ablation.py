from paper_plot_style import *

data = load_data()['ablation']

fig, ax = plt.subplots(1, 1, figsize=(5, 3.2))
components = data['components']
acc = data['accuracy']
std = data['std']

gradient_colors = ['#3498DB', '#2ECC71', '#F39C12', '#E67E22', '#E74C3C']

bars = ax.bar(components, acc, yerr=std, capsize=3, color=gradient_colors,
              width=0.6, linewidth=0.8, edgecolor='white')

for bar, val, comp in zip(bars, acc, components):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.2,
            f'{val:.1f}', ha='center', va='bottom', fontsize=8)

ax.set_ylabel('Accuracy (%)')
ax.set_xticks(range(len(components)))
ax.set_xticklabels(components, rotation=15, ha='right', fontsize=8)
ax.set_ylim(70, 100)

fig.tight_layout()
save_fig(fig, 'fig7_ablation')
