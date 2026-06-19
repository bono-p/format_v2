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
fmt — Module Python pour les fichiers .fmt v2

Lecture, écriture et manipulation de fichiers au format .fmt.

Usage rapide :
    import fmt

    # ── Charger un fichier ────────────────────────────────────────
    doc = fmt.load("data.fmt")
    doc = fmt.load("data.fmt", strict=True, max_depth=5)

    # ── Créer un document depuis zéro ────────────────────────────
    doc = fmt.new("Dataset", "Paires FR-EN")

    # ── Lire des valeurs ──────────────────────────────────────────
    doc.section("fr").get("1")
    doc.get("fr", "1")                   # raccourci
    doc.get("config/database", "host")   # chemin imbriqué

    # ── Sauvegarder ───────────────────────────────────────────────
    doc.save("data.fmt")

    # ── Valider ───────────────────────────────────────────────────
    errors = fmt.validate(doc, schema)

Documentation complète : DOCUMENTATION.md
"""

from ._core      import FMT, FMTSection
from ._parser    import parse_string, parse_file
from ._types     import FMTType, FMTValue
from .exceptions import (
    FMTError,
    FMTSyntaxError,
    FMTFileError,
    FMTSectionNotFoundError,
    FMTEntryNotFoundError,
    FMTDuplicateSectionError,
    FMTDepthError,
    FMTTypeError,
    FMTPathError,
)

__version__  = "2.0.0"
__all__ = [
    # Fonctions principales
    "load", "parse", "new", "validate",
    # Classes
    "FMT", "FMTSection",
    # Système de types
    "FMTType", "FMTValue",
    # Exceptions
    "FMTError",
    "FMTSyntaxError",
    "FMTFileError",
    "FMTSectionNotFoundError",
    "FMTEntryNotFoundError",
    "FMTDuplicateSectionError",
    "FMTDepthError",
    "FMTTypeError",
    "FMTPathError",
]


def load(path: str, *, strict: bool = False, max_depth: int = 3) -> FMT:
    """
    Charge et parse un fichier .fmt depuis le disque.

    Paramètres :
        path      : chemin vers le fichier .fmt
        strict    : si True, lève FMTSyntaxError sur toute ligne non reconnue
                    (défaut False : les lignes inconnues sont ignorées)
        max_depth : profondeur maximale d'imbrication des sections (1–10, défaut 3)

    Lève :
        FMTFileError   si le fichier est introuvable ou illisible
        FMTSyntaxError si la syntaxe est invalide

    Exemples :
        doc = fmt.load("dataset.fmt")
        doc = fmt.load("config.fmt", strict=True, max_depth=5)
    """
    return parse_file(path, strict=strict, max_depth=max_depth)


def parse(text: str, *, strict: bool = False, max_depth: int = 3) -> FMT:
    """
    Parse un texte .fmt depuis une chaîne Python.

    Paramètres :
        text      : contenu .fmt sous forme de chaîne
        strict    : si True, lève FMTSyntaxError sur toute ligne non reconnue
        max_depth : profondeur maximale d'imbrication (1–10, défaut 3)

    Lève :
        FMTSyntaxError si le texte est invalide

    Exemple :
        doc = fmt.parse(texte_fmt, strict=True)
    """
    return parse_string(text, strict=strict, max_depth=max_depth)


def new(title_key: str, title_value: str, *, max_depth: int = 3) -> FMT:
    """
    Crée un nouveau document .fmt vide.

    Paramètres :
        title_key   : label du titre   (ex : "Dataset", "Config", "Projet")
        title_value : valeur du titre  (ex : "Mes données", "Production")
        max_depth   : profondeur maximale d'imbrication (1–10, défaut 3)

    Exemples :
        doc = fmt.new("Dataset", "Paires FR-EN")
        doc = fmt.new("Config", "Serveur prod", max_depth=4)
    """
    return FMT(title_key, title_value, max_depth=max_depth)


def validate(doc: FMT, schema: dict) -> list[str]:
    """
    Valide un document FMT contre un schéma structurel.
    Retourne la liste des erreurs (liste vide = document valide).

    Paramètres :
        doc    : document FMT à valider
        schema : dictionnaire de contraintes

    Structure du schéma :
        {
            "sections": {
                "nom": {
                    "required":      True,
                    "required_keys": ["clé1", "clé2"],
                    "allowed_keys":  ["clé1", "clé2"],
                    "subsections":   { "sous_nom": { ... } }
                }
            },
            "metadata": { "nom": { ... } }
        }

    Exemple :
        errors = fmt.validate(doc, {
            "sections": {
                "fr": {"required": True},
                "en": {"required": True},
            }
        })
        assert errors == []
    """
    from ._validator import FMTValidator
    return FMTValidator.validate(doc, schema)
