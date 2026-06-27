import matplotlib.pyplot as plt
import matplotlib
import json
import os

matplotlib.rcParams.update({
    'font.size': 10,
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'Times', 'DejaVu Serif'],
    'axes.labelsize': 10,
    'axes.titlesize': 11,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.05,
    'axes.grid': False,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'text.usetex': False,
    'mathtext.fontset': 'stix',
})

COLORS = plt.cm.tab10.colors
OUR_COLOR = '#E74C3C'
MARKERS = ['o', 's', 'D', '^', 'v']
FIG_DIR = os.path.dirname(os.path.abspath(__file__))

def load_data():
    with open(os.path.join(FIG_DIR, 'exp_results.json')) as f:
        return json.load(f)

def save_fig(fig, name):
    path = os.path.join(FIG_DIR, f'{name}.pdf')
    fig.savefig(path)
    print(f'Saved: {path}')
    plt.close(fig)
