"""
fmt/_core.py — Structures de données principales du module .fmt v2

Deux classes centrales :

  FMTSection
    Bloc nommé contenant des paires clé/valeur ET/OU des sous-sections.
    Récursif : une FMTSection peut contenir d'autres FMTSection.

  FMT
    Document complet avec titre, sections de premier niveau,
    métadonnées, version de format et configuration de profondeur.

Philosophie d'encapsulation :
  - Les attributs préfixés _ sont internes au package.
  - Le writer et le parser utilisent _append_section/_append_subsection
    pour construire l'arbre sans déclencher les validations publiques.
  - L'accès public passe toujours par les méthodes nommées (get, set, section…).
"""

from __future__ import annotations

import copy
from typing import Iterator

from ._types  import FMTValue, FMTType, serialize_value, get_fmt_type, infer_value
from .spec    import (
    FMT_PATH_SEPARATOR,
    FMT_MAX_DEPTH_DEFAULT,
    FMT_MAX_DEPTH_LIMIT,
)
from .exceptions import (
    FMTSectionNotFoundError,
    FMTEntryNotFoundError,
    FMTDuplicateSectionError,
    FMTDepthError,
    FMTPathError,
    FMTTypeError,
)


# ══════════════════════════════════════════════════════════════════════════════
#  FMTSection
# ══════════════════════════════════════════════════════════════════════════════

