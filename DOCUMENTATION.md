# Format .fmt — Documentation v2

> Module Python pour lire, écrire et manipuler des fichiers au format `.fmt`  
> Version du module : **2.0.0** | Version du format : **1**

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Spécification du format](#2-spécification-du-format)
   - 2.1 Grammaire EBNF
   - 2.2 Règles syntaxiques
   - 2.3 Commentaires
   - 2.4 Système de types
3. [Sections imbriquées et profondeur](#3-sections-imbriquées-et-profondeur)
   - 3.1 Principe
   - 3.2 Niveaux de profondeur (depth)
   - 3.3 Navigation par chemin
   - 3.4 Limites et configuration
4. [Structure de l'architecture interne](#4-structure-de-larchitecture-interne)
5. [Guide d'utilisation](#5-guide-dutilisation)
   - 5.1 Création d'un document
   - 5.2 Chargement d'un fichier
   - 5.3 Lecture des données
   - 5.4 Écriture et modification
   - 5.5 Sections imbriquées
   - 5.6 Métadonnées
   - 5.7 Sauvegarde
6. [Référence API complète](#6-référence-api-complète)
   - 6.1 Fonctions du module
   - 6.2 Classe FMT
   - 6.3 Classe FMTSection
   - 6.4 Système de types
   - 6.5 Validateur
7. [Référence des erreurs](#7-référence-des-erreurs)
8. [Exemples de fichiers .fmt](#8-exemples-de-fichiers-fmt)
9. [Migration depuis la v1](#9-migration-depuis-la-v1)

---

## 1. Vue d'ensemble

Le format `.fmt` est un format de fichier texte structuré, lisible par l'humain, conçu pour stocker des données organisées en sections hiérarchiques avec des paires clé/valeur typées.

**Caractéristiques principales :**
- Syntaxe claire et lisible
- Sections imbriquées jusqu'à 10 niveaux (3 par défaut)
- Système de types explicite : `str`, `int`, `float`, `bool`, `null`
- Commentaires sur une ligne (`#`) et multi-lignes (`/* ... */`)
- Métadonnées intégrées au fichier
- Marqueur de version optionnel (`# fmt:1`)
- Encodage UTF-8 (BOM Windows géré en lecture)

---

## 2. Spécification du format

### 2.1 Grammaire EBNF

```ebnf
document     ::= magic? title section* metadata?

magic        ::= "# fmt:" INTEGER NEWLINE
title        ::= '"' text '"' " : " '"' text '"' NEWLINE

section      ::= "section" " : " '"' name '"' NEWLINE block
block        ::= "[" NEWLINE (entry | section)* "]" NEWLINE

entry        ::= "'" key "'" " : " value NEWLINE
value        ::= quoted_str | integer | float | boolean | null

quoted_str   ::= '"' (char | escape)* '"'
             |   "'" (char | escape)* "'"
integer      ::= ["-"] DIGIT+
float        ::= ["-"] DIGIT+ "." DIGIT+
boolean      ::= "true" | "false"            (* insensible à la casse *)
null         ::= "null" | "none"             (* insensible à la casse *)

metadata     ::= "{" NEWLINE section* "}"

comment_line ::= "#" [^\n]* NEWLINE          (* hors magic *)
comment_blk  ::= "/*" .* "*/"               (* multi-lignes *)
escape       ::= "\\" ('"' | "'" | "n" | "t" | "\\")
key          ::= char+
name         ::= char+
text         ::= char+
```

### 2.2 Règles syntaxiques

| Élément | Syntaxe | Exemple |
|---------|---------|---------|
| Magic (optionnel) | `# fmt:N` sur la 1ère ligne non vide | `# fmt:1` |
| Titre (obligatoire) | `"Clé" : "Valeur"` | `"Dataset" : "Paires FR-EN"` |
| Section | `section : "nom"` + `[ ... ]` | `section : "config"` |
| Clé d'entrée | Entre guillemets simples | `'host'` |
| Valeur quotée (str) | Entre guillemets doubles | `"localhost"` |
| Valeur non quotée | Sans guillemets | `5432`, `true`, `null` |
| Commentaire inline | `#` hors chaîne | `'k' : 1  # note` |
| Commentaire bloc | `/* ... */` | `/* multi\nligne */` |
| Métadonnées | Bloc `{ ... }` à la fin | `{ section : "infos" [...] }` |

**Règles importantes :**
- Le titre est la première ligne non commentaire du fichier (après le magic).
- Les sections et sous-sections s'ouvrent avec `[` et se ferment avec `]`, chacun sur sa propre ligne.
- La comparaison des noms de sections est **insensible à la casse** (`"FR"` == `"fr"`).
- Le séparateur de chemin imbriqué est `/` : `"config/database/pool"`.

### 2.3 Commentaires

```
# Commentaire sur une ligne (ignoré par le parser)

/* Commentaire
   sur plusieurs
   lignes */

'clé' : "valeur"  # commentaire inline (après la valeur)
```

Le commentaire `# fmt:1` est un **cas spécial** : il est détecté avant le prétraitement et ne doit pas être confondu avec un commentaire ordinaire.

### 2.4 Système de types

La règle est simple et sans exception :

```
┌──────────────────────────────────────────────────────────────┐
│  Valeur entre guillemets " → toujours str, aucune inférence │
│  Valeur sans guillemets   → inférence automatique du type   │
└──────────────────────────────────────────────────────────────┘
```

**Tableau d'inférence (valeur non quotée) :**

| Valeur dans le fichier | Type Python | Exemple |
|------------------------|-------------|---------|
| `"texte"` | `str` | `"Bonjour"` → `"Bonjour"` |
| `"42"` | `str` (forcé !) | `"42"` → `"42"` |
| `42` | `int` | `42` → `42` |
| `3.14` | `float` | `3.14` → `3.14` |
| `true` / `false` | `bool` | `true` → `True` |
| `null` / `none` | `None` | `null` → `None` |
| `""` (quoté vide) | `str` | `""` → `""` |
| (vide non quoté) | `None` | → `None` |

**Exemples dans un fichier :**

```
section : "types"
[
'nom'     : "Alice"     # str  "Alice"  (quoté)
'age'     : 30          # int  30       (non quoté)
'ratio'   : 0.85        # float 0.85   (non quoté)
'actif'   : true        # bool True    (non quoté)
'fin'     : null        # None         (non quoté)
'code'    : "42"        # str  "42"    (quoté → reste str)
'vide'    : ""          # str  ""      (chaîne vide explicite)
]
```

**Sérialisation (writer) :**

```python
str   → "valeur"    # toujours entre guillemets doubles
int   → 42          # sans guillemets
float → 3.14        # sans guillemets
bool  → true/false  # sans guillemets, minuscule
None  → null        # sans guillemets
```

---

## 3. Sections imbriquées et profondeur

### 3.1 Principe

Une `FMTSection` peut contenir à la fois des **entrées** (paires clé/valeur) et des **sous-sections**. Il n'y a pas de contrainte sur leur ordre ou leur mélange.

```
section : "config"
[
'debug' : false          ← entrée au niveau 1

  section : "database"   ← sous-section au niveau 2
  [
  'host' : "localhost"
  'port' : 5432

    section : "pool"     ← sous-sous-section au niveau 3
    [
    'min' : 2
    'max' : 10
    ]
  ]

  section : "cache"      ← autre sous-section au niveau 2
  [
  'ttl' : 300
  ]
]
```

### 3.2 Niveaux de profondeur (depth)

La **profondeur** (depth) mesure le nombre de niveaux d'imbrication d'une section dans le document.

```
FMT document (racine — depth 0)
│
├── section : "config"              depth 1  ← sections principales
│   [
│   'debug' : false                 ← entrées à depth 1
│   │
│   └── section : "database"        depth 2  ← sous-sections
│       [
│       'host' : "localhost"        ← entrées à depth 2
│       │
│       └── section : "pool"        depth 3  ← sous-sous-sections
│           [
│           'min' : 2               ← entrées à depth 3
│           ]
│       ]                           ← FIN depth 3
│   ]                               ← FIN depth 2
│
└── section : "fr"                  depth 1
    [
    '1' : "Bonjour"
    ]
```

**Règles de depth :**

| depth | Description |
|-------|-------------|
| 0 | Document racine (objet `FMT`) |
| 1 | Sections principales (`doc.add_section(...)`) |
| 2 | Sous-sections directes (`sec.add_section(...)`) |
| 3 | Sous-sous-sections (max par défaut) |
| ... | Jusqu'à `max_depth` (configurable, max absolu = 10) |

**`max_depth` par défaut = 3.** Tenter de créer une section à `depth > max_depth` lève `FMTDepthError`.

### 3.3 Navigation par chemin

Le séparateur `/` permet de naviguer dans l'arbre de sections sans chaîner les appels :

```python
# Navigation objet (équivalent)
doc.section("config").section("database").section("pool").get("min")

# Navigation par chemin (raccourci)
doc.section("config/database/pool").get("min")

# Raccourci complet
doc.get("config/database/pool", "min")

# has_section avec chemin
doc.has_section("config/database")   # True
doc.has_section("config/database/pool/timeout")  # False si absent
```

La navigation par chemin fonctionne sur `FMT` et sur `FMTSection` :

```python
db = doc.section("config/database")
pool = db.section("pool")            # navigation relative
```

### 3.4 Limites et configuration

```python
# Configurer max_depth à la création
doc = fmt.new("Config", "Prod", max_depth=5)

# Configurer max_depth au chargement
doc = fmt.load("config.fmt", max_depth=5)

# Parser avec max_depth personnalisé
doc = fmt.parse(texte, max_depth=1)  # sections plates uniquement
```

| max_depth | Signification |
|-----------|---------------|
| 1 | Aucune sous-section possible (sections plates uniquement) |
| 2 | 1 niveau de sous-sections |
| 3 | 2 niveaux de sous-sections (défaut) |
| N | N-1 niveaux de sous-sections |
| 10 | Plafond absolu (même si max_depth > 10 est passé) |

---

## 4. Structure de l'architecture interne

```
fmt/
├── __init__.py        Interface publique : load, parse, new, validate
├── spec.py            Constantes du format (version, encodage, séparateur…)
├── _types.py          Système de types : FMTType, FMTValue, infer_value, serialize_value
├── exceptions.py      Hiérarchie d'exceptions (8 classes)
├── _core.py           Structures de données : FMTSection (récursif) + FMT
├── _parser.py         Parser récursif avec line_map pour les numéros de ligne réels
├── _writer.py         Writer avec indentation récursive et types propres
└── _validator.py      Validateur optionnel (schéma structurel)
```

**Flux de données :**

```
Fichier .fmt  ──[parse_file]──►  _FMTParser  ──►  FMT + FMTSection[]
                                                          │
                                                          ▼
                                               Opérations utilisateur
                                                          │
                                                          ▼
Fichier .fmt  ◄──[to_file]────  FMTWriter  ◄───────────  FMT
```

**Séparation des responsabilités :**

| Fichier | Rôle | Dépend de |
|---------|------|-----------|
| `spec.py` | Constantes uniquement | rien |
| `_types.py` | Inférence et sérialisation des types | `spec` |
| `exceptions.py` | Hiérarchie d'erreurs | rien |
| `_core.py` | Modèle de données | `_types`, `spec`, `exceptions` |
| `_parser.py` | Lecture .fmt → FMT | `_core`, `_types`, `exceptions`, `spec` |
| `_writer.py` | FMT → texte .fmt | `_core`, `_types`, `exceptions`, `spec` |
| `_validator.py` | Validation structurelle | `_core` (TYPE_CHECKING) |
| `__init__.py` | API publique | tous |

---

## 5. Guide d'utilisation

### 5.1 Création d'un document

```python
import fmt

# Document vide avec titre
doc = fmt.new("Dataset", "Paires Français-Anglais")

# Avec profondeur maximale personnalisée
doc = fmt.new("Config", "Production", max_depth=5)
```

### 5.2 Chargement d'un fichier

```python
# Chargement simple
doc = fmt.load("data.fmt")

# Mode strict : erreur sur toute ligne non reconnue
doc = fmt.load("data.fmt", strict=True)

# Avec profondeur maximale
doc = fmt.load("config.fmt", max_depth=5)

# Depuis une chaîne
doc = fmt.parse(texte_fmt)
doc = fmt.parse(texte_fmt, strict=True, max_depth=4)
```

### 5.3 Lecture des données

```python
# Accès à une section
sec = doc.section("fr")
sec = doc.section("config/database")   # chemin imbriqué

# Vérifier l'existence
doc.has_section("fr")                  # True/False
doc.has_section("config/database")    # supporte les chemins

# Lire une valeur
val = sec.get("1")                     # None si absente
val = sec.get("1", "défaut")          # avec valeur par défaut
val = sec.get_or_raise("1")           # lève FMTEntryNotFoundError si absente

# Raccourci (section + get)
val = doc.get("fr", "1")
val = doc.get("config/database", "host")

# Lecture typée (lève FMTTypeError si mauvais type)
n   = sec.get_int("port")
f   = sec.get_float("ratio")
b   = sec.get_bool("debug")
s   = sec.get_str("nom")

# Informations
sec.keys()                             # ['1', '2', '3']
sec.count()                            # 3  (entrées directes)
sec.total_entry_count()               # N  (récursif)
sec.has("1")                           # True
sec.section_names()                    # ['sub1', 'sub2']
sec.depth                              # 1, 2, 3...
doc.section_names()                    # sections de niveau 1
doc.info()                             # dict récapitulatif
```

### 5.4 Écriture et modification

```python
# Ajouter / modifier une entrée
sec.set("host", "localhost")
sec.set("port", 5432)                  # int stocké en tant qu'int
sec.set("debug", True)                 # bool
sec.set("tag", "42")                   # str (pas int !)

# Chaînage
sec.set("a", 1).set("b", 2).set("c", True)

# Ajouter avec clé numérique auto
key = sec.append("Bonjour")           # key == "1" (ou suivant)
key = doc.append_to("fr", "Bonjour") # raccourci

# Supprimer une entrée
sec.remove("clé")
doc.remove_entry("fr", "clé")

# Vider les entrées (garde les sous-sections)
sec.clear()

# Vider tout (entrées + sous-sections)
sec.clear_all()

# Modifier le titre
doc.set_title("Nouvelle valeur")
doc.set_title_key("Nouveau label")

# Raccourci set depuis FMT
doc.set("fr", "1", "Bonjour modifié")
```

### 5.5 Sections imbriquées

```python
# Créer des sections imbriquées
config = doc.add_section("config")
db     = config.add_section("database")   # depth 2
pool   = db.add_section("pool")           # depth 3

pool.set("min", 2).set("max", 10)

# get_or_add (idempotent)
cache = config.get_or_add_section("cache")

# Accès
doc.section("config/database/pool").get("min")   # 2
doc.get("config/database/pool", "max")           # 10

# Vérification
db.has_section("pool")                           # True
db.section_names()                               # ['pool']
db.subsection_count()                            # 1

# Supprimer une sous-section
db.remove_section("pool")

# Opérations au niveau FMT
doc.rename_section("config", "configuration")
doc.copy_section("fr", "fr_backup")
doc.remove_section("fr_backup")
doc.merge(autre_doc)
doc.merge(autre_doc, overwrite=True)
```

### 5.6 Métadonnées

```python
# Lire
doc.has_meta("infos")                   # True
doc.meta("auteur").get("nom")           # "Dupont"
doc.get_meta_entry("infos", "version") # 1.0

# Écrire
meta = doc.add_meta("stats")
meta.set("total", 100).set("actif", True)
doc.set_meta("stats", "total", 200)

# get_or_add
meta = doc.get_or_add_meta("config")

# Liste
doc.meta_names()                        # ['auteur', 'infos']
```

### 5.7 Sauvegarde

```python
# Sauvegarder sur le disque (UTF-8, sans BOM, retours Unix)
doc.save("data.fmt")

# Obtenir le texte sans écrire sur le disque
texte = doc.to_string()

# Afficher dans la console
doc.print_all()
doc.print_title()
doc.print_section("config")
doc.section("config").print()
```

---

## 6. Référence API complète

### 6.1 Fonctions du module

```python
fmt.load(path, *, strict=False, max_depth=3)  → FMT
fmt.parse(text, *, strict=False, max_depth=3) → FMT
fmt.new(title_key, title_value, *, max_depth=3) → FMT
fmt.validate(doc, schema) → list[str]
```

### 6.2 Classe FMT

#### Titre
| Méthode / Propriété | Retour | Description |
|---------------------|--------|-------------|
| `.title` | `tuple[str,str]` | `(clé, valeur)` |
| `.title_key` | `str` | Label du titre |
| `.title_value` | `str` | Valeur du titre |
| `.set_title(val)` | `FMT` | Modifie la valeur (chaînable) |
| `.set_title_key(key)` | `FMT` | Modifie le label (chaînable) |

#### Sections
| Méthode | Retour | Description |
|---------|--------|-------------|
| `.section(path)` | `FMTSection` | Section ou chemin `/` |
| `.has_section(path)` | `bool` | Existence (supporte chemin) |
| `.add_section(name)` | `FMTSection` | Crée et retourne |
| `.get_or_add_section(name)` | `FMTSection` | Crée si absent |
| `.remove_section(name)` | `FMT` | Supprime |
| `.rename_section(old, new)` | `FMT` | Renomme |
| `.copy_section(src, dst)` | `FMTSection` | Duplique (deep copy) |
| `.section_names()` | `list[str]` | Noms niveau 1 |
| `.merge(other, overwrite=False)` | `FMT` | Fusionne |

#### Raccourcis entrées
| Méthode | Retour | Description |
|---------|--------|-------------|
| `.get(path, key, default=None)` | `FMTValue` | Lecture |
| `.set(path, key, value)` | `FMT` | Écriture |
| `.append_to(path, value)` | `str` | Ajout auto |
| `.remove_entry(path, key)` | `FMT` | Suppression |
| `.get_pairs(path_a, path_b)` | `list[tuple]` | Paires alignées |

#### Métadonnées
| Méthode | Retour | Description |
|---------|--------|-------------|
| `.meta(name)` | `FMTSection` | Section meta |
| `.has_meta(name)` | `bool` | Existence |
| `.add_meta(name)` | `FMTSection` | Crée |
| `.get_or_add_meta(name)` | `FMTSection` | Crée si absent |
| `.set_meta(sec, key, val)` | `FMT` | Raccourci écriture |
| `.get_meta_entry(sec, key, default)` | `FMTValue` | Raccourci lecture |
| `.meta_names()` | `list[str]` | Noms des sections meta |

#### Persistance / affichage
| Méthode | Retour | Description |
|---------|--------|-------------|
| `.save(path)` | `None` | Écrit le fichier |
| `.to_string()` | `str` | Texte .fmt |
| `.info()` | `dict` | Récapitulatif |
| `.print_all()` | `None` | Affichage complet |
| `.print_section(path)` | `None` | Affiche une section |
| `.print_title()` | `None` | Affiche le titre |

### 6.3 Classe FMTSection

#### Entrées
| Méthode | Retour | Description |
|---------|--------|-------------|
| `.get(key, default=None)` | `FMTValue` | Lecture |
| `.get_or_raise(key)` | `FMTValue` | Lecture (lève si absent) |
| `.get_str(key, default="")` | `str` | Lecture forcée str |
| `.get_int(key)` | `int` | Lecture typée |
| `.get_float(key)` | `float` | Lecture typée |
| `.get_bool(key)` | `bool` | Lecture typée |
| `.set(key, value)` | `FMTSection` | Écriture (chaînable) |
| `.append(value)` | `str` | Clé auto (chaînable) |
| `.remove(key)` | `FMTSection` | Suppression |
| `.clear()` | `FMTSection` | Vide les entrées |
| `.clear_all()` | `FMTSection` | Vide tout |
| `.has(key)` | `bool` | Existence |
| `.keys()` | `list[str]` | Liste des clés |
| `.all_entries()` | `dict` | Copie du dictionnaire |
| `.count()` | `int` | Nombre d'entrées directes |
| `.total_entry_count()` | `int` | Récursif (inclut sous-sections) |
| `.next_key()` | `str` | Prochaine clé numérique |

#### Sous-sections
| Méthode | Retour | Description |
|---------|--------|-------------|
| `.section(path)` | `FMTSection` | Accès (supporte chemin /) |
| `.has_section(name)` | `bool` | Existence directe |
| `.add_section(name)` | `FMTSection` | Crée (lève si existe ou depth max) |
| `.get_or_add_section(name)` | `FMTSection` | Crée si absent |
| `.remove_section(name)` | `FMTSection` | Supprime |
| `.rename(new_name)` | `FMTSection` | Renomme (chaînable) |
| `.section_names()` | `list[str]` | Noms des sous-sections directes |
| `.subsection_count()` | `int` | Nombre de sous-sections directes |

#### Propriétés et protocoles
| Attribut / Méthode | Type | Description |
|--------------------|------|-------------|
| `.name` | `str` | Nom (lecture seule) |
| `.depth` | `int` | Profondeur dans l'arbre |
| `.info()` | `dict` | Récapitulatif |
| `.print(_indent)` | `None` | Affichage indenté |
| `len(sec)` | `int` | Nombre d'entrées directes |
| `key in sec` | `bool` | Existence d'une clé |
| `for k, v in sec` | — | Itère sur les entrées |
| `sec1 == sec2` | `bool` | Égalité structurelle |

### 6.4 Système de types

```python
from fmt._types import FMTType, FMTValue, infer_value, serialize_value, get_fmt_type

# Enum des types
FMTType.STRING   # "str"
FMTType.INTEGER  # "int"
FMTType.FLOAT    # "float"
FMTType.BOOLEAN  # "bool"
FMTType.NULL     # "null"

# Inférer depuis le fichier
infer_value("42",   quoted=False)  # → 42  (int)
infer_value("42",   quoted=True)   # → "42" (str)
infer_value("true", quoted=False)  # → True (bool)

# Sérialiser pour le fichier
serialize_value(42)      # "42"
serialize_value(True)    # "true"
serialize_value("42")    # '"42"'
serialize_value(None)    # "null"

# Obtenir le type d'une valeur
get_fmt_type(42)         # FMTType.INTEGER
get_fmt_type("hello")    # FMTType.STRING
get_fmt_type(True)       # FMTType.BOOLEAN
```

### 6.5 Validateur

```python
schema = {
    "sections": {
        "config": {
            "required": True,
            "required_keys": ["host", "port"],
            "allowed_keys": ["host", "port", "debug"],
            "subsections": {
                "pool": {
                    "required": True,
                    "required_keys": ["min", "max"]
                }
            }
        }
    },
    "metadata": {
        "infos": {
            "required_keys": ["version", "date"]
        }
    }
}

errors = fmt.validate(doc, schema)
for e in errors:
    print("❌", e)
```

**Clés de schéma disponibles :**

| Clé | Type | Description |
|-----|------|-------------|
| `required` | `bool` | La section doit exister |
| `required_keys` | `list[str]` | Clés obligatoires dans la section |
| `allowed_keys` | `list[str]` | Clés autorisées (None = toutes) |
| `subsections` | `dict` | Sous-schéma récursif pour les sous-sections |

---

## 7. Référence des erreurs

Toutes les exceptions héritent de `FMTError` :

```python
try:
    doc = fmt.load("config.fmt")
    val = doc.get("config/database", "host")
except fmt.FMTError as e:
    print(f"Erreur fmt : {e}")
```

| Exception | Cause | Attributs utiles |
|-----------|-------|-----------------|
| `FMTSyntaxError` | Syntaxe invalide dans le fichier | `.line_number`, `.line_content`, `.hint` |
| `FMTFileError` | Fichier inaccessible | `.path`, `.reason` |
| `FMTSectionNotFoundError` | Section introuvable | `.name`, `.available`, `.path` |
| `FMTEntryNotFoundError` | Clé introuvable | `.key`, `.section_name` |
| `FMTDuplicateSectionError` | Section déjà existante | `.name`, `.parent` |
| `FMTDepthError` | Profondeur maximale dépassée | `.name`, `.current_depth`, `.max_depth` |
| `FMTTypeError` | Type inattendu | `.key`, `.expected`, `.got` |
| `FMTPathError` | Chemin invalide ou vide | `.path` |

**Exemple avec attributs :**

```python
try:
    doc.section("config/database/pool/timeout")
except fmt.FMTSectionNotFoundError as e:
    print(f"'{e.name}' introuvable")
    print(f"Disponibles : {e.available}")
    print(f"Chemin tenté : {e.path}")

try:
    sec.add_section("deep")
except fmt.FMTDepthError as e:
    print(f"Depth {e.current_depth} ≥ max {e.max_depth}")
    print(f"💡 Utilisez max_depth={e.max_depth + 1}")
```

**Mode strict vs permissif :**

```python
# Permissif (défaut) : lignes inconnues ignorées silencieusement
doc = fmt.load("data.fmt")

# Strict : FMTSyntaxError sur toute ligne non reconnue
doc = fmt.load("data.fmt", strict=True)

# Clés dupliquées : warning en permissif, FMTSyntaxError en strict
import warnings
with warnings.catch_warnings(record=True) as w:
    doc = fmt.parse(contenu_avec_doublons, strict=False)
    # w[0].category == UserWarning
```

---

## 8. Exemples de fichiers .fmt

### Dataset de traduction

```
# fmt:1
"Dataset" : "Paires Français-Anglais"

section : "fr"
[
'1' : "Bonjour, comment allez-vous ?"
'2' : "Le chat est sur le tapis."
'3' : "J'adore apprendre de nouvelles langues."
]

section : "en"
[
'1' : "Hello, how are you?"
'2' : "The cat is on the rug."
'3' : "I love learning new languages."
]

{
  section : "auteur"
  [
  'nom'    : "Dupont"
  'prénom' : "Alice"
  ]
  section : "infos"
  [
  'date'    : "2026-06-15"
  'version' : 1.0
  'paires'  : 3
  ]
}
```

### Fichier de configuration avec sous-sections

```
# fmt:1
"Config" : "Serveur de production"

section : "server"
[
'host' : "0.0.0.0"
'port' : 443
'debug' : false

  section : "tls"
  [
  'enabled' : true
  'cert'    : "/etc/ssl/server.crt"
  'key'     : "/etc/ssl/server.key"
  ]

  section : "rate_limit"
  [
  'enabled'  : true
  'requests' : 100
  'window'   : 60
  ]
]

section : "database"
[
'url'  : "postgresql://localhost/mydb"
'pool' : 5

  section : "replica"
  [
  'url'  : "postgresql://replica/mydb"
  'pool' : 2
  ]
]

/* Journalisation */
section : "logging"
[
'level'  : "info"
'file'   : "/var/log/app.log"
'rotate' : true
]

{
  section : "déploiement"
  [
  'version'     : "2.1.0"
  'date'        : "2026-06-15"
  'environnement' : "production"
  ]
}
```

---

## 9. Migration depuis la v1

### Changements majeurs

#### 1. Système de types (BREAKING)

```
# v1 : toutes les valeurs sans guillemets étaient inférées
#       et toutes les valeurs AVEC guillemets aussi (via _parse_value)
'version' : "1.0"    → float 1.0   ← COMPORTEMENT v1

# v2 : valeur entre guillemets = TOUJOURS str
'version' : "1.0"    → str "1.0"   ← COMPORTEMENT v2
'version' : 1.0      → float 1.0   ← pour avoir un float, ne pas quoter
```

**Action requise :** revoir les fichiers existants où des nombres/booléens
sont stockés entre guillemets et que vous attendez un type numérique.

#### 2. Writer (amélioration transparente)

```
# v1 : tout était sérialisé entre guillemets
'port' : "5432"    ← v1 (incorrect sémantiquement)
'debug' : "true"   ← v1

# v2 : types préservés
'port' : 5432      ← v2
'debug' : true     ← v2
```

Les fichiers écrits en v2 sont toujours lisibles en v2.
Les fichiers écrits en v1 sont lisibles en v2 **avec changement de type** pour les valeurs numériques entre guillemets.

#### 3. Nouvelles exceptions

| v1 | v2 |
|----|----|
| — | `FMTDepthError` (profondeur dépassée) |
| — | `FMTTypeError` (type inattendu) |
| — | `FMTPathError` (chemin invalide) |

#### 4. `to_file()` / `save()` ne pollue plus stdout

```python
# v1 : affichait "✅ Fichier sauvegardé : ..." sur stdout (bug)
# v2 : silencieux — à l'appelant de gérer le feedback
doc.save("data.fmt")
```

#### 5. Nouvelles fonctionnalités (sans impact sur le code existant)

- Sections imbriquées (`add_section` sur `FMTSection`)
- Navigation par chemin (`doc.section("a/b/c")`)
- `max_depth` configurable
- `rename_section`, `copy_section`, `merge` sur `FMT`
- `get_int`, `get_float`, `get_bool`, `get_str` sur `FMTSection`
- `clear_all`, `total_entry_count`, `subsection_count`
- `__eq__` sur `FMT` et `FMTSection`
- `__iter__`, `__contains__`, `__len__` sur `FMTSection`
- `fmt.validate(doc, schema)`
- Magic `# fmt:N`
- Mode strict

### Guide de migration

```python
# Étape 1 : identifier les valeurs numériques stockées entre guillemets
# Chercher dans vos fichiers les patterns comme :
#   'version' : "1.0"   (float attendu)
#   'count'   : "42"    (int attendu)
#   'active'  : "true"  (bool attendu)

# Étape 2 : supprimer les guillemets autour des valeurs non-string
# Avant (v1 compatible) :
#   'count'  : "42"
# Après (v2) :
#   'count'  : 42

# Étape 3 : mettre à jour max_depth si vos fichiers ont des sous-sections
doc = fmt.load("config.fmt", max_depth=4)  # si profondeur > 3
```
