# fmt — Module Python pour les fichiers .fmt
# Copyright (C) 2026 bono-p
#
# Ce fichier fait partie du module fmt.
#
# Le module fmt est un logiciel libre ; vous pouvez le redistribuer
# et/ou le modifier selon les termes de la GNU Lesser General Public
# License telle que publiée par la Free Software Foundation, version 3
# de la Licence, ou (à votre option) toute version ultérieure.
#
# Ce module est distribué dans l'espoir qu'il sera utile, mais SANS
# AUCUNE GARANTIE. Voir la GNU LGPL pour plus de détails.
#
# Vous devez avoir reçu une copie de la GNU LGPL avec ce module.
# Sinon : <https: //www.gnu.org/licenses/lgpl-3.0.html>
  



"""
fmt/exceptions.py — Hiérarchie complète des exceptions .fmt v2

Toutes les exceptions héritent de FMTError pour permettre un
bloc except FMTError: générique, tout en restant attrapables
individuellement avec précision.

Arbre d'héritage :
    FMTError
    ├── FMTSyntaxError          erreur de syntaxe (avec ligne réelle)
    ├── FMTFileError            lecture/écriture impossible
    ├── FMTSectionNotFoundError section introuvable
    ├── FMTEntryNotFoundError   clé introuvable dans une section
    ├── FMTDuplicateSectionError section déjà existante
    ├── FMTDepthError           profondeur maximale dépassée
    ├── FMTTypeError            type inattendu sur une valeur
    └── FMTPathError            chemin de navigation invalide
"""

from __future__ import annotations


class FMTError(Exception):
    """Exception de base du module fmt. Toutes les erreurs fmt en héritent."""
    pass


class FMTSyntaxError(FMTError):
    """
    Erreur de syntaxe dans un fichier .fmt.

    Fournit systématiquement :
      - le numéro de ligne RÉEL dans le fichier original (pas la ligne prétraitée)
      - le contenu de la ligne fautive
      - un hint optionnel pour guider la correction

    Exemple :
        Ligne 14 ('port' : abc def) — Clé dupliquée dans 'config'
        💡 Les valeurs non quotées ne peuvent pas contenir d'espaces.
    """

    def __init__(
        self,
        message: str,
        line_number: int | None = None,
        line_content: str | None = None,
        hint: str | None = None,
    ):
        self.line_number  = line_number
        self.line_content = line_content
        self.hint         = hint

        parts: list[str] = []
        if line_number is not None:
            loc = f"Ligne {line_number}"
            if line_content is not None:
                loc += f" ({line_content!r})"
            parts.append(loc)
        parts.append(message)

        full = " — ".join(parts)
        if hint:
            full += f"\n  💡 {hint}"

        super().__init__(full)


class FMTFileError(FMTError):
    """
    Erreur lors de l'accès à un fichier .fmt (lecture ou écriture).

    Attributs :
        path   : chemin du fichier concerné
        reason : raison de l'échec
    """

    def __init__(self, path: str, reason: str):
        self.path   = path
        self.reason = reason
        super().__init__(f"Impossible d'accéder à '{path}' : {reason}")


class FMTSectionNotFoundError(FMTError):
    """
    Section ou sous-section introuvable.

    Attributs :
        name      : nom de la section demandée
        available : liste des sections disponibles au même niveau
        path      : chemin complet tenté (si navigation imbriquée)
    """

    def __init__(
        self,
        name: str,
        available: list[str] | None = None,
        *,
        path: str | None = None,
    ):
        self.name      = name
        self.available = available or []
        self.path      = path

        msg = f"Section '{name}' introuvable."
        if path and path != name:
            msg += f" (chemin : '{path}')"
        if self.available:
            msg += f" Disponibles : [{', '.join(repr(a) for a in self.available)}]"
        else:
            msg += " Aucune section disponible à ce niveau."

        super().__init__(msg)


class FMTEntryNotFoundError(FMTError):
    """
    Clé introuvable dans une section.

    Attributs :
        key          : clé demandée
        section_name : nom de la section inspectée
    """

    def __init__(self, key: str, section_name: str):
        self.key          = key
        self.section_name = section_name
        super().__init__(
            f"Clé '{key}' introuvable dans la section '{section_name}'."
        )


class FMTDuplicateSectionError(FMTError):
    """
    Tentative de création d'une section déjà existante.

    Attributs :
        name   : nom en conflit
        parent : nom de la section parente (None si niveau racine)
    """

    def __init__(self, name: str, parent: str | None = None):
        self.name   = name
        self.parent = parent
        where = f" dans '{parent}'" if parent else " (niveau racine)"
        super().__init__(
            f"La section '{name}' existe déjà{where}. "
            f"Utilisez .section('{name}').set(...) pour modifier son contenu."
        )


class FMTDepthError(FMTError):
    """
    Profondeur maximale d'imbrication dépassée.

    Levée quand on tente de créer une sous-section à un niveau
    supérieur au max_depth configuré à l'ouverture du document.

    Attributs :
        name          : nom de la sous-section qu'on voulait créer
        current_depth : profondeur actuelle (là où l'erreur survient)
        max_depth     : profondeur maximale autorisée

    Exemple de message :
        Impossible de créer 'timeout' à la profondeur 3 (max autorisé : 3).
        💡 Augmentez max_depth lors du chargement : fmt.load("f.fmt", max_depth=5)
    """

    def __init__(self, name: str, current_depth: int, max_depth: int):
        self.name          = name
        self.current_depth = current_depth
        self.max_depth     = max_depth
        super().__init__(
            f"Impossible de créer la sous-section '{name}' à la profondeur "
            f"{current_depth} : maximum autorisé = {max_depth}.\n"
            f"  💡 Augmentez max_depth à l'ouverture : "
            f"fmt.load(\"fichier.fmt\", max_depth={max_depth + 1})"
        )


class FMTTypeError(FMTError):
    """
    Type inattendu sur une valeur.

    Levée par les opérations de lecture typée (ex : get_int, get_bool).

    Attributs :
        key      : clé de l'entrée fautive
        expected : type attendu (ex: "int")
        got      : type reçu  (ex: "str")
    """

    def __init__(self, key: str, expected: str, got: str):
        self.key      = key
        self.expected = expected
        self.got      = got
        super().__init__(
            f"Type inattendu pour '{key}' : attendu {expected}, reçu {got}."
        )


class FMTPathError(FMTError):
    """
    Chemin de navigation invalide (vide, mal formé, ou segment vide).

    Attributs :
        path   : chemin fourni par l'utilisateur
        reason : explication de l'invalidité
    """

    def __init__(self, path: str, reason: str = ""):
        self.path = path
        detail = f" : {reason}" if reason else ""
        super().__init__(f"Chemin invalide '{path}'{detail}.")
