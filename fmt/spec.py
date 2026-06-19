"""
fmt/spec.py — Constantes de spécification du format .fmt v2

Ce fichier est le contrat unique du format.
Toutes les valeurs sensibles passent par ici — aucune constante
magique dispersée dans le code.
"""

# ── Version du FORMAT (pas du document utilisateur) ──────────────────────────
FMT_FORMAT_VERSION: int = 1

# ── Fichier ───────────────────────────────────────────────────────────────────
FMT_EXTENSION: str     = ".fmt"
FMT_ENCODING: str      = "utf-8-sig"   # gère le BOM Windows en lecture
FMT_WRITE_ENCODING     = "utf-8"       # pas de BOM à l'écriture
FMT_NEWLINE: str       = "\n"

# ── Marqueur optionnel en tête de fichier ─────────────────────────────────────
FMT_MAGIC_PREFIX: str  = "# fmt:"

# ── Sections imbriquées ───────────────────────────────────────────────────────
FMT_PATH_SEPARATOR: str     = "/"
FMT_MAX_DEPTH_DEFAULT: int  = 3
FMT_MAX_DEPTH_LIMIT: int    = 10

# ── Mots-clés de types non quotés (insensibles à la casse) ───────────────────
FMT_TRUE_VALUES:  frozenset = frozenset({"true"})
FMT_FALSE_VALUES: frozenset = frozenset({"false"})
FMT_NULL_VALUES:  frozenset = frozenset({"null", "none"})

# ── Indentation dans le fichier sérialisé ─────────────────────────────────────
FMT_INDENT_SIZE: int = 2
