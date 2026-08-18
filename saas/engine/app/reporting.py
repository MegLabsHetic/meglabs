"""Fabrication du rapport PDF : graphiques en images + mise en page.

Les graphiques sont re-rendus ici plutot que captures depuis le navigateur :
un PDF s'imprime, et une capture d'ecran d'interface sombre en basse
resolution donne un document illisible. On reprend donc la MEME palette
validee que l'interface, sur fond clair.
"""

import io
import os
import re
from datetime import datetime

import matplotlib

matplotlib.use("Agg")  # rendu hors ecran : aucun serveur graphique ici
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_JUSTIFY, TA_RIGHT  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.graphics import renderPDF  # noqa: E402
from reportlab.graphics.shapes import (  # noqa: E402
    Circle,
    Drawing,
    Group,
    Path,
    PolyLine,
    Rect,
    String,
)
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ──────────────────────────────────────────────
# Palette : identique a `.viz-root` de globals.css, mode clair.
# L'ordre des slots est le mecanisme de surete daltonisme : ne pas reordonner.
# ──────────────────────────────────────────────
SERIE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
         "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
ENCRE = "#0f172a"
ENCRE_2 = "#475569"
ENCRE_3 = "#64748b"
GRILLE = "#e2e8f0"
AXE = "#cbd5e1"
PRIMAIRE = colors.HexColor("#0d59f2")

_ARABE_RE = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")

# Libelles de structure du document. Le corps du rapport est redige par
# l'agent dans la langue de l'utilisateur ; ces intitules-la sont fixes, il
# faut donc les traduire ici, sinon un rapport arabe garde des titres francais.
LIBELLES = {
    "fr": {
        "synthese": "Synthèse",
        "attention": "Points d'attention",
        "recommandations": "Recommandations",
        "graphiques": "Graphiques",
        "lignes": "lignes",
        "pied": "Chiffres calculés sur les données du projet",
        "page": "page",
        "titre_defaut": "Rapport d'analyse",
    },
    "en": {
        "synthese": "Summary",
        "attention": "Points of attention",
        "recommandations": "Recommendations",
        "graphiques": "Charts",
        "lignes": "rows",
        "pied": "Figures computed on the project data",
        "page": "page",
        "titre_defaut": "Analysis report",
    },
    "ar": {
        "synthese": "الملخص",
        "attention": "نقاط الانتباه",
        "recommandations": "التوصيات",
        "graphiques": "الرسوم البيانية",
        "lignes": "سطر",
        "pied": "أرقام محسوبة من بيانات المشروع",
        "page": "صفحة",
        "titre_defaut": "تقرير تحليلي",
    },
}


def libelles(langue: str) -> dict:
    return LIBELLES.get(langue, LIBELLES["fr"])


# ──────────────────────────────────────────────
# Polices
# ──────────────────────────────────────────────
def _chercher_police(*noms) -> str | None:
    racines = ["/usr/share/fonts", "/usr/local/share/fonts"]
    for racine in racines:
        for dossier, _, fichiers in os.walk(racine):
            for f in fichiers:
                if f in noms:
                    return os.path.join(dossier, f)
    return None


_POLICE_LATIN = _chercher_police("DejaVuSans.ttf")
_POLICE_LATIN_GRAS = _chercher_police("DejaVuSans-Bold.ttf")
_POLICE_ARABE = _chercher_police("NotoSansArabic-Regular.ttf", "NotoNaskhArabic-Regular.ttf")

FONT = "Helvetica"
FONT_GRAS = "Helvetica-Bold"
FONT_AR = None

if _POLICE_LATIN:
    pdfmetrics.registerFont(TTFont("DejaVu", _POLICE_LATIN))
    FONT = "DejaVu"
    if _POLICE_LATIN_GRAS:
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", _POLICE_LATIN_GRAS))
        FONT_GRAS = "DejaVu-Bold"
    else:
        FONT_GRAS = "DejaVu"

if _POLICE_ARABE:
    pdfmetrics.registerFont(TTFont("NotoArabe", _POLICE_ARABE))
    FONT_AR = "NotoArabe"
    font_manager.fontManager.addfont(_POLICE_ARABE)

if _POLICE_LATIN:
    font_manager.fontManager.addfont(_POLICE_LATIN)
    plt.rcParams["font.family"] = "DejaVu Sans"


def contient_arabe(texte: str) -> bool:
    return bool(_ARABE_RE.search(str(texte or "")))


