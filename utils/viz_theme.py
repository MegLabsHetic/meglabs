"""Theme graphique partage par tous les charts Plotly de l'application.

Palette validee (accessibilite daltonisme) — ordre des couleurs fixe, ne
jamais re-ordonner : l'ordre est le mecanisme de securite CVD.
"""

import plotly.io as pio

# Palette categorielle (mode clair) — ordre fixe, jamais cycle
CATEGORICAL = [
    "#2a78d6",  # bleu
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # jaune
    "#e87ba4",  # magenta
    "#008300",  # vert
    "#4a3aa7",  # violet
    "#e34948",  # rouge
]

# Rampe sequentielle mono-teinte (magnitude continue)
SEQUENTIAL_BLUES = [
    "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
    "#256abf", "#1c5cab", "#0d366b",
]

# Echelle divergente bleu <-> rouge, point neutre gris (pour correlations)
DIVERGING_SCALE = [
    [0.0, "#0d366b"],
    [0.25, "#5598e7"],
    [0.5, "#f0efec"],
    [0.75, "#e57f7e"],
    [1.0, "#8f1f1f"],
]

INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
AXIS_LINE = "#c3c2b7"
SURFACE = "#fcfcfb"

FONT_FAMILY = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def apply_plotly_theme():
    """Applique la palette et le chrome au template plotly_white.

    Mute le template existant : tous les charts qui passent
    template="plotly_white" heritent aussi du theme.
    """
    tpl = pio.templates["plotly_white"]
    tpl.layout.colorway = CATEGORICAL
    tpl.layout.font = dict(family=FONT_FAMILY, color=INK_PRIMARY, size=13)
    tpl.layout.title = dict(font=dict(size=15, color=INK_PRIMARY))
    tpl.layout.paper_bgcolor = "rgba(0,0,0,0)"
    tpl.layout.plot_bgcolor = "rgba(0,0,0,0)"
    tpl.layout.xaxis = dict(
        gridcolor=GRIDLINE, linecolor=AXIS_LINE, zerolinecolor=AXIS_LINE,
        tickfont=dict(color=INK_MUTED),
    )
    tpl.layout.yaxis = dict(
        gridcolor=GRIDLINE, linecolor=AXIS_LINE, zerolinecolor=AXIS_LINE,
        tickfont=dict(color=INK_MUTED),
    )
    tpl.layout.legend = dict(font=dict(color=INK_SECONDARY))
    pio.templates.default = "plotly_white"
