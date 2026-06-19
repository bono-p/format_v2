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