# ──────────────────────────────────────────────
# Signe DataVox
# ──────────────────────────────────────────────
# Le signe est REDESSINE en primitives reportlab plutot qu'importe depuis le
# SVG : pas de dependance supplementaire, et le trace reste vectoriel dans le
# PDF, donc net a l'impression comme au zoom.
#
# Le trace d'origine est cadre dans une boite de 64 unites, axe Y vers le bas
# (convention SVG) ; reportlab compte l'axe Y vers le haut, d'ou la conversion.
_SIGNE_BOITE = 64.0
_BLEU_SIGNE = colors.HexColor("#2f7ce0")
_BLEU_CLAIR_SIGNE = colors.HexColor("#6db2ff")
_CYAN_SIGNE = colors.HexColor("#3fbfe0")
_FOND_SIGNE = colors.HexColor("#0b1729")


def signe(taille: float) -> Drawing:
    """Le signe seul, a la taille demandee (en points)."""
    f = taille / _SIGNE_BOITE
    d = Drawing(taille, taille)

    def y(v: float) -> float:
        return (_SIGNE_BOITE - v) * f

    def x(v: float) -> float:
        return v * f

    # Disque interieur : le signe porte son fond, il reste lisible sur blanc.
    d.add(Circle(x(32), y(29), 20 * f, fillColor=_FOND_SIGNE, strokeColor=None))

    # Queue de la bulle
    queue = Path(fillColor=_BLEU_SIGNE, strokeColor=None)
    queue.moveTo(x(23.5), y(44.5))
    queue.curveTo(x(21), y(51), x(17.5), y(55.5), x(13), y(58.5))
    queue.curveTo(x(19.5), y(56), x(26), y(52.5), x(31), y(48.5))
    queue.closePath()
    d.add(queue)

    d.add(Circle(x(32), y(29), 20 * f, fillColor=None,
                 strokeColor=_BLEU_SIGNE, strokeWidth=4.2 * f))

    # Histogramme, en retrait
    for bx, by, bh in ((20.5, 27, 12), (26, 20, 19), (31.5, 16, 23),
                       (37, 23, 16), (42.5, 18.5, 20.5)):
        d.add(Rect(x(bx), y(by + bh), 3.4 * f, bh * f, rx=1.5 * f, ry=1.5 * f,
                   fillColor=_BLEU_CLAIR_SIGNE, strokeColor=None,
                   fillOpacity=0.45))

    # Onde, au premier plan
    sommets = [(15, 29.5), (20.5, 29.5), (23.5, 21.5), (26.5, 37.5), (29.5, 15),
               (33, 42), (36.5, 22), (39.5, 32), (42, 27.5), (44.5, 29.5), (49, 29.5)]
    points = []
    for px, py in sommets:
        points += [x(px), y(py)]
    d.add(PolyLine(points, strokeColor=_CYAN_SIGNE, strokeWidth=2.6 * f,
                   strokeLineCap=1, strokeLineJoin=1))
    return d


def verrou(taille: float = 34) -> Drawing:
    """Signe + nom, pour l'en-tete du rapport."""
    hauteur = taille
    d = Drawing(260, hauteur)
    d.add(Group(signe(taille), transform=(1, 0, 0, 1, 0, 0)))
    d.add(String(taille + 10, hauteur * 0.30, "Data",
                 fontName=FONT_GRAS, fontSize=taille * 0.62,
                 fillColor=colors.HexColor(ENCRE)))
    largeur_data = pdfmetrics.stringWidth("Data", FONT_GRAS, taille * 0.62)
    d.add(String(taille + 10 + largeur_data, hauteur * 0.30, "Vox",
                 fontName=FONT_GRAS, fontSize=taille * 0.62,
                 fillColor=PRIMAIRE))
    return d


def mettre_en_forme(texte: str) -> str:
    """Prepare un texte arabe pour un moteur qui ignore le bidirectionnel.

    L'arabe s'ecrit de droite a gauche et ses lettres changent de forme selon
    leur position dans le mot. reportlab et matplotlib ne font ni l'un ni
    l'autre : sans ce passage, le texte sort a l'envers et desolidarise.
    """
    texte = str(texte or "")
    if not contient_arabe(texte):
        return texte
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(arabic_reshaper.reshape(texte))
    except Exception:
        return texte


def _police_pour(texte: str) -> str:
    return FONT_AR if (contient_arabe(texte) and FONT_AR) else FONT


