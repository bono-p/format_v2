"""
fmt/_parser.py — Parser récursif du format .fmt v2

Transforme un texte brut .fmt en objet FMT.
Ne pas appeler directement — passer par fmt.load() ou fmt.parse().

Améliorations v2 :
  • Numéros de ligne RÉELS  : chaque erreur indique la ligne dans le fichier
    original, pas la position dans les lignes prétraitées.
  • Parser récursif         : _parse_block() appelle récursivement _parse_block()
    pour les sous-sections imbriquées.
  • Système de types propre : quoted=True → str, quoted=False → inférence.
  • strict_mode             : lève FMTSyntaxError sur toute ligne non reconnue.
  • Détection magic         : lit # fmt:N sur la première ligne non vide
    avant le prétraitement (le magic est un commentaire, il serait sinon perdu).
  • Gestion BOM             : le fichier est lu en utf-8-sig (BOM automatiquement
    retiré par Python en lecture).
  • Clés dupliquées         : avertissement UserWarning (mode permissif)
    ou FMTSyntaxError (mode strict).
"""

from __future__ import annotations

import re
import warnings
from typing import Any

from ._core      import FMT, FMTSection
from ._types     import infer_value
from .exceptions import (
    FMTSyntaxError,
    FMTFileError,
    FMTDepthError,
)
from .spec import (
    FMT_ENCODING,
    FMT_MAX_DEPTH_DEFAULT,
    FMT_MAX_DEPTH_LIMIT,
)


