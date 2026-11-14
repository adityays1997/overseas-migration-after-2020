"""Shared matplotlib settings so every chart in this repo looks the same."""

import matplotlib as mpl
import matplotlib.pyplot as plt

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SOFT = "#52514e"
GRID = "#e4e3df"
CONTEXT_GREY = "#b9b8b2"

BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
YELLOW = "#eda100"
MAGENTA = "#e87ba4"


def apply():
    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "figure.dpi": 110,
        "savefig.dpi": 150,
        "font.size": 10,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK_SOFT,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlecolor": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": INK_SOFT,
        "ytick.color": INK_SOFT,
        "legend.frameon": False,
        "lines.linewidth": 2,
    })


def source_note(fig, text):
    fig.text(0.01, 0.01, text, fontsize=8, color=INK_SOFT, ha="left", va="bottom")


def thousands(ax, axis="y"):
    fmt = mpl.ticker.FuncFormatter(lambda x, _: f"{x/1000:,.0f}k" if x else "0")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)
