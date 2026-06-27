from paper_plot_style import *
import numpy as np

data = load_data()['confusion']
labels = data['true_labels']
cm = np.array([data['predicted'][l] for l in labels])
cm_perc = cm.astype('float') / cm.sum(axis=1, keepdims=True) * 100

fig, ax = plt.subplots(1, 1, figsize=(4.8, 4.2))

im = ax.imshow(cm, cmap='Blues', aspect='equal', vmin=0, vmax=100)
cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
cbar.set_label('Samples')

ax.set_xticks(range(len(labels)))
ax.set_yticks(range(len(labels)))
ax.set_xticklabels(labels, rotation=25, ha='right', fontsize=8)
ax.set_yticklabels(labels, fontsize=8)
ax.set_xlabel('Predicted Label')
ax.set_ylabel('True Label')

for i in range(len(labels)):
    for j in range(len(labels)):
        val = cm[i, j]
        pct = cm_perc[i, j]
        color = 'white' if val > 50 else 'black'
        ax.text(j, i, f'{val}\n({pct:.0f}%)', ha='center', va='center',
                fontsize=7, color=color, fontweight='bold' if i == j else 'normal')

fig.tight_layout()
save_fig(fig, 'fig4_confusion')