class _FMTParser:
    """
    Parse un texte .fmt et retourne un objet FMT.

    Phases de traitement :
      1. Détection du magic # fmt:N (avant prétraitement)
      2. Prétraitement : suppression commentaires + construction du line_map
         (line_map[i] = numéro de ligne original de la i-ème ligne traitée)
      3. Parsing du titre
      4. Parsing récursif des sections et du bloc de métadonnées {}
    """

    # ── Expressions régulières ────────────────────────────────────────────────

    # # fmt:1  ou  # fmt: 2  (insensible à la casse, espaces optionnels)
    _RE_MAGIC = re.compile(r"^#\s*fmt\s*:\s*(\d+)\s*$", re.IGNORECASE)

    # "Clé" : "Valeur"  (titre du document)
    _RE_TITLE = re.compile(r'^"(.+?)"\s*:\s*"(.+?)"$')

    # section : "nom"  ou  section : 'nom'
    _RE_SECTION = re.compile(r'^section\s*:\s*["\'](.+?)["\']$', re.IGNORECASE)

    # 'clé' : "valeur"    → groupe 1=clé, 2=val double-quotée
    # 'clé' : 'valeur'    → groupe 1=clé, 3=val simple-quotée
    # 'clé' : valeur      → groupe 1=clé, 4=val non quotée
    # Gère les séquences d'échappement \" et \' à l'intérieur des chaînes.
    _RE_ENTRY = re.compile(
        r"""^'(.+?)'\s*:\s*"""
        r"""(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)'|(\S[^#]*?)?)\s*$""",
        re.VERBOSE,
    )

    # ── Construction ─────────────────────────────────────────────────────────

    def __init__(
        self,
        text:      str,
        *,
        strict:    bool = False,
        max_depth: int  = FMT_MAX_DEPTH_DEFAULT,
    ):
        self._original  = text
        self._strict    = strict
        self._max_depth = min(max(1, max_depth), FMT_MAX_DEPTH_LIMIT)

        # État interne (initialisé dans parse())
        self._lines:    list[str] = []
        self._line_map: list[int] = []   # index prétraité → numéro ligne original
        self._pos:      int       = 0

    # ── Prétraitement ─────────────────────────────────────────────────────────

    def _detect_magic(self) -> int | None:
        """
        Cherche le marqueur # fmt:N sur la première ligne non vide du texte brut.
        Doit être appelé AVANT le prétraitement (le magic est un commentaire
        et serait sinon supprimé).

        Retourne le numéro de version ou None si absent.
        """
        for raw_line in self._original.split("\n"):
            stripped = raw_line.strip()
            if not stripped:
                continue
            m = self._RE_MAGIC.match(stripped)
            if m:
                return int(m.group(1))
            break  # première ligne non vide sans magic → pas de marqueur
        return None

    def _strip_line_comment(self, line: str) -> str:
        """
        Supprime les commentaires # sur une ligne en respectant les chaînes
        entre guillemets simples ou doubles.

        Gère les séquences d'échappement \' et \" pour ne pas confondre
        un guillemet échappé avec la fin d'une chaîne.

        Exemple :
            'msg' : "il dit #pas un commentaire"  # vrai commentaire
            → 'msg' : "il dit #pas un commentaire"
        """
        in_quote   = False
        quote_char = ""
        i          = 0
        while i < len(line):
            ch = line[i]

            # Séquence d'échappement à l'intérieur d'une chaîne
            if in_quote and ch == "\\" and i + 1 < len(line):
                i += 2
                continue

            if not in_quote:
                if ch in ('"', "'"):
                    in_quote   = True
                    quote_char = ch
                elif ch == "#":
                    return line[:i].rstrip()
            else:
                if ch == quote_char:
                    in_quote   = False
                    quote_char = ""
            i += 1

        return line.rstrip()

    def _preprocess(self) -> tuple[list[str], list[int]]:
        """
        Prépare le texte pour le parsing :
          1. Supprime les commentaires blocs /* ... */ (multi-lignes)
             en préservant les sauts de ligne pour le comptage.
          2. Traite ligne par ligne : retire les commentaires inline #
             et les lignes vides.
          3. Construit le line_map : index_ligne_prétraitée → numéro_ligne_original.

        Retourne (lignes_nettoyées, line_map).
        """
        # ── Étape 1 : supprimer les commentaires blocs ────────────────────────
        text   = self._original
        result = []
        i      = 0
        while i < len(text):
            if text[i:i+2] == "/*":
                end = text.find("*/", i + 2)
                if end == -1:
                    # Commentaire non fermé : on ignore jusqu'à la fin
                    # On préserve les newlines pour ne pas décaler le comptage
                    block = text[i:]
                    result.extend("\n" if c == "\n" else " " for c in block)
                    break
                # Remplacer le bloc par des espaces (newlines conservés)
                block = text[i:end + 2]
                result.extend("\n" if c == "\n" else " " for c in block)
                i = end + 2
            else:
                result.append(text[i])
                i += 1

        cleaned_text = "".join(result)

        # ── Étape 2 : traitement ligne par ligne ──────────────────────────────
        lines:    list[str] = []
        line_map: list[int] = []

        for line_no, raw_line in enumerate(cleaned_text.split("\n"), start=1):
            clean = self._strip_line_comment(raw_line).strip()
            if clean:
                lines.append(clean)
                line_map.append(line_no)

        return lines, line_map

    # ── Navigation ────────────────────────────────────────────────────────────

    def _peek(self) -> str | None:
        """Retourne la ligne courante sans avancer."""
        return self._lines[self._pos] if self._pos < len(self._lines) else None

    def _consume(self) -> str:
        """Retourne la ligne courante et avance d'une position."""
        line = self._lines[self._pos]
        self._pos += 1
        return line

    def _real_line(self) -> int | None:
        """
        Numéro de ligne RÉEL (dans le fichier original) de la position courante.
        Garanti exact grâce au line_map construit lors du prétraitement.
        """
        if self._pos < len(self._line_map):
            return self._line_map[self._pos]
        if self._line_map:
            return self._line_map[-1]
        return None

    def _prev_real_line(self) -> int | None:
        """Numéro de ligne réel de la dernière ligne consommée."""
        idx = self._pos - 1
        if 0 <= idx < len(self._line_map):
            return self._line_map[idx]
        return None

    # ── Parsing d'un bloc [...] ───────────────────────────────────────────────

    def _parse_block(self, section_name: str, depth: int) -> tuple[dict, list]:
        """
        Parse le contenu entre '[' et ']' d'une section.
        Gère les entrées clé/valeur ET les sous-sections de façon récursive.

        Paramètres :
            section_name : nom de la section en cours (pour les messages d'erreur)
            depth        : profondeur actuelle dans l'arbre

        Retourne :
            (entries: dict[str, FMTValue], subsections: list[FMTSection])
        """
        ln   = self._real_line()
        line = self._peek()

        # Attente d'un '['
        if line is None:
            raise FMTSyntaxError(
                f"Fin de fichier inattendue : '[' attendu après la section '{section_name}'.",
                line_number=ln,
            )
        if line != "[":
            raise FMTSyntaxError(
                f"'[' attendu après la déclaration de '{section_name}'.",
                line_number=ln,
                line_content=line,
                hint="Toute section doit être suivie d'un bloc [ ... ].",
            )
        self._consume()  # consomme '['

        entries:     dict[str, Any]    = {}
        subsections: list[FMTSection]  = []
        seen_keys:   set[str]          = set()

        while True:
            line = self._peek()
            ln   = self._real_line()

            # Fin de fichier sans ']'
            if line is None:
                raise FMTSyntaxError(
                    f"']' manquant : fin de fichier à l'intérieur de '{section_name}'.",
                    line_number=self._line_map[-1] if self._line_map else None,
                )

            # Fermeture du bloc
            if line == "]":
                self._consume()
                break

            # ── Sous-section ──────────────────────────────────────────────
            sec_match = self._RE_SECTION.match(line)
            if sec_match:
                sub_name = sec_match.group(1)
                # Vérification de la profondeur avant de descendre
                if depth >= self._max_depth:
                    raise FMTDepthError(sub_name, depth, self._max_depth)
                self._consume()
                sub_entries, sub_subs = self._parse_block(sub_name, depth + 1)
                sub_sec = FMTSection(
                    sub_name,
                    sub_entries,
                    sub_subs,
                    _depth=depth + 1,
                    _max_depth=self._max_depth,
                )
                subsections.append(sub_sec)
                continue

            # ── Erreur guidée : guillemets doubles sur la clé ─────────────
            if line.startswith('"') and ":" in line:
                raise FMTSyntaxError(
                    f"Les clés utilisent des guillemets simples ' (pas doubles) dans '{section_name}'.",
                    line_number=ln,
                    line_content=line,
                    hint="Remplacez \"clé\" : valeur  par  'clé' : valeur.",
                )

            # ── Entrée clé / valeur ───────────────────────────────────────
            entry_match = self._RE_ENTRY.match(line)
            if entry_match:
                key = entry_match.group(1)

                if entry_match.group(2) is not None:
                    # Valeur entre guillemets doubles : toujours str
                    raw, quoted = entry_match.group(2), True
                elif entry_match.group(3) is not None:
                    # Valeur entre guillemets simples : toujours str
                    raw, quoted = entry_match.group(3), True
                else:
                    # Valeur non quotée : inférence de type
                    raw    = (entry_match.group(4) or "").strip()
                    quoted = False

                # Clé dupliquée dans la même section
                if key in seen_keys:
                    msg = (
                        f"Clé dupliquée '{key}' dans '{section_name}' "
                        f"(ligne {ln}) — la dernière valeur est conservée."
                    )
                    if self._strict:
                        raise FMTSyntaxError(msg, line_number=ln, line_content=line)
                    warnings.warn(msg, UserWarning, stacklevel=6)

                seen_keys.add(key)
                entries[key] = infer_value(raw, quoted=quoted)
                self._consume()
                continue

            # ── Ligne non reconnue ────────────────────────────────────────
            if self._strict:
                raise FMTSyntaxError(
                    f"Ligne non reconnue dans la section '{section_name}'.",
                    line_number=ln,
                    line_content=line,
                    hint="En mode strict, seules les entrées 'clé' : valeur "
                         "et les sous-sections sont autorisées.",
                )
            self._consume()  # mode permissif : ignorer silencieusement

        return entries, subsections

    # ── Parsing d'un ensemble de sections ─────────────────────────────────────

    def _parse_sections(
        self,
        stop_on: str | None = None,
        depth:   int         = 1,
    ) -> list[FMTSection]:
        """
        Parse une suite de déclarations section : "..." [ ... ] jusqu'à :
          • stop_on (si précisé), ex: '}'
          • fin de fichier

        Utilisé pour les sections principales ET pour le bloc {} des métadonnées.
        """
        sections: list[FMTSection] = []

        while True:
            line = self._peek()
            if line is None:
                break
            if stop_on and line == stop_on:
                break

            sec_match = self._RE_SECTION.match(line)
            if sec_match:
                name = sec_match.group(1)
                self._consume()
                entries, subsections = self._parse_block(name, depth)
                sections.append(
                    FMTSection(
                        name,
                        entries,
                        subsections,
                        _depth=depth,
                        _max_depth=self._max_depth,
                    )
                )
                continue

            if self._strict:
                raise FMTSyntaxError(
                    "Ligne non reconnue hors d'une section.",
                    line_number=self._real_line(),
                    line_content=line,
                )
            self._consume()

        return sections

    # ── Point d'entrée ────────────────────────────────────────────────────────

    def parse(self) -> FMT:
        """
        Lance le parsing complet et retourne un objet FMT.

        Phases :
          1. Détection du magic (sur le texte brut)
          2. Prétraitement (suppression commentaires + line_map)
          3. Parsing du titre
          4. Parsing du corps (sections + bloc métadonnées)
        """
        # ── Phase 1 : magic ───────────────────────────────────────────────
        fmt_version = self._detect_magic()

        # ── Phase 2 : prétraitement ───────────────────────────────────────
        self._lines, self._line_map = self._preprocess()
        self._pos = 0

        if not self._lines:
            raise FMTSyntaxError("Le fichier est vide ou ne contient que des commentaires.")

        # ── Phase 3 : titre ───────────────────────────────────────────────
        first = self._peek()
        title_match = self._RE_TITLE.match(first)
        if not title_match:
            raise FMTSyntaxError(
                'Titre attendu en première position sous la forme "Clé" : "Valeur".',
                line_number=self._real_line(),
                line_content=first,
                hint='Exemple valide : "Dataset" : "Mes données"',
            )
        title_key   = title_match.group(1)
        title_value = title_match.group(2)
        self._consume()

        doc = FMT(
            title_key,
            title_value,
            max_depth=self._max_depth,
            fmt_version=fmt_version,
        )

        # ── Phase 4 : corps ───────────────────────────────────────────────
        while True:
            line = self._peek()
            if line is None:
                break

            # Bloc de métadonnées { ... }
            if line == "{":
                self._consume()
                for sec in self._parse_sections(stop_on="}", depth=1):
                    doc._append_meta(sec)
                if self._peek() == "}":
                    self._consume()
                continue

            # Section principale
            sec_match = self._RE_SECTION.match(line)
            if sec_match:
                name = sec_match.group(1)
                self._consume()
                entries, subsections = self._parse_block(name, depth=1)
                doc._append_section(
                    FMTSection(
                        name,
                        entries,
                        subsections,
                        _depth=1,
                        _max_depth=self._max_depth,
                    )
                )
                continue

            # Ligne racine non reconnue
            if self._strict:
                raise FMTSyntaxError(
                    "Ligne non reconnue au niveau racine du document.",
                    line_number=self._real_line(),
                    line_content=line,
                )
            self._consume()

        return doc