class FMTSection:
    """
    Bloc nommé d'un fichier .fmt, contenant :
      • des paires clé → valeur  (entrées)
      • des sous-sections        (FMTSection imbriquées)

    Les deux coexistent librement dans le même bloc.

    Structure dans le fichier :
    ┌─────────────────────────────────────────────────────┐
    │  section : "database"                               │
    │  [                                                  │
    │  'host' : "localhost"     ← entrées à ce niveau    │
    │  'port' : 5432                                      │
    │                                                     │
    │    section : "pool"       ← sous-section (depth+1) │
    │    [                                                │
    │    'min' : 2                                        │
    │    'max' : 10                                       │
    │    ]                                                │
    │  ]                                                  │
    └─────────────────────────────────────────────────────┘

    Accès imbriqué :
        sec.section("pool").get("min")        # navigation objet
        sec.section("pool/timeout").get("ms") # chemin slash
    """

    def __init__(
        self,
        name: str,
        entries:     dict[str, FMTValue] | None = None,
        subsections: list["FMTSection"]  | None = None,
        *,
        _depth:     int = 1,
        _max_depth: int = FMT_MAX_DEPTH_DEFAULT,
    ):
        self._name:        str                 = str(name)
        self._entries:     dict[str, FMTValue] = dict(entries or {})
        self._subsections: list[FMTSection]    = list(subsections or [])
        self._depth:       int                 = _depth
        self._max_depth:   int                 = min(_max_depth, FMT_MAX_DEPTH_LIMIT)

    # ── Propriétés ────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        """Nom de la section (lecture seule — utiliser .rename() pour modifier)."""
        return self._name

    @property
    def depth(self) -> int:
        """Profondeur dans l'arbre (1 = premier niveau, 2 = sous-section, etc.)."""
        return self._depth

    # ══════════════════════════════════════════════════════════════════════════
    #  ENTRÉES — paires clé / valeur
    # ══════════════════════════════════════════════════════════════════════════

    def get(self, key: str, default: FMTValue = None) -> FMTValue:
        """
        Retourne la valeur associée à key, ou default si absente.

        Exemple :
            sec.get("host", "localhost")
        """
        return self._entries.get(str(key), default)

    def get_or_raise(self, key: str) -> FMTValue:
        """
        Retourne la valeur ou lève FMTEntryNotFoundError.

        Exemple :
            host = sec.get_or_raise("host")
        """
        k = str(key)
        if k not in self._entries:
            raise FMTEntryNotFoundError(k, self._name)
        return self._entries[k]

    def get_str(self, key: str, default: str = "") -> str:
        """Retourne la valeur sous forme de str (conversion si nécessaire)."""
        v = self.get(key)
        if v is None:
            return default
        return str(v)

    def get_int(self, key: str) -> int:
        """
        Retourne la valeur sous forme de int.
        Lève FMTTypeError si la valeur n'est pas un entier.
        """
        v = self.get_or_raise(key)
        if not isinstance(v, int) or isinstance(v, bool):
            raise FMTTypeError(key, "int", type(v).__name__)
        return v

    def get_float(self, key: str) -> float:
        """
        Retourne la valeur sous forme de float (accepte aussi les int).
        Lève FMTTypeError si la valeur n'est ni int ni float.
        """
        v = self.get_or_raise(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise FMTTypeError(key, "float", type(v).__name__)
        return float(v)

    def get_bool(self, key: str) -> bool:
        """
        Retourne la valeur sous forme de bool.
        Lève FMTTypeError si la valeur n'est pas un booléen.
        """
        v = self.get_or_raise(key)
        if not isinstance(v, bool):
            raise FMTTypeError(key, "bool", type(v).__name__)
        return v

    def has(self, key: str) -> bool:
        """True si la clé existe dans les entrées de cette section."""
        return str(key) in self._entries

    def keys(self) -> list[str]:
        """Liste ordonnée de toutes les clés d'entrées."""
        return list(self._entries.keys())

    def all_entries(self) -> dict[str, FMTValue]:
        """Copie du dictionnaire clé → valeur (modifications sans effet sur la section)."""
        return dict(self._entries)

    def count(self) -> int:
        """Nombre d'entrées directes (sous-sections non comptées)."""
        return len(self._entries)

    def next_key(self) -> str:
        """
        Prochaine clé numérique disponible.

        Retourne str(max_clé_numérique + 1), ou "1" si aucune clé numérique.
        Les clés négatives sont ignorées dans le calcul.

        Exemple :
            section avec clés "1", "2", "5" → next_key() == "6"
        """
        numeric: list[int] = []
        for k in self._entries:
            try:
                n = int(k)
                if n > 0:
                    numeric.append(n)
            except ValueError:
                pass
        return str(max(numeric) + 1) if numeric else "1"

    def set(self, key: str, value: FMTValue) -> "FMTSection":
        """
        Ajoute ou modifie une entrée.
        Retourne self pour permettre le chaînage.

        Exemple :
            sec.set("host", "localhost").set("port", 5432)
        """
        self._entries[str(key)] = value
        return self

    def append(self, value: FMTValue) -> str:
        """
        Ajoute une entrée avec la prochaine clé numérique auto.
        Retourne la clé utilisée.

        Exemple :
            key = sec.append("Bonjour")   # key == "1"
        """
        key = self.next_key()
        self._entries[key] = value
        return key

    def remove(self, key: str) -> "FMTSection":
        """
        Supprime une entrée.
        Lève FMTEntryNotFoundError si la clé est absente.
        """
        k = str(key)
        if k not in self._entries:
            raise FMTEntryNotFoundError(k, self._name)
        del self._entries[k]
        return self

    def clear(self) -> "FMTSection":
        """Supprime toutes les entrées (les sous-sections sont conservées)."""
        self._entries.clear()
        return self

    def clear_all(self) -> "FMTSection":
        """Supprime les entrées ET toutes les sous-sections."""
        self._entries.clear()
        self._subsections.clear()
        return self

    def rename(self, new_name: str) -> "FMTSection":
        """
        Renomme la section.
        Retourne self pour le chaînage.
        """
        self._name = str(new_name)
        return self

    # ══════════════════════════════════════════════════════════════════════════
    #  SOUS-SECTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def section_names(self) -> list[str]:
        """Noms des sous-sections directes (un seul niveau)."""
        return [s.name for s in self._subsections]

    def has_section(self, name: str) -> bool:
        """True si une sous-section directe porte ce nom (insensible à la casse)."""
        return any(s.name.lower() == name.lower() for s in self._subsections)

    def section(self, path: str) -> "FMTSection":
        """
        Retourne une sous-section par son nom ou chemin.

        Le chemin utilise '/' comme séparateur :
            sec.section("pool")            # sous-section directe
            sec.section("pool/timeout")    # imbrication

        Lève FMTPathError            si le chemin est vide ou malformé.
        Lève FMTSectionNotFoundError si la section n'existe pas.
        """
        if not path or path.strip(FMT_PATH_SEPARATOR) == "":
            raise FMTPathError(path, "chemin vide")

        parts = path.split(FMT_PATH_SEPARATOR, 1)
        name  = parts[0].strip()

        if not name:
            raise FMTPathError(path, f"segment vide dans '{path}'")

        found = next(
            (s for s in self._subsections if s.name.lower() == name.lower()),
            None,
        )
        if found is None:
            raise FMTSectionNotFoundError(name, self.section_names(), path=path)

        return found if len(parts) == 1 else found.section(parts[1])

    def add_section(self, name: str) -> "FMTSection":
        """
        Crée et ajoute une sous-section vide.

        Lève FMTDuplicateSectionError si une section du même nom existe déjà.
        Lève FMTDepthError si la profondeur maximale est atteinte.

        Exemple :
            pool = sec.add_section("pool")
            pool.set("min", 2).set("max", 10)
        """
        if self.has_section(name):
            raise FMTDuplicateSectionError(name, parent=self._name)
        if self._depth >= self._max_depth:
            raise FMTDepthError(name, self._depth, self._max_depth)

        sub = FMTSection(
            name,
            _depth=self._depth + 1,
            _max_depth=self._max_depth,
        )
        self._subsections.append(sub)
        return sub

    def get_or_add_section(self, name: str) -> "FMTSection":
        """
        Retourne la sous-section si elle existe, la crée sinon.

        Exemple :
            pool = sec.get_or_add_section("pool")
        """
        if self.has_section(name):
            return self.section(name)
        return self.add_section(name)

    def remove_section(self, name: str) -> "FMTSection":
        """
        Supprime une sous-section directe.
        Lève FMTSectionNotFoundError si absente.
        """
        if not self.has_section(name):
            raise FMTSectionNotFoundError(name, self.section_names())
        self._subsections = [
            s for s in self._subsections if s.name.lower() != name.lower()
        ]
        return self

    def subsection_count(self) -> int:
        """Nombre de sous-sections directes."""
        return len(self._subsections)

    def total_entry_count(self) -> int:
        """Compte récursif de toutes les entrées (sous-sections incluses)."""
        total = len(self._entries)
        for sub in self._subsections:
            total += sub.total_entry_count()
        return total

    # ══════════════════════════════════════════════════════════════════════════
    #  INFORMATIONS
    # ══════════════════════════════════════════════════════════════════════════

    def info(self) -> dict:
        """Dictionnaire récapitulatif de la section."""
        return {
            "nom":            self._name,
            "profondeur":     self._depth,
            "entrées":        self.count(),
            "sous_sections":  self.section_names(),
            "total_entrées":  self.total_entry_count(),
        }

    # ══════════════════════════════════════════════════════════════════════════
    #  AFFICHAGE
    # ══════════════════════════════════════════════════════════════════════════

    def print(self, _indent: int = 0) -> None:
        """
        Affiche la section avec indentation visuelle pour les sous-sections.

        Exemple de sortie :
            ┌─ section : "database" ─ depth 1 ──────────────────────
            │  'host' : "localhost"
            │  'port' : 5432
            │
            │  ┌─ section : "pool" ─ depth 2 ──────────────────────
            │  │  'min' : 2
            │  │  'max' : 10
            │  └────────────────────────────────────────────────────
            └────────────────────────────────────────────────────────
        """
        pad    = "│  " * _indent
        header = f'section : "{self._name}" — depth {self._depth}'
        bar    = "─" * max(4, 48 - len(header))

        print(f"{pad}┌─ {header} {bar}")

        if not self._entries and not self._subsections:
            print(f"{pad}│  (section vide)")
        else:
            for key, val in self._entries.items():
                print(f"{pad}│  '{key}' : {serialize_value(val)}")
            for i, sub in enumerate(self._subsections):
                if self._entries or i > 0:
                    print(f"{pad}│")
                sub.print(_indent=_indent + 1)

        print(f"{pad}└" + "─" * (len(header) + len(bar) + 4))

    # ══════════════════════════════════════════════════════════════════════════
    #  PROTOCOLES PYTHON
    # ══════════════════════════════════════════════════════════════════════════

    def __repr__(self) -> str:
        return (
            f"FMTSection(name={self._name!r}, "
            f"depth={self._depth}, "
            f"entries={len(self._entries)}, "
            f"subsections={len(self._subsections)})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FMTSection):
            return NotImplemented
        return (
            self._name        == other._name
            and self._entries == other._entries
            and self._subsections == other._subsections
        )

    def __len__(self) -> int:
        """Nombre d'entrées directes."""
        return self.count()

    def __contains__(self, key: str) -> bool:
        """Vérifie si une clé d'entrée existe : 'host' in sec."""
        return self.has(key)

    def __iter__(self) -> Iterator[tuple[str, FMTValue]]:
        """Itère sur les paires (clé, valeur) des entrées directes."""
        return iter(self._entries.items())

    # ── Méthodes internes (parser uniquement) ─────────────────────────────────

    def _append_subsection(self, sec: "FMTSection") -> None:
        """
        Ajoute une sous-section pré-construite sans validation.
        Réservé au parser — ne pas appeler depuis le code utilisateur.
        """
        self._subsections.append(sec)


# ══════════════════════════════════════════════════════════════════════════════
#  FMT — document complet
# ══════════════════════════════════════════════════════════════════════════════

class FMT:
    """
    Document .fmt complet.

    Contient :
      • un titre  (obligatoire)
      • des sections de premier niveau (avec sous-sections possibles)
      • un bloc de métadonnées optionnel
      • la version du format lue depuis le fichier (# fmt:N)
      • la configuration de profondeur maximale

    Accès imbriqué unifié via '/' :
        doc.section("database/pool").get("max")
        doc.get("database/pool", "max")

    Exemple minimal :
        doc = fmt.new("Dataset", "Mes données")
        sec = doc.add_section("fr")
        sec.append("Bonjour")
        doc.save("data.fmt")
    """

    def __init__(
        self,
        title_key:   str,
        title_value: str,
        *,
        max_depth:   int       = FMT_MAX_DEPTH_DEFAULT,
        fmt_version: int | None = None,
    ):
        self._title_key:   str              = str(title_key)
        self._title_value: str              = str(title_value)
        self._sections:    list[FMTSection] = []
        self._metadata:    list[FMTSection] = []
        self._max_depth:   int              = min(max(1, max_depth), FMT_MAX_DEPTH_LIMIT)
        self._fmt_version: int | None       = fmt_version

    # ── Titre ─────────────────────────────────────────────────────────────────

    @property
    def title(self) -> tuple[str, str]:
        """Tuple (clé_du_titre, valeur_du_titre)."""
        return (self._title_key, self._title_value)

    @property
    def title_key(self) -> str:
        return self._title_key

    @property
    def title_value(self) -> str:
        return self._title_value

    def set_title(self, value: str) -> "FMT":
        """Modifie la valeur du titre. Retourne self."""
        self._title_value = str(value)
        return self

    def set_title_key(self, key: str) -> "FMT":
        """Modifie le label du titre. Retourne self."""
        self._title_key = str(key)
        return self

    def print_title(self) -> None:
        """Affiche le titre dans la console."""
        print(f'🏷️  "{self._title_key}" : "{self._title_value}"')

    # ── Sections ──────────────────────────────────────────────────────────────

    def section_names(self) -> list[str]:
        """Noms des sections de premier niveau."""
        return [s.name for s in self._sections]

    def has_section(self, path: str) -> bool:
        """
        True si la section ou le chemin existe.

        Exemple :
            doc.has_section("fr")
            doc.has_section("config/database")
        """
        try:
            self.section(path)
            return True
        except (FMTSectionNotFoundError, FMTPathError):
            return False

    def section(self, path: str) -> FMTSection:
        """
        Retourne une section par son nom ou son chemin imbriqué.

        Le chemin utilise '/' comme séparateur de niveaux.
        La comparaison des noms est insensible à la casse.

        Exemples :
            doc.section("fr")                   # niveau 1
            doc.section("config/database")      # niveau 2
            doc.section("config/database/pool") # niveau 3

        Lève FMTPathError            si le chemin est vide.
        Lève FMTSectionNotFoundError si un segment du chemin est absent.
        """
        if not path or path.strip(FMT_PATH_SEPARATOR) == "":
            raise FMTPathError(path, "chemin vide")

        parts = path.split(FMT_PATH_SEPARATOR, 1)
        name  = parts[0].strip()

        found = next(
            (s for s in self._sections if s.name.lower() == name.lower()),
            None,
        )
        if found is None:
            raise FMTSectionNotFoundError(name, self.section_names(), path=path)

        return found if len(parts) == 1 else found.section(parts[1])

    def add_section(self, name: str) -> FMTSection:
        """
        Crée une section de premier niveau vide.
        Lève FMTDuplicateSectionError si une section du même nom existe déjà.

        Exemple :
            fr = doc.add_section("fr")
            fr.append("Bonjour")
        """
        if self.has_section(name):
            raise FMTDuplicateSectionError(name)
        sec = FMTSection(name, _depth=1, _max_depth=self._max_depth)
        self._sections.append(sec)
        return sec

    def get_or_add_section(self, name: str) -> FMTSection:
        """Retourne la section si elle existe, la crée sinon."""
        if self.has_section(name):
            return self.section(name)
        return self.add_section(name)

    def remove_section(self, name: str) -> "FMT":
        """Supprime une section de premier niveau. Lève FMTSectionNotFoundError si absente."""
        if not self.has_section(name):
            raise FMTSectionNotFoundError(name, self.section_names())
        self._sections = [
            s for s in self._sections if s.name.lower() != name.lower()
        ]
        return self

    def rename_section(self, old_name: str, new_name: str) -> "FMT":
        """
        Renomme une section de premier niveau.
        Lève FMTDuplicateSectionError si new_name existe déjà.
        """
        sec = self.section(old_name)
        if old_name.lower() != new_name.lower() and self.has_section(new_name):
            raise FMTDuplicateSectionError(new_name)
        sec.rename(new_name)
        return self

    def copy_section(self, source: str, dest: str) -> FMTSection:
        """
        Duplique une section de premier niveau sous un nouveau nom.
        La copie est indépendante de l'originale (deep copy).
        Retourne la copie.

        Lève FMTSectionNotFoundError si source n'existe pas.
        Lève FMTDuplicateSectionError si dest existe déjà.
        """
        original = self.section(source)
        if self.has_section(dest):
            raise FMTDuplicateSectionError(dest)
        clone = copy.deepcopy(original)
        clone.rename(dest)
        self._sections.append(clone)
        return clone

    # ── Raccourcis entrées ─────────────────────────────────────────────────────

    def get(self, path: str, key: str, default: FMTValue = None) -> FMTValue:
        """
        Raccourci : lit une valeur dans une section (ou chemin imbriqué).

        Exemples :
            doc.get("fr", "1")
            doc.get("config/database", "host")
        """
        return self.section(path).get(key, default)

    def set(self, path: str, key: str, value: FMTValue) -> "FMT":
        """Raccourci : ajoute ou modifie une entrée dans une section."""
        self.section(path).set(key, value)
        return self

    def append_to(self, path: str, value: FMTValue) -> str:
        """Raccourci : ajoute une entrée avec clé auto. Retourne la clé."""
        return self.section(path).append(value)

    def remove_entry(self, path: str, key: str) -> "FMT":
        """Raccourci : supprime une entrée dans une section."""
        self.section(path).remove(key)
        return self

    # ── Paires alignées ────────────────────────────────────────────────────────

    def get_pairs(self, path_a: str, path_b: str) -> list[tuple[FMTValue, FMTValue]]:
        """
        Retourne les paires alignées entre deux sections partageant les mêmes clés.
        Supporte les chemins imbriqués.

        Exemple :
            doc.get_pairs("fr", "en")
            # [("Bonjour", "Hello"), ("Au revoir", "Goodbye")]
        """
        sa = self.section(path_a)
        sb = self.section(path_b)
        return [
            (sa.get(k), sb.get(k))
            for k in sa.keys()
            if sb.has(k)
        ]

    # ── Métadonnées ───────────────────────────────────────────────────────────

    def meta_names(self) -> list[str]:
        """Noms des sections de métadonnées."""
        return [s.name for s in self._metadata]

    def has_meta(self, name: str) -> bool:
        """True si une section de métadonnées porte ce nom."""
        return any(s.name.lower() == name.lower() for s in self._metadata)

    def meta(self, name: str) -> FMTSection:
        """
        Retourne une section de métadonnées.
        Lève FMTSectionNotFoundError si absente.
        """
        found = next(
            (s for s in self._metadata if s.name.lower() == name.lower()), None
        )
        if found is None:
            raise FMTSectionNotFoundError(name, self.meta_names())
        return found

    def add_meta(self, name: str) -> FMTSection:
        """Crée une section de métadonnées. Lève FMTDuplicateSectionError si existante."""
        if self.has_meta(name):
            raise FMTDuplicateSectionError(name)
        sec = FMTSection(name, _depth=1, _max_depth=self._max_depth)
        self._metadata.append(sec)
        return sec

    def get_or_add_meta(self, name: str) -> FMTSection:
        """Retourne la section de métadonnées si elle existe, la crée sinon."""
        return self.meta(name) if self.has_meta(name) else self.add_meta(name)

    def set_meta(self, section: str, key: str, value: FMTValue) -> "FMT":
        """Raccourci : modifie une entrée dans les métadonnées."""
        self.meta(section).set(key, value)
        return self

    def get_meta_entry(self, section: str, key: str, default: FMTValue = None) -> FMTValue:
        """Raccourci : lit une valeur dans les métadonnées."""
        return self.meta(section).get(key, default)

    # ── Fusion ────────────────────────────────────────────────────────────────

    def merge(self, other: "FMT", *, overwrite: bool = False) -> "FMT":
        """
        Fusionne les sections de `other` dans ce document.

        Paramètres :
            overwrite : si True, les sections existantes sont remplacées.
                        si False (défaut), elles sont ignorées.

        Retourne self pour le chaînage.
        """
        for sec in other._sections:
            if self.has_section(sec.name):
                if overwrite:
                    self.remove_section(sec.name)
                else:
                    continue
            clone = copy.deepcopy(sec)
            self._sections.append(clone)
        return self

    # ── Affichage ─────────────────────────────────────────────────────────────

    def print_section(self, path: str) -> None:
        """Affiche une section (supporte les chemins imbriqués)."""
        self.section(path).print()

    def print_all_sections(self) -> None:
        """Affiche toutes les sections de premier niveau."""
        if not self._sections:
            print("(aucune section)")
            return
        for sec in self._sections:
            sec.print()
            print()

    def print_meta(self) -> None:
        """Affiche le bloc de métadonnées."""
        if not self._metadata:
            print("(aucune métadonnée)")
            return
        print("╔══ MÉTADONNÉES ══╗")
        for sec in self._metadata:
            sec.print()

    def print_all(self) -> None:
        """Affiche l'intégralité du document."""
        bar = "═" * 54
        print(bar)
        self.print_title()
        print(bar)
        print()
        self.print_all_sections()
        if self._metadata:
            self.print_meta()

    # ── Sérialisation ─────────────────────────────────────────────────────────

    def to_string(self) -> str:
        """Sérialise le document en texte .fmt (chaîne Python)."""
        from ._writer import FMTWriter
        return FMTWriter.to_string(self)

    def save(self, path: str) -> None:
        """
        Sauvegarde le document dans un fichier .fmt sur le disque.
        Encodage : UTF-8 sans BOM, retours à la ligne Unix.
        """
        from ._writer import FMTWriter
        FMTWriter.to_file(self, path)

    # ── Informations ──────────────────────────────────────────────────────────

    def info(self) -> dict:
        """Dictionnaire récapitulatif du document."""
        total = sum(s.total_entry_count() for s in self._sections)
        return {
            "titre":          self._title_value,
            "version_format": self._fmt_version,
            "max_depth":      self._max_depth,
            "sections":       self.section_names(),
            "total_entrées":  total,
            "métadonnées":    self.meta_names(),
        }

    # ── Protocoles Python ─────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"FMT(titre={self._title_value!r}, "
            f"sections={self.section_names()}, "
            f"max_depth={self._max_depth})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FMT):
            return NotImplemented
        return (
            self._title_key   == other._title_key
            and self._title_value == other._title_value
            and self._sections    == other._sections
            and self._metadata    == other._metadata
        )

    # ── Méthodes internes (parser uniquement) ─────────────────────────────────

    def _append_section(self, sec: FMTSection) -> None:
        """
        Ajoute une section pré-construite sans validation.
        Réservé au parser — ne pas appeler depuis le code utilisateur.
        """
        self._sections.append(sec)

    def _append_meta(self, sec: FMTSection) -> None:
        """
        Ajoute une section de métadonnées pré-construite sans validation.
        Réservé au parser.
        """
        self._metadata.append(sec)

    # Accès en lecture pour le writer (vues, pas de copies)
    @property
    def _raw_sections(self) -> list[FMTSection]:
        """Vue interne des sections — réservé au writer."""
        return self._sections

    @property
    def _raw_metadata(self) -> list[FMTSection]:
        """Vue interne des métadonnées — réservé au writer."""
        return self._metadata
