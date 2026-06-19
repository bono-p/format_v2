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
fmt/_validator.py — Validateur optionnel du format .fmt v2

Vérifie qu'un document FMT respecte un schéma structurel attendu.
Usage : fmt.validate(doc, schema) → list[str]  (vide = valide)

Structure du schéma :
{
    "sections": {
        "nom_section": {
            "required":      True,                # la section doit exister
            "required_keys": ["clé1", "clé2"],   # clés obligatoires
            "allowed_keys":  ["clé1", "clé2"],   # clés autorisées (None = tout)
            "subsections": {                      # même structure récursive
                "nom_sous_section": { ... }
            }
        }
    },
    "metadata": {
        "nom_meta": { ... }                       # idem pour les métadonnées
    }
}

Exemple complet :
    schema = {
        "sections": {
            "config": {
                "required": True,
                "required_keys": ["host", "port"],
                "subsections": {
                    "pool": {
                        "required": True,
                        "required_keys": ["min", "max"]
                    }
                }
            },
            "fr": {
                "required": True
            }
        },
        "metadata": {
            "infos": {
                "required_keys": ["version", "date"]
            }
        }
    }

    errors = fmt.validate(doc, schema)
    if errors:
        for e in errors:
            print("❌", e)
    else:
        print("✅ Document valide")
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._core import FMT, FMTSection


class FMTValidator:
    """
    Valide un document FMT contre un schéma structurel.

    Utilisation via fmt.validate(doc, schema) ou directement :
        from fmt._validator import FMTValidator
        errors = FMTValidator.validate(doc, schema)
    """

    @classmethod
    def validate(cls, doc: "FMT", schema: dict) -> list[str]:
        """
        Valide le document et retourne la liste des erreurs trouvées.
        Une liste vide signifie que le document est valide.

        Paramètres :
            doc    : document FMT à valider
            schema : dictionnaire de contraintes (voir module docstring)
        """
        errors: list[str] = []

        # Validation des sections principales
        for name, sec_schema in schema.get("sections", {}).items():
            if not doc.has_section(name):
                if sec_schema.get("required", False):
                    errors.append(f"Section requise absente : '{name}'")
            else:
                sec = doc.section(name)
                errors.extend(cls._validate_section(sec, sec_schema, path=name))

        # Validation des métadonnées
        for name, meta_schema in schema.get("metadata", {}).items():
            if not doc.has_meta(name):
                if meta_schema.get("required", False):
                    errors.append(f"Métadonnée requise absente : '{name}'")
            else:
                sec = doc.meta(name)
                errors.extend(cls._validate_section(sec, meta_schema, path=f"meta/{name}"))

        return errors

    @classmethod
    def _validate_section(
        cls,
        sec:    "FMTSection",
        schema: dict,
        path:   str,
    ) -> list[str]:
        """Valide récursivement une section contre son sous-schéma."""
        errors: list[str] = []

        # Clés obligatoires
        for key in schema.get("required_keys", []):
            if not sec.has(key):
                errors.append(f"Clé requise absente : '{key}' dans '{path}'")

        # Clés autorisées (liste blanche)
        allowed = schema.get("allowed_keys")
        if allowed is not None:
            for key in sec.keys():
                if key not in allowed:
                    errors.append(
                        f"Clé non autorisée : '{key}' dans '{path}' "
                        f"(autorisées : {allowed})"
                    )

        # Sous-sections
        for sub_name, sub_schema in schema.get("subsections", {}).items():
            if not sec.has_section(sub_name):
                if sub_schema.get("required", False):
                    errors.append(
                        f"Sous-section requise absente : '{sub_name}' dans '{path}'"
                    )
            else:
                sub = sec.section(sub_name)
                errors.extend(
                    cls._validate_section(sub, sub_schema, path=f"{path}/{sub_name}")
                )

        return errors
