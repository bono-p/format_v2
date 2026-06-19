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
fmt/_writer.py — Writer du format .fmt v2

Sérialise un objet FMT vers du texte .fmt ou un fichier sur le disque.

Améliorations v2 :
  • Types propres     : int/float/bool/null sans guillemets forcés
  • Indentation       : récursive, FMT_INDENT_SIZE espaces par niveau
  • Magic             : écrit # fmt:N si fmt_version est défini
  • Encodage          : UTF-8 sans BOM, retours Unix (\n)
  • Pas de stdout     : aucun print() dans une bibliothèque
  • Sections vides    : écrites proprement (bloc [] sans contenu)
"""

from ._core      import FMT, FMTSection
from ._types     import serialize_value
from .exceptions import FMTFileError
from .spec       import FMT_WRITE_ENCODING, FMT_NEWLINE, FMT_INDENT_SIZE


class FMTWriter:
    """Sérialise un objet FMT en texte .fmt."""

    # ── Sérialisation d'une section ───────────────────────────────────────────

    @classmethod
    def _section_to_lines(cls, sec: FMTSection, indent: int = 0) -> list[str]:
        """
        Convertit récursivement une FMTSection en liste de lignes .fmt.

        Paramètres :
            sec    : section à sérialiser
            indent : niveau d'indentation (0 = premier niveau, 1 = sous-section…)

        Structure produite :
            section : "nom"
            [
              'clé1' : "valeur"     ← entrées indentées de 1 niveau
              'clé2' : 42

              section : "sous"      ← sous-section indentée récursivement
              [
                'clé' : true
              ]
            ]
        """
        pad      = " " * (FMT_INDENT_SIZE * indent)
        pad_in   = " " * (FMT_INDENT_SIZE * (indent + 1))  # contenu du bloc
        lines: list[str] = []

        lines.append(f'{pad}section : "{sec.name}"')
        lines.append(f'{pad}[')

        # ── Entrées ──────────────────────────────────────────────────────
        for key, val in sec._entries.items():
            lines.append(f"{pad_in}'{key}' : {serialize_value(val)}")

        # ── Sous-sections (séparées visuellement des entrées si les deux existent)
        if sec._subsections:
            if sec._entries:
                lines.append("")   # ligne vide séparatrice

            for idx, sub in enumerate(sec._subsections):
                lines.extend(cls._section_to_lines(sub, indent + 1))
                # Ligne vide entre sous-sections consécutives
                if idx < len(sec._subsections) - 1:
                    lines.append("")

        lines.append(f'{pad}]')
        return lines

    # ── Sérialisation du document complet ─────────────────────────────────────

    @classmethod
    def to_string(cls, doc: FMT) -> str:
        """
        Sérialise l'intégralité du document FMT en texte .fmt.

        Ordre de sortie :
          1. Ligne magic  # fmt:N   (si fmt_version présent)
          2. Titre
          3. Sections principales
          4. Bloc de métadonnées {}  (si présent)
        """
        lines: list[str] = []

        # ── Magic (optionnel) ─────────────────────────────────────────────
        if doc._fmt_version is not None:
            lines.append(f"# fmt:{doc._fmt_version}")
            lines.append("")

        # ── Titre ─────────────────────────────────────────────────────────
        lines.append(f'"{doc.title_key}" : "{doc.title_value}"')
        lines.append("")

        # ── Sections ──────────────────────────────────────────────────────
        for sec in doc._raw_sections:
            lines.extend(cls._section_to_lines(sec, indent=0))
            lines.append("")

        # ── Métadonnées ───────────────────────────────────────────────────
        if doc._raw_metadata:
            lines.append("{")
            for sec in doc._raw_metadata:
                lines.extend(cls._section_to_lines(sec, indent=1))
            lines.append("}")
            lines.append("")

        # Supprimer les lignes vides doubles en fin de fichier
        while len(lines) >= 2 and lines[-1] == "" and lines[-2] == "":
            lines.pop()

        return FMT_NEWLINE.join(lines) + FMT_NEWLINE

    # ── Écriture sur le disque ─────────────────────────────────────────────────

    @classmethod
    def to_file(cls, doc: FMT, path: str) -> None:
        """
        Écrit le document dans un fichier sur le disque.
        Encodage : UTF-8 sans BOM, retours à la ligne Unix (\n).

        Lève FMTFileError en cas d'erreur d'accès.
        """
        content = cls.to_string(doc)
        try:
            with open(path, "w", encoding=FMT_WRITE_ENCODING, newline="") as f:
                f.write(content)
        except PermissionError:
            raise FMTFileError(path, "permission refusée en écriture")
        except OSError as e:
            raise FMTFileError(path, str(e))