# ── Fonctions publiques du module ─────────────────────────────────────────────

def parse_string(
    text:      str,
    *,
    strict:    bool = False,
    max_depth: int  = FMT_MAX_DEPTH_DEFAULT,
) -> FMT:
    """
    Parse un texte .fmt depuis une chaîne Python.

    Paramètres :
        text      : contenu .fmt
        strict    : si True, toute ligne inconnue lève FMTSyntaxError
        max_depth : profondeur maximale d'imbrication (1–10, défaut : 3)
    """
    return _FMTParser(text, strict=strict, max_depth=max_depth).parse()


def parse_file(
    path:      str,
    *,
    strict:    bool = False,
    max_depth: int  = FMT_MAX_DEPTH_DEFAULT,
) -> FMT:
    """
    Lit et parse un fichier .fmt depuis le disque.

    Paramètres :
        path      : chemin du fichier .fmt
        strict    : si True, toute ligne inconnue lève FMTSyntaxError
        max_depth : profondeur maximale d'imbrication (1–10, défaut : 3)

    Lève :
        FMTFileError   si le fichier est introuvable ou illisible
        FMTSyntaxError si le contenu est invalide
    """
    try:
        with open(path, encoding=FMT_ENCODING) as f:
            text = f.read()
    except FileNotFoundError:
        raise FMTFileError(path, "fichier introuvable")
    except PermissionError:
        raise FMTFileError(path, "permission refusée en lecture")
    except OSError as e:
        raise FMTFileError(path, str(e))

    return _FMTParser(text, strict=strict, max_depth=max_depth).parse()
