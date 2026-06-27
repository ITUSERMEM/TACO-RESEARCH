from paper_plot_style import *

data = load_data()['few_shot']

fig, ax = plt.subplots(1, 1, figsize=(5, 3.2))

curves = [
    ('MAML', data['maml'], COLORS[0], 'o'),
    ('ProtoNet', data['protonet'], COLORS[1], 's'),
    ('Matching Net', data['matching_net'], COLORS[2], 'D'),
    ('TAFN (Ours)', data['tafn_ours'], OUR_COLOR, '^'),
]

for name, vals, color, marker in curves:
    ax.plot(data['shots'], vals, color=color, marker=marker, linewidth=1.5,
            markersize=5, label=name, markerfacecolor=color, markeredgewidth=0.5,
            markeredgecolor='white')

ax.set_xlabel('Number of Shots')
ax.set_ylabel('Accuracy (%)')
ax.legend(frameon=False, loc='lower right')
ax.set_ylim(45, 95)
ax.set_xticks(data['shots'])

fig.tight_layout()
save_fig(fig, 'fig6_fewshot')
