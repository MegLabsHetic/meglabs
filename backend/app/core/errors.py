"""Erreurs destinees a l'utilisateur.

Toute erreur remontee a l'interface doit etre en francais et actionnable : elle dit ce
qui ne va pas ET ce qu'il faut faire. Un « 422 Unprocessable Entity » n'aide personne.
"""


class ErreurUtilisateur(Exception):
    """Erreur imputable a la demande, a afficher telle quelle."""

    def __init__(self, message: str, code_http: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code_http = code_http


class RessourceIntrouvable(ErreurUtilisateur):
    def __init__(self, message: str) -> None:
        super().__init__(message, code_http=404)