# ──────────────────────────────────────────────
# Formatage des valeurs
# ──────────────────────────────────────────────
def fmt(v, format_: str = "nombre") -> str:
    if v is None:
        return "—"
    try:
        x = float(v)
    except (TypeError, ValueError):
        return str(v)
    if format_ == "pourcentage":
        p = x * 100 if abs(x) <= 1.5 else x
        return f"{p:.1f}".replace(".", ",") + " %"
    if abs(x) >= 1000:
        s = f"{round(x):,}".replace(",", " ")
    else:
        s = f"{round(x, 2):g}".replace(".", ",")
    return s + " €" if format_ == "monetaire" else s


def _fmt_axe(v, format_: str) -> str:
    a = abs(v)
    if format_ == "pourcentage":
        return f"{round(v)} %"
    if a >= 1_000_000:
        return f"{v / 1_000_000:.1f}".replace(".", ",") + " M"
    if a >= 1000:
        return f"{v / 1000:.0f}".replace(".", ",") + " k"
    return f"{round(v, 2):g}".replace(".", ",")


# ──────────────────────────────────────────────
# Graphiques
# ──────────────────────────────────────────────
def _habiller(ax):
    """Grille et axes recessifs : la donnee doit primer sur le decor."""
    ax.set_facecolor("white")
    for cote in ("top", "right"):
        ax.spines[cote].set_visible(False)
    for cote in ("left", "bottom"):
        ax.spines[cote].set_color(AXE)
        ax.spines[cote].set_linewidth(0.8)
    ax.tick_params(colors=ENCRE_3, labelsize=8, length=0)
    ax.grid(axis="y", color=GRILLE, linewidth=0.8)
    ax.set_axisbelow(True)


def _teinte(style: dict) -> str:
    """Couleur demandee, ramenee au nuancier du document.

    Le PDF est toujours sur fond blanc : on prend donc la version « mode
    clair » de la teinte nommee, celle qui a ete validee contre ce fond-la.
    """
    couleur = (style or {}).get("couleur")
    if not couleur:
        return SERIE[0]
    rang = {"bleu": 0, "orange": 1, "aqua": 2, "jaune": 3,
            "magenta": 4, "vert": 5, "violet": 6, "rouge": 7}.get(str(couleur))
    if rang is not None:
        return SERIE[rang]
    return couleur if re.match(r"^#[0-9a-fA-F]{6}$", str(couleur)) else SERIE[0]


def _extremes(valeurs: list, entourer) -> list:
    """Index des points a entourer — meme regle qu'a l'ecran."""
    if not entourer or not valeurs:
        return []
    haut = max(range(len(valeurs)), key=lambda i: valeurs[i])
    bas = min(range(len(valeurs)), key=lambda i: valeurs[i])
    if entourer == "max":
        return [haut]
    if entourer == "min":
        return [bas]
    if entourer == "extremes":
        return [haut] if haut == bas else [haut, bas]
    return []


