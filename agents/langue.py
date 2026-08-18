"""Detection de la langue de l'utilisateur — en code, pas par le modele.

Demander au modele « reponds dans la langue de la question » ne suffit pas :
la question est noyee dans un contexte redige en francais (consignes, schema,
libelles), et le modele suit la langue dominante. On tranche donc ici, et on
lui donne un ordre explicite.

Trois langues visees : francais, anglais, arabe.
"""

import re

FRANCAIS = "fr"
ANGLAIS = "en"
ARABE = "ar"

# Blocs Unicode arabes (arabe, supplement, formes de presentation)
_ARABE_RE = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")

# Mots outils : frequents, courts, et surtout absents de l'autre langue.
_MOTS_FR = {
    "le", "la", "les", "un", "une", "des", "du", "de", "et", "est", "sont",
    "quel", "quelle", "quels", "quelles", "combien", "pourquoi", "comment",
    "par", "pour", "dans", "sur", "avec", "sans", "plus", "moins", "moyenne",
    "chiffre", "affaires", "ventes", "montre", "donne", "ajoute", "enleve",
    "supprime", "calcule", "repartition", "evolution", "taux", "meilleur",
    "ca", "cette", "ce", "mes", "mon", "ma", "nos", "notre", "qui", "que",
}
_MOTS_EN = {
    "the", "a", "an", "of", "and", "is", "are", "was", "were", "what", "which",
    "how", "many", "much", "why", "who", "by", "for", "in", "on", "with",
    "without", "more", "less", "average", "revenue", "sales", "show", "give",
    "add", "remove", "delete", "compute", "breakdown", "trend", "rate", "best",
    "top", "my", "our", "this", "that", "per", "total", "count",
}

_MOT_RE = re.compile(r"[a-zà-ÿœæ']+", re.IGNORECASE)


def detect(texte: str, defaut: str = FRANCAIS) -> str:
    """Renvoie 'fr', 'en' ou 'ar'. `defaut` sert quand rien ne tranche."""
    if not texte or not texte.strip():
        return defaut

    # L'ecriture arabe est sans ambiguite : sa seule presence suffit.
    if _ARABE_RE.search(texte):
        return ARABE

    mots = [m.lower() for m in _MOT_RE.findall(texte)]
    if not mots:
        return defaut

    score_fr = sum(1 for m in mots if m in _MOTS_FR)
    score_en = sum(1 for m in mots if m in _MOTS_EN)

    # Les accents et l'apostrophe elidee sont des marqueurs francais forts,
    # mais ils ne doivent pas ecraser un decompte net cote anglais.
    if re.search(r"[àâäéèêëîïôöùûüç]|\b[ldjmnstc]'", texte, re.IGNORECASE):
        score_fr += 2

    if score_fr > score_en:
        return FRANCAIS
    if score_en > score_fr:
        return ANGLAIS
    return defaut


_DIRECTIVES = {
    FRANCAIS: (
        "LANGUE DE REPONSE IMPOSEE : FRANCAIS.\n"
        "Redige tous les textes destines a l'utilisateur en francais."
    ),
    ANGLAIS: (
        "REQUIRED OUTPUT LANGUAGE: ENGLISH.\n"
        "Write every user-facing text (answer, title, description, suggestions, "
        "explanation) in ENGLISH. The instructions you received are written in "
        "French for internal reasons — ignore that completely and answer in English."
    ),
    ARABE: (
        "لغة الإجابة المطلوبة: العربية.\n"
        "اكتب جميع النصوص الموجهة للمستخدم بالعربية. التعليمات مكتوبة بالفرنسية "
        "لأسباب داخلية، تجاهل ذلك تماما وأجب بالعربية."
    ),
}


def directive(code: str) -> str:
    """Bloc a placer en tete du contexte, dans la langue cible."""
    return _DIRECTIVES.get(code, _DIRECTIVES[FRANCAIS])


def directive_pour(texte: str, defaut: str = FRANCAIS) -> str:
    """Raccourci : detecte puis renvoie la directive correspondante."""
    return directive(detect(texte, defaut))
