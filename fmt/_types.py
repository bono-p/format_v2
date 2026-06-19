"""
fmt/_types.py — Système de types du format .fmt v2

Règle fondamentale du système de types :
  ┌─────────────────────────────────────────────────────────────┐
  │  Valeur entre guillemets " → toujours str, sans inférence  │
  │  Valeur sans guillemets   → inférence automatique du type  │
  └─────────────────────────────────────────────────────────────┘

Hiérarchie d'inférence (unquoted) :
  true / false  → bool
  null / none   → None
  entier        → int
  décimal       → float
  autre         → str (fallback)

Sérialisation (writer) :
  bool  → true / false        (sans guillemets)
  None  → null                (sans guillemets)
  int   → 42                  (sans guillemets)
  float → 3.14                (sans guillemets)
  str   → "valeur"            (toujours entre guillemets doubles)
"""

from __future__ import annotations
from enum import Enum
from typing import Union

from .spec import FMT_TRUE_VALUES, FMT_FALSE_VALUES, FMT_NULL_VALUES


# Type union Python représentant toute valeur .fmt
FMTValue = Union[str, int, float, bool, None]


class FMTType(Enum):
    """Enum des types supportés par le format .fmt."""
    STRING  = "str"
    INTEGER = "int"
    FLOAT   = "float"
    BOOLEAN = "bool"
    NULL    = "null"


def infer_value(raw: str, *, quoted: bool) -> FMTValue:
    """
    Convertit une valeur brute du fichier vers son type Python.

    Paramètres :
        raw    : contenu textuel de la valeur (guillemets déjà retirés si quoted)
        quoted : True si la valeur était entourée de " ou ' dans le fichier

    Comportement :
        quoted=True  → retourne raw tel quel (str), aucune inférence
        quoted=False → applique la hiérarchie d'inférence : bool > None > int > float > str

    Exemples :
        infer_value("42",    quoted=True)  → "42"     (str)
        infer_value("42",    quoted=False) → 42        (int)
        infer_value("true",  quoted=False) → True      (bool)
        infer_value("null",  quoted=False) → None
        infer_value("3.14",  quoted=False) → 3.14     (float)
        infer_value("hello", quoted=False) → "hello"  (str, fallback)
        infer_value("",      quoted=True)  → ""       (str vide explicite)
        infer_value("",      quoted=False) → None     (unquoted vide = null)
    """
    if quoted:
        # Guillemets présents : chaîne explicite, pas d'inférence
        # Gérer les séquences d'échappement basiques
        return _unescape(raw)

    s = raw.strip()

    # Mots-clés booléens
    if s.lower() in FMT_TRUE_VALUES:
        return True
    if s.lower() in FMT_FALSE_VALUES:
        return False

    # Mots-clés null
    if s.lower() in FMT_NULL_VALUES or s == "":
        return None

    # Entier
    try:
        return int(s)
    except ValueError:
        pass

    # Décimal
    try:
        return float(s)
    except ValueError:
        pass

    # Fallback : chaîne non reconnue
    return s


def serialize_value(v: FMTValue) -> str:
    """
    Sérialise une valeur Python vers sa représentation textuelle .fmt.

    Règles de sérialisation :
        bool  → true / false     (AVANT int : bool hérite de int en Python)
        None  → null
        str   → "valeur"         (toujours entre guillemets doubles)
        int   → 42
        float → 3.14             (repr Python, évite la perte de précision)

    Exemples :
        serialize_value(True)    → 'true'
        serialize_value(False)   → 'false'
        serialize_value(None)    → 'null'
        serialize_value("hello") → '"hello"'
        serialize_value(42)      → '42'
        serialize_value(3.14)    → '3.14'
        serialize_value("42")    → '"42"'   # string, pas int
    """
    # ⚠️  bool AVANT int — bool est une sous-classe de int en Python
    if isinstance(v, bool):
        return "true" if v else "false"

    if v is None:
        return "null"

    if isinstance(v, str):
        return '"' + _escape(v) + '"'

    if isinstance(v, int):
        return str(v)

    if isinstance(v, float):
        return _format_float(v)

    # Fallback sécurisé pour les types inattendus
    return '"' + _escape(str(v)) + '"'


def get_fmt_type(v: FMTValue) -> FMTType:
    """Retourne l'enum FMTType correspondant à une valeur Python."""
    if isinstance(v, bool):   return FMTType.BOOLEAN
    if v is None:              return FMTType.NULL
    if isinstance(v, str):     return FMTType.STRING
    if isinstance(v, int):     return FMTType.INTEGER
    if isinstance(v, float):   return FMTType.FLOAT
    return FMTType.STRING


# ── Helpers internes ──────────────────────────────────────────────────────────

def _escape(s: str) -> str:
    """Échappe les caractères spéciaux dans une chaîne pour le fichier .fmt."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")


def _unescape(s: str) -> str:
    """Décode les séquences d'échappement d'une chaîne lue depuis le fichier."""
    return (
        s.replace("\\n", "\n")
         .replace("\\t", "\t")
         .replace('\\"', '"')
         .replace("\\\\", "\\")
    )


def _format_float(v: float) -> str:
    """
    Formate un float sans perte de précision, en évitant la notation scientifique
    pour les valeurs courantes (entre 1e-6 et 1e15).
    """
    r = repr(v)
    # repr() peut produire de la notation scientifique (ex: 1e-10)
    if "e" in r or "E" in r:
        # Reformatter sans notation scientifique si raisonnable
        try:
            formatted = f"{v:.15g}"
            # S'assurer qu'il y a toujours un point décimal pour distinguer de int
            if "." not in formatted and "e" not in formatted:
                formatted += ".0"
            return formatted
        except (ValueError, OverflowError):
            return r
    return r
