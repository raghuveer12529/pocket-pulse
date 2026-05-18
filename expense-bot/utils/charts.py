from io import BytesIO
import matplotlib
matplotlib.use("Agg")  # non-interactive backend, must be set before pyplot import
import matplotlib.pyplot as plt

CATEGORY_COLORS = {
    "Food": "#FF6B6B",
    "Transport": "#4ECDC4",
    "Shopping": "#45B7D1",
    "Health": "#96CEB4",
    "Bills": "#FFEAA7",
    "Entertainment": "#DDA0DD",
    "Other": "#B0B0B0",
}

def generate_pie_chart(data: dict[str, float], month_label: str) -> BytesIO:
    if not data:
        raise ValueError("No data to chart.")
    labels = list(data.keys())
    sizes = list(data.values())
    colors = [CATEGORY_COLORS.get(lbl, "#B0B0B0") for lbl in labels]

    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        colors=colors,
        autopct="%1.0f%%",
        startangle=140,
        pctdistance=0.82,
    )
    for at in autotexts:
        at.set_fontsize(9)
    ax.set_title(f"Spending — {month_label}", fontsize=14, pad=20)
    plt.tight_layout()

    bio = BytesIO()
    fig.savefig(bio, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    bio.seek(0)
    return bio