def rendre_graphique(indicateur: dict) -> bytes | None:
    """Rend un indicateur en PNG. Renvoie None si rien n'est tracable."""
    lignes = indicateur.get("lignes") or []
    colonnes = indicateur.get("colonnes") or []
    viz = indicateur.get("viz") or "table"
    format_ = indicateur.get("format") or "nombre"
    style = indicateur.get("style") or {}

    if viz == "tuile" or len(colonnes) < 2 or not lignes:
        return None

    x_col, y_col = colonnes[0], colonnes[1]
    etiquettes = [mettre_en_forme(str(r.get(x_col, ""))) for r in lignes]
    try:
        valeurs = [float(r.get(y_col)) for r in lignes]
    except (TypeError, ValueError):
        return None
    if not valeurs:
        return None

    # Au-dela de 8 categories la queue est repliee : on ne genere jamais
    # une 9e teinte, elle serait indistinguable sous daltonisme.
    if viz in ("anneau",) and len(valeurs) > 8:
        reste = sum(valeurs[7:])
        etiquettes, valeurs = etiquettes[:7] + [f"Autres ({len(valeurs) - 7})"], valeurs[:7] + [reste]

    fig, ax = plt.subplots(figsize=(6.6, 3.1), dpi=200)
    fig.patch.set_facecolor("white")
    teinte = _teinte(style)
    # L'anneau garde ses huit teintes : ce sont elles qui separent les parts.
    entoures = _extremes(valeurs, style.get("entourer")) if viz != "anneau" else []

    if viz == "anneau":
        total = sum(valeurs) or 1
        coins, _, autotextes = ax.pie(
            valeurs,
            labels=etiquettes,
            colors=SERIE[: len(valeurs)],
            startangle=90,
            counterclock=False,
            wedgeprops={"width": 0.38, "edgecolor": "white", "linewidth": 2},
            autopct=lambda p: f"{p:.0f} %" if p >= 4 else "",
            pctdistance=0.8,
            textprops={"fontsize": 8, "color": ENCRE_2},
        )
        # Etiquettes directes : la valeur ne depend jamais de la seule couleur
        # (trois teintes de la palette passent sous 3:1 en mode clair).
        for t in autotextes:
            t.set_color("white")
            t.set_fontsize(7.5)
        ax.axis("equal")

    elif viz == "courbe":
        ax.plot(range(len(valeurs)), valeurs, color=teinte, linewidth=2)
        sommet = max(valeurs)
        for i in entoures:
            # Cercle vide pose sur le point, valeur a cote : le meme repere
            # qu'a l'ecran, pour que le rapport et le tableau de bord se
            # lisent pareil. La valeur d'un creux se pose SOUS le point —
            # au-dessus, elle tomberait sur la courbe qui remonte.
            ax.plot(i, valeurs[i], "o", markersize=11, markerfacecolor="none",
                    markeredgecolor=teinte, markeredgewidth=2)
            ax.annotate(fmt(valeurs[i], format_), (i, valeurs[i]),
                        textcoords="offset points",
                        xytext=(0, 13 if valeurs[i] == sommet else -20),
                        ha="center", fontsize=7.5, fontweight="bold", color=ENCRE)
        if style.get("etiquettes"):
            for i, v in enumerate(valeurs):
                if i not in entoures:
                    ax.annotate(fmt(v, format_), (i, v), textcoords="offset points",
                                xytext=(0, 7), ha="center", fontsize=7, color=ENCRE_2)
        ax.set_xticks(range(len(etiquettes)))
        ax.set_xticklabels(etiquettes, rotation=30, ha="right")
        ax.yaxis.set_major_formatter(lambda v, _: _fmt_axe(v, format_))
        ax.margins(y=0.16 if (entoures or style.get("etiquettes")) else 0.05)
        _habiller(ax)

    elif viz == "barres_horizontales":
        y = range(len(valeurs))
        barres = ax.barh(y, valeurs, color=teinte, height=0.62)
        for i in entoures:
            barres[i].set_edgecolor(ENCRE)
            barres[i].set_linewidth(1.6)
        if style.get("etiquettes"):
            ax.bar_label(barres, labels=[fmt(v, format_) for v in valeurs],
                         padding=3, fontsize=7, color=ENCRE_2)
        ax.set_yticks(list(y))
        ax.set_yticklabels(etiquettes)
        ax.invert_yaxis()
        ax.xaxis.set_major_formatter(lambda v, _: _fmt_axe(v, format_))
        ax.grid(axis="x", color=GRILLE, linewidth=0.8)
        ax.grid(axis="y", visible=False)
        for cote in ("top", "right"):
            ax.spines[cote].set_visible(False)
        for cote in ("left", "bottom"):
            ax.spines[cote].set_color(AXE)
            ax.spines[cote].set_linewidth(0.8)
        ax.tick_params(colors=ENCRE_3, labelsize=8, length=0)
        ax.set_axisbelow(True)

    else:  # barres, table repliee en barres
        barres = ax.bar(range(len(valeurs)), valeurs, color=teinte, width=0.62)
        for i in entoures:
            barres[i].set_edgecolor(ENCRE)
            barres[i].set_linewidth(1.6)
        if style.get("etiquettes"):
            ax.bar_label(barres, labels=[fmt(v, format_) for v in valeurs],
                         padding=3, fontsize=7, color=ENCRE_2)
        ax.set_xticks(range(len(etiquettes)))
        ax.set_xticklabels(
            etiquettes, rotation=30 if len(etiquettes) > 5 else 0,
            ha="right" if len(etiquettes) > 5 else "center",
        )
        ax.yaxis.set_major_formatter(lambda v, _: _fmt_axe(v, format_))
        _habiller(ax)

    fig.tight_layout(pad=0.6)
    tampon = io.BytesIO()
    fig.savefig(tampon, format="png", facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return tampon.getvalue()


# ──────────────────────────────────────────────
# Document
# ──────────────────────────────────────────────
def _styles(rtl: bool) -> dict:
    base = getSampleStyleSheet()
    align = TA_RIGHT if rtl else TA_JUSTIFY
    return {
        "titre": ParagraphStyle(
            "titre", parent=base["Title"], fontName=FONT_GRAS, fontSize=21,
            leading=26, textColor=colors.HexColor(ENCRE), alignment=TA_RIGHT if rtl else 0,
            spaceAfter=2,
        ),
        "sous_titre": ParagraphStyle(
            "sous_titre", parent=base["Normal"], fontName=FONT, fontSize=9,
            textColor=colors.HexColor(ENCRE_3), alignment=TA_RIGHT if rtl else 0,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName=FONT_GRAS, fontSize=13,
            leading=17, textColor=colors.HexColor(ENCRE), spaceBefore=14, spaceAfter=6,
            alignment=TA_RIGHT if rtl else 0,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"], fontName=FONT_GRAS, fontSize=10.5,
            leading=14, textColor=PRIMAIRE, spaceBefore=8, spaceAfter=3,
            alignment=TA_RIGHT if rtl else 0,
        ),
        "corps": ParagraphStyle(
            "corps", parent=base["Normal"], fontName=FONT, fontSize=9.5,
            leading=14.5, textColor=colors.HexColor(ENCRE_2), alignment=align,
        ),
        "legende": ParagraphStyle(
            "legende", parent=base["Normal"], fontName=FONT, fontSize=8,
            textColor=colors.HexColor(ENCRE_3), alignment=TA_RIGHT if rtl else 0,
        ),
    }


def _para(texte: str, style: ParagraphStyle) -> Paragraph:
    """Paragraphe avec la police adaptee au script du texte.

    Le texte vient du modele ou des donnees : il est echappe, jamais
    interprete comme du balisage. Le gras passe donc par un style, pas par
    une balise — sinon il faudrait echapper apres l'avoir ajoutee, et
    l'utilisateur verrait « <b> » en clair dans son rapport.
    """
    texte = mettre_en_forme(texte)
    if contient_arabe(texte) and FONT_AR:
        style = ParagraphStyle(f"{style.name}_ar", parent=style, fontName=FONT_AR)
    echappe = texte.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(echappe, style)


def _bandeau_chiffres(tuiles: list, st: dict) -> Table | None:
    """Les chiffres cles en tete de rapport, facon tuiles de tableau de bord."""
    if not tuiles:
        return None
    retenues = tuiles[:4]
    n = len(retenues)
    # Deux LIGNES (valeurs puis libelles), pas deux colonnes : cote a cote,
    # chaque tuile n'aurait qu'une quinzaine de millimetres et « 75 221 € »
    # se couperait en trois.
    style_valeur = ParagraphStyle(
        "valeur_tuile", parent=st["corps"], fontName=FONT_GRAS, fontSize=13.5,
        leading=17, textColor=colors.HexColor(ENCRE), alignment=0,
    )
    valeurs = [_para(fmt(t["valeur"], t.get("format")), style_valeur) for t in retenues]
    libelles = [_para(t.get("titre", ""), st["legende"]) for t in retenues]

    largeur_totale = 170 * mm
    table = Table([valeurs, libelles], colWidths=[largeur_totale / n] * n)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(GRILLE)),
        # Seulement des separateurs verticaux : une ligne horizontale
        # couperait la valeur de son libelle.
        ("LINEAFTER", (0, 0), (-2, -1), 0.6, colors.HexColor(GRILLE)),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
        ("TOPPADDING", (0, 1), (-1, 1), 0),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _tableau_valeurs(indicateur: dict, st: dict) -> Table | None:
    """Vue tableau jumelle du graphique.

    Trois teintes de la palette passent sous 3:1 en mode clair : ce tableau
    est le relief obligatoire qui garde chaque valeur lisible sans la couleur.
    """
    lignes = indicateur.get("lignes") or []
    colonnes = indicateur.get("colonnes") or []
    if len(colonnes) < 2 or not lignes:
        return None

    style_entete = ParagraphStyle(
        "entete_tableau", parent=st["legende"], fontName=FONT_GRAS,
        textColor=colors.HexColor(ENCRE_2),
    )
    corps = [[_para(c, style_entete) for c in colonnes[:2]]]
    for r in lignes[:12]:
        corps.append([
            _para(str(r.get(colonnes[0], "")), st["legende"]),
            _para(fmt(r.get(colonnes[1]), indicateur.get("format")), st["legende"]),
        ])

    table = Table(corps, colWidths=[110 * mm, 60 * mm])
    table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, colors.HexColor(AXE)),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, colors.HexColor(GRILLE)),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def construire_pdf(rapport: dict, indicateurs: list, meta: dict, langue: str = "fr") -> bytes:
    """Assemble le document final et renvoie les octets du PDF."""
    lb = libelles(langue)
    rtl = langue == "ar" or contient_arabe(
        rapport.get("titre", "") + rapport.get("synthese", "")
    )
    st = _styles(rtl)
    tampon = io.BytesIO()

    doc = SimpleDocTemplate(
        tampon, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=rapport.get("titre", lb["titre_defaut"]), author="DataVox",
    )

    # La date reste sur SA PROPRE ligne : melangee a du texte arabe, elle
    # traverse l'algorithme bidirectionnel et ses separateurs se deplacent
    # (« 2026-07-27 » devient « 27072026 »). Seule, elle ne contient aucun
    # caractere arabe, donc elle n'est pas retraitee du tout.
    sous_titre = " · ".join(
        p for p in [meta.get("projet", ""), f"{meta.get('lignes', 0)} {lb['lignes']}"] if p
    )

    fl = [
        verrou(30),
        Spacer(1, 14),
        _para(rapport.get("titre", lb["titre_defaut"]), st["titre"]),
        _para(sous_titre, st["sous_titre"]),
        _para(datetime.now().strftime("%Y-%m-%d"), st["sous_titre"]),
        Spacer(1, 10),
    ]

    tuiles = [i for i in indicateurs if i.get("viz") == "tuile" and i.get("valeur") is not None]
    bandeau = _bandeau_chiffres(tuiles, st)
    if bandeau:
        fl += [bandeau, Spacer(1, 12)]

    if rapport.get("synthese"):
        fl += [_para(lb["synthese"], st["h2"]), _para(rapport["synthese"], st["corps"])]

    for bloc in rapport.get("etat_des_lieux") or []:
        fl += [_para(bloc.get("titre", ""), st["h3"]),
               _para(bloc.get("texte", ""), st["corps"])]

    points = rapport.get("points_attention") or []
    if points:
        fl.append(_para(lb["attention"], st["h2"]))
        for p in points:
            fl += [_para(p.get("titre", ""), st["h3"]),
                   _para(p.get("texte", ""), st["corps"])]

    recos = rapport.get("recommandations") or []
    if recos:
        fl.append(_para(lb["recommandations"], st["h2"]))
        for i, r in enumerate(recos, 1):
            fl += [
                _para(f"{i}. {r.get('action', '')}", st["h3"]),
                _para(r.get("pourquoi", ""), st["corps"]),
            ]

    # ── Graphiques ────────────────────────────
    graphiques = [i for i in indicateurs if i.get("image")]
    if graphiques:
        fl += [PageBreak(), _para(lb["graphiques"], st["h2"])]
        for ind in graphiques:
            bloc = [
                _para(ind.get("titre", ""), st["h3"]),
                Image(io.BytesIO(ind["image"]), width=170 * mm, height=80 * mm,
                      kind="proportional"),
            ]
            tab = _tableau_valeurs(ind, st)
            if tab:
                bloc += [Spacer(1, 4), tab]
            fl += [KeepTogether(bloc), Spacer(1, 12)]

    def _pied(canvas, document):
        # Le pied est dessine directement sur le canevas : il echappe au
        # moteur de paragraphes, donc la mise en forme arabe et le choix de
        # police doivent etre faits a la main ici.
        mention = mettre_en_forme(f"{lb['pied']} · {lb['page']} {document.page}")
        canvas.saveState()
        # Signe en pied de page : un rapport transmis hors de l'outil doit
        # rester identifiable, page par page.
        renderPDF.draw(signe(11), canvas, 20 * mm, 8.2 * mm)
        canvas.setFillColor(colors.HexColor(ENCRE_3))
        canvas.setFont(FONT_GRAS, 7.5)
        canvas.drawString(20 * mm + 14, 10 * mm, "DataVox")
        canvas.setFont(_police_pour(mention), 7.5)
        canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, mention)
        canvas.restoreState()

    doc.build(fl, onFirstPage=_pied, onLaterPages=_pied)
    return tampon.getvalue()
