from paper_plot_style import *

data = load_data()['noise_robustness']

fig, ax = plt.subplots(1, 1, figsize=(5, 3.2))

curves = [
    ('CNN', data['cnn'], COLORS[0], 'o'),
    ('ResNet', data['resnet'], COLORS[1], 's'),
    ('ViT', data['vit'], COLORS[2], 'D'),
    ('TAFN (Ours)', data['tafn_ours'], OUR_COLOR, '^'),
]

for name, vals, color, marker in curves:
    ax.plot(data['snr_db'], vals, color=color, marker=marker, linewidth=1.5,
            markersize=5, label=name, markerfacecolor=color, markeredgewidth=0.5,
            markeredgecolor='white')

ax.set_xlabel('SNR (dB)')
ax.set_ylabel('Accuracy (%)')
ax.legend(frameon=False, loc='lower right')
ax.set_ylim(40, 100)
ax.invert_xaxis()

fig.tight_layout()
save_fig(fig, 'fig5_noise_robustness')
