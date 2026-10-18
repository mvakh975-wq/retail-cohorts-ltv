"""Единый стиль графиков: один акцентный цвет, серый для контекста, приглушённые оси."""

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

ACCENT = "#2a78d6"
CONTEXT = "#c9c8c2"
TEXT = "#0b0b0b"
MUTED = "#52514e"


def apply() -> None:
    mpl.rcParams.update(
        {
            "figure.dpi": 110,
            "savefig.dpi": 160,
            "savefig.bbox": "tight",
            "font.size": 10.5,
            "axes.titlesize": 12.5,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.titlepad": 12,
            "axes.labelcolor": MUTED,
            "axes.edgecolor": CONTEXT,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": "#ebeae6",
            "grid.linewidth": 0.8,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "text.color": TEXT,
            "legend.frameon": False,
            "lines.linewidth": 2,
        }
    )


def rub(x: float, _pos=None) -> str:
    return f"{x:,.0f} ₽".replace(",", " ")


def pct(x: float, _pos=None) -> str:
    return f"{x:.0%}"


RUB = FuncFormatter(rub)
PCT = FuncFormatter(pct)


def finish(fig: plt.Figure, path=None) -> None:
    fig.tight_layout()
    if path is not None:
        fig.savefig(path)


def num(x: float, digits: int = 0) -> str:
    """Число в русской записи: пробел между разрядами, запятая перед дробной частью."""
    return f"{x:,.{digits}f}".replace(",", " ").replace(".", ",")


def gbp(x: float, _pos=None) -> str:
    return f"−£{num(-x)}" if x < 0 else f"£{num(x)}"


GBP = FuncFormatter(gbp)
