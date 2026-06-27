from paper_plot_style import *

data = load_data()['training']

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.5, 2.8))

ax1.plot(data['steps'], data['train_acc'], color=COLORS[0], linewidth=1.5, label='Train')
ax1.plot(data['steps'], data['val_acc'], color=COLORS[1], linewidth=1.5, linestyle='--', label='Validation')
ax1.set_xlabel('Training Steps')
ax1.set_ylabel('Accuracy')
ax1.legend(frameon=False, loc='lower right')
ax1.set_ylim(0.2, 1.0)
ax1.text(-0.12, 1.02, '(a)', transform=ax1.transAxes, fontsize=10, fontweight='bold', va='bottom', ha='left')

ax2.plot(data['steps'], data['train_loss'], color=COLORS[0], linewidth=1.5, label='Train')
ax2.plot(data['steps'], data['val_loss'], color=COLORS[1], linewidth=1.5, linestyle='--', label='Validation')
ax2.set_xlabel('Training Steps')
ax2.set_ylabel('Loss')
ax2.legend(frameon=False, loc='upper right')
ax2.set_ylim(0, 2.5)
ax2.text(-0.12, 1.02, '(b)', transform=ax2.transAxes, fontsize=10, fontweight='bold', va='bottom', ha='left')

fig.tight_layout()
save_fig(fig, 'fig2_training_curves')
