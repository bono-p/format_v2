"""
test_fmt.py — Suite de tests complète pour fmt v2

Couvre :
  G1  — Chargement et titre
  G2  — Sections de base et entrées
  G3  — Système de types (quoted vs unquoted)
  G4  — Sections imbriquées (création, lecture, chemin /)
  G5  — Profondeur maximale (FMTDepthError)
  G6  — Métadonnées
  G7  — Opérations sur les sections (rename, copy, remove, merge)
  G8  — Persistance et round-trip (write → load)
  G9  — Gestion des erreurs (exceptions)
  G10 — Mode strict
  G11 — Validateur (FMTValidator)
  G12 — API raccourcis et paires
  G13 — Protocoles Python (__eq__, __len__, __contains__, __iter__)
  G14 — Numéros de ligne réels dans les erreurs
"""

import sys
import os
import tempfile
import warnings

# Ajouter le dossier courant au path pour trouver le module fmt
sys.path.insert(0, os.path.dirname(__file__))
import fmt

# ── Couleurs console ──────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED   = "\033[91m"
CYAN  = "\033[96m"
BOLD  = "\033[1m"
RESET = "\033[0m"

# ── Compteurs ─────────────────────────────────────────────────────────────────
_passed = 0
_failed = 0
_total  = 0

def test(label: str, condition: bool, note: str = "") -> None:
    global _passed, _failed, _total
    _total += 1
    if condition:
        _passed += 1
        print(f"  {GREEN}✓{RESET} {label}")
    else:
        _failed += 1
        detail = f"  {RED}({note}){RESET}" if note else ""
        print(f"  {RED}✗ {label}{RESET}{detail}")

def group(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{title}{RESET}")


# ══════════════════════════════════════════════════════════════════════════════
#  Contenu de test v2
#  Note : les valeurs numériques/booléennes/null sont non quotées (inférence).
#         Les chaînes sont entre guillemets.
# ══════════════════════════════════════════════════════════════════════════════

CONTENU_V2 = """
# fmt:1
# Commentaire de fichier

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

section : "config"
[
'debug' : false
'version_api' : 2
'ratio' : 0.95

  section : "server"
  [
  'host' : "localhost"
  'port' : 8080

    section : "tls"
    [
    'enabled' : true
    'cert'    : "/etc/ssl/cert.pem"
    ]
  ]
]

/* Commentaire bloc multi-lignes
   ignoré par le parser */
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
  'vérifié' : true
  'vide'    : null
  ]
}
"""

# ══════════════════════════════════════════════════════════════════════════════
#  G1 — Chargement et titre
# ══════════════════════════════════════════════════════════════════════════════
group("G1 — Chargement et titre")

doc = fmt.parse(CONTENU_V2)

test("Parsing sans exception",                 doc is not None)
test("Titre key correct",                      doc.title_key   == "Dataset")
test("Titre value correct",                    doc.title_value == "Paires Français-Anglais")
test("Tuple title correct",                    doc.title       == ("Dataset", "Paires Français-Anglais"))
test("Version format détectée (# fmt:1)",      doc._fmt_version == 1)
test("max_depth par défaut = 3",               doc._max_depth == 3)

# ══════════════════════════════════════════════════════════════════════════════
#  G2 — Sections de base et entrées
# ══════════════════════════════════════════════════════════════════════════════
group("G2 — Sections de base et entrées")

test("Section 'fr' existe",                    doc.has_section("fr"))
test("Section 'en' existe",                    doc.has_section("en"))
test("Section 'config' existe",               doc.has_section("config"))
test("Lecture entrée fr/1",                    doc.get("fr", "1") == "Bonjour, comment allez-vous ?")
test("Lecture entrée en/2",                    doc.get("en", "2") == "The cat is on the rug.")
test("Clé absente → None",                    doc.section("fr").get("99") is None)
test("Clé absente → default",                 doc.section("fr").get("99", "X") == "X")
test("has() clé présente",                    doc.section("fr").has("1"))
test("has() clé absente",                     not doc.section("fr").has("42"))
test("keys() retourne liste",                  doc.section("fr").keys() == ["1", "2", "3"])
test("count() correct",                       doc.section("fr").count() == 3)
test("section_names() correct",               "fr" in doc.section_names())
test("Insensibilité casse section",           doc.has_section("FR"))
test("Insensibilité casse accès",             doc.section("FR").get("1") == doc.section("fr").get("1"))

# ══════════════════════════════════════════════════════════════════════════════
#  G3 — Système de types
# ══════════════════════════════════════════════════════════════════════════════
group("G3 — Système de types (quoted=str, unquoted=inférence)")

test("Quoted '1.0' → str '1.0'",              doc.get("fr", "1") == "Bonjour, comment allez-vous ?")

# Types depuis la section config (non quotés)
test("debug : false → bool False",            doc.get("config", "debug")       == False)
test("debug est un bool",                     isinstance(doc.get("config", "debug"), bool))
test("version_api : 2 → int 2",              doc.get("config", "version_api") == 2)
test("version_api est un int",               isinstance(doc.get("config", "version_api"), int))
test("ratio : 0.95 → float",                 doc.get("config", "ratio")       == 0.95)
test("ratio est un float",                   isinstance(doc.get("config", "ratio"), float))
test("vide : null → None",                   doc.get_meta_entry("infos", "vide") is None)
test("vérifié : true → bool True",           doc.get_meta_entry("infos", "vérifié") == True)
test("version meta → float 1.0",             doc.get_meta_entry("infos", "version") == 1.0)
test("paires meta → int 3",                  doc.get_meta_entry("infos", "paires") == 3)

# get_str / get_int / get_float / get_bool
test("get_str() force str",                  doc.section("fr").get_str("1") == "Bonjour, comment allez-vous ?")
test("get_int() retourne int",               doc.section("config").get_int("version_api") == 2)
test("get_float() retourne float",           doc.section("config").get_float("ratio") == 0.95)
test("get_bool() retourne bool",             doc.section("config").get_bool("debug") == False)

# FMTTypeError
try:
    doc.section("fr").get_int("1")
    test("get_int sur str → FMTTypeError", False)
except fmt.FMTTypeError:
    test("get_int sur str → FMTTypeError", True)

# Chaîne vide quotée ≠ null
doc_vide = fmt.parse('"Test" : "T"\nsection : "s"\n[\n\'k\' : ""\n]\n')
test('Chaîne vide quotée "" → str ""',      doc_vide.get("s", "k") == "")
test('Chaîne vide quotée n\'est pas None',   doc_vide.get("s", "k") is not None)

# ══════════════════════════════════════════════════════════════════════════════
#  G4 — Sections imbriquées
# ══════════════════════════════════════════════════════════════════════════════
group("G4 — Sections imbriquées (création, lecture, chemin /)")

# Lecture depuis le contenu parsé
test("Sous-section 'server' dans 'config'",   doc.section("config").has_section("server"))
test("Accès direct config → server",          doc.section("config").section("server").get("host") == "localhost")
test("Accès chemin config/server",            doc.section("config/server").get("host") == "localhost")
test("Accès chemin config/server raccourci",  doc.get("config/server", "host") == "localhost")
test("Port server → int 8080",               doc.get("config/server", "port") == 8080)
test("has_section chemin imbriqué",           doc.has_section("config/server"))

# Sous-sous-section (depth 3)
test("Sous-sous-section 'tls'",              doc.has_section("config/server/tls"))
test("Accès config/server/tls",              doc.get("config/server/tls", "enabled") == True)
test("Cert tls → str",                       doc.get("config/server/tls", "cert") == "/etc/ssl/cert.pem")

# Création programmatique de sous-sections
doc2 = fmt.new("Test", "Imbrication")
db   = doc2.add_section("database")
test("add_section niveau 1",                  doc2.has_section("database"))

pool = db.add_section("pool")
pool.set("min", 2).set("max", 10)
test("add_section niveau 2",                  db.has_section("pool"))
test("Valeur dans sous-section",             doc2.get("database/pool", "min") == 2)
test("Chaînage set()",                       doc2.get("database/pool", "max") == 10)

logs = db.add_section("logs")
logs.set("level", "info")
test("Deux sous-sections dans db",            db.subsection_count() == 2)
test("section_names sous-sections",          db.section_names() == ["pool", "logs"])

# depth
test("Profondeur db = 1",                    db.depth == 1)
test("Profondeur pool = 2",                  pool.depth == 2)

# total_entry_count récursif
doc_cnt = fmt.parse(
    '"T":"T"\nsection:"a"\n[\n\'k\':1\nsection:"b"\n[\n\'x\':2\n\'y\':3\n]\n]\n'
)
test("total_entry_count récursif",           doc_cnt.section("a").total_entry_count() == 3)

# ══════════════════════════════════════════════════════════════════════════════
#  G5 — Profondeur maximale
# ══════════════════════════════════════════════════════════════════════════════
group("G5 — Profondeur maximale (FMTDepthError)")

doc3 = fmt.new("Test", "Depth", max_depth=2)
a = doc3.add_section("a")      # depth 1 — OK
b = a.add_section("b")         # depth 2 — OK (max atteint)
test("Depth 1 créé OK",                       doc3.has_section("a"))
test("Depth 2 créé OK",                       a.has_section("b"))

try:
    b.add_section("c")         # depth 3 — dépasse max_depth=2
    test("FMTDepthError levée",               False)
except fmt.FMTDepthError as e:
    test("FMTDepthError levée",               True)
    test("FMTDepthError.current_depth == 2", e.current_depth == 2)
    test("FMTDepthError.max_depth == 2",     e.max_depth == 2)
    test("FMTDepthError.name == 'c'",        e.name == "c")

# FMTDepthError depuis le parser
contenu_trop_profond = (
    '"T":"T"\n'
    'section:"a"\n[\n'
    '  section:"b"\n[\n'
    '    section:"c"\n[\n'
    '      section:"d"\n[\n'       # depth 4 > max_depth=3
    '      \'k\':1\n'
    '      ]\n'
    '    ]\n'
    '  ]\n'
    ']\n'
)
try:
    fmt.parse(contenu_trop_profond, max_depth=3)
    test("Parser lève FMTDepthError",         False)
except fmt.FMTDepthError:
    test("Parser lève FMTDepthError",         True)

# max_depth=1 : aucune sous-section possible
doc4 = fmt.new("T", "T", max_depth=1)
sec4 = doc4.add_section("s")
try:
    sec4.add_section("sub")
    test("max_depth=1 bloque sous-section",   False)
except fmt.FMTDepthError:
    test("max_depth=1 bloque sous-section",   True)

# ══════════════════════════════════════════════════════════════════════════════
#  G6 — Métadonnées
# ══════════════════════════════════════════════════════════════════════════════
group("G6 — Métadonnées")

test("Section meta 'auteur' existe",          doc.has_meta("auteur"))
test("Section meta 'infos' existe",           doc.has_meta("infos"))
test("Lecture meta auteur/nom",               doc.get_meta_entry("auteur", "nom") == "Dupont")
test("Lecture meta auteur/prénom",            doc.get_meta_entry("auteur", "prénom") == "Alice")
test("meta_names() correct",                  "auteur" in doc.meta_names())

doc5 = fmt.new("T", "T")
meta = doc5.add_meta("stats")
meta.set("total", 42).set("actif", True)
test("add_meta crée section",                 doc5.has_meta("stats"))
test("Valeur dans meta",                      doc5.get_meta_entry("stats", "total") == 42)
test("set_meta fonctionne",                   doc5.set_meta("stats", "actif", False).get_meta_entry("stats", "actif") == False)

# ══════════════════════════════════════════════════════════════════════════════
#  G7 — Opérations sur les sections
# ══════════════════════════════════════════════════════════════════════════════
group("G7 — Opérations : rename, copy, remove, merge")

d = fmt.new("T", "T")
d.add_section("original").set("clé", "valeur")

# rename_section
d.rename_section("original", "renommée")
test("rename_section fonctionne",             d.has_section("renommée"))
test("Ancien nom disparu après rename",       not d.has_section("original"))

# copy_section
d.copy_section("renommée", "copie")
test("copy_section crée une copie",           d.has_section("copie"))
test("Copie indépendante (deepcopy)",         d.section("copie") is not d.section("renommée"))
test("Copie a les mêmes valeurs",             d.get("copie", "clé") == "valeur")

# Modification de la copie n'affecte pas l'original
d.section("copie").set("clé", "modifié")
test("Modif copie n'affecte pas original",    d.get("renommée", "clé") == "valeur")

# remove_section
d.remove_section("copie")
test("remove_section supprime la section",    not d.has_section("copie"))

# remove_section absente → FMTSectionNotFoundError
try:
    d.remove_section("inexistante")
    test("remove absente → FMTSectionNotFoundError", False)
except fmt.FMTSectionNotFoundError:
    test("remove absente → FMTSectionNotFoundError", True)

# merge
src = fmt.new("S", "S")
src.add_section("extra").set("x", 1)
d.merge(src)
test("merge ajoute section absente",          d.has_section("extra"))
test("Valeur après merge",                    d.get("extra", "x") == 1)

# merge sans overwrite : section existante non écrasée
src2 = fmt.new("S2", "S2")
src2.add_section("renommée").set("clé", "ÉCRASÉ")
d.merge(src2, overwrite=False)
test("merge sans overwrite préserve l'original", d.get("renommée", "clé") == "valeur")

# merge avec overwrite
d.merge(src2, overwrite=True)
test("merge avec overwrite écrase",           d.get("renommée", "clé") == "ÉCRASÉ")

# FMTDuplicateSectionError
try:
    d.add_section("extra")
    test("add_section dupliquée → FMTDuplicateSectionError", False)
except fmt.FMTDuplicateSectionError:
    test("add_section dupliquée → FMTDuplicateSectionError", True)

# FMTDuplicateSectionError sous-section
try:
    d.section("extra").add_section("a")
    d.section("extra").add_section("a")
    test("add_section dupliquée (sous-section) → FMTDuplicateSectionError", False)
except fmt.FMTDuplicateSectionError:
    test("add_section dupliquée (sous-section) → FMTDuplicateSectionError", True)

# get_or_add_section (ne lève pas)
s1 = d.get_or_add_section("nouvelle")
s2 = d.get_or_add_section("nouvelle")
test("get_or_add_section retourne existante", s1 is s2)

# ══════════════════════════════════════════════════════════════════════════════
#  G8 — Persistance et round-trip
# ══════════════════════════════════════════════════════════════════════════════
group("G8 — Persistance et round-trip (write → load)")

with tempfile.TemporaryDirectory() as tmpdir:
    path = os.path.join(tmpdir, "test.fmt")
    doc.save(path)

    test("Fichier créé",                      os.path.exists(path))

    doc_r = fmt.load(path)

    test("Titre préservé après reload",        doc_r.title_value == doc.title_value)
    test("fr/1 préservée",                    doc_r.get("fr", "1") == doc.get("fr", "1"))
    test("en/2 préservée",                    doc_r.get("en", "2") == doc.get("en", "2"))
    test("config/debug bool préservé",        doc_r.get("config", "debug")       == False)
    test("config/version_api int préservé",   doc_r.get("config", "version_api") == 2)
    test("config/ratio float préservé",       doc_r.get("config", "ratio")       == 0.95)

    # Round-trip sous-sections
    test("config/server/host préservé",       doc_r.get("config/server", "host")       == "localhost")
    test("config/server/port int préservé",   doc_r.get("config/server", "port")       == 8080)
    test("config/server/tls/enabled préservé",doc_r.get("config/server/tls", "enabled") == True)

    # Round-trip métadonnées
    test("meta version float préservée",      doc_r.get_meta_entry("infos", "version") == 1.0)
    test("meta paires int préservé",          doc_r.get_meta_entry("infos", "paires")  == 3)
    test("meta vérifié bool préservé",        doc_r.get_meta_entry("infos", "vérifié") == True)
    test("meta vide None préservé",           doc_r.get_meta_entry("infos", "vide")    is None)

    # Round-trip chaîne qui ressemble à un nombre
    doc_str = fmt.new("T", "T")
    doc_str.add_section("s").set("code", "42")   # str "42", pas int
    doc_str.save(path)
    doc_str2 = fmt.load(path)
    test('Round-trip str "42" reste str',     doc_str2.get("s", "code") == "42")
    test('Round-trip str "42" est bien str',  isinstance(doc_str2.get("s", "code"), str))

    # to_string puis parse → même résultat
    texte = doc.to_string()
    doc_ts = fmt.parse(texte)
    test("to_string → parse cohérent",        doc_ts.title_value == doc.title_value)
    test("to_string → sections identiques",   doc_ts.section_names() == doc.section_names())
    test("to_string → sous-sections OK",      doc_ts.has_section("config/server"))

# ══════════════════════════════════════════════════════════════════════════════
#  G9 — Gestion des erreurs
# ══════════════════════════════════════════════════════════════════════════════
group("G9 — Gestion des erreurs (exceptions)")

# FMTSyntaxError : fichier vide
try:
    fmt.parse("")
    test("Fichier vide → FMTSyntaxError", False)
except fmt.FMTSyntaxError:
    test("Fichier vide → FMTSyntaxError", True)

# FMTSyntaxError : titre manquant
try:
    fmt.parse("section : \"s\"\n[\n]\n")
    test("Titre manquant → FMTSyntaxError", False)
except fmt.FMTSyntaxError:
    test("Titre manquant → FMTSyntaxError", True)

# FMTSyntaxError : crochet manquant
try:
    fmt.parse('"T":"T"\nsection:"s"\n')
    test("Crochet manquant → FMTSyntaxError", False)
except fmt.FMTSyntaxError:
    test("Crochet manquant → FMTSyntaxError", True)

# FMTSyntaxError : numéro de ligne renseigné
try:
    contenu = '"T":"T"\nsection:"s"\n'   # ligne 2 a le problème
    fmt.parse(contenu)
except fmt.FMTSyntaxError as e:
    test("FMTSyntaxError a un numéro de ligne", e.line_number is not None)

# FMTFileError : fichier inexistant
try:
    fmt.load("/chemin/inexistant/test.fmt")
    test("Fichier inexistant → FMTFileError", False)
except fmt.FMTFileError as e:
    test("Fichier inexistant → FMTFileError", True)
    test("FMTFileError.path renseigné",       e.path == "/chemin/inexistant/test.fmt")

# FMTSectionNotFoundError
try:
    doc.section("inexistante")
    test("Section inexistante → FMTSectionNotFoundError", False)
except fmt.FMTSectionNotFoundError as e:
    test("Section inexistante → FMTSectionNotFoundError", True)
    test("FMTSectionNotFoundError.name correct",  e.name == "inexistante")
    test("FMTSectionNotFoundError.available renseigné", len(e.available) > 0)

# FMTEntryNotFoundError
try:
    doc.section("fr").get_or_raise("999")
    test("Clé inexistante → FMTEntryNotFoundError", False)
except fmt.FMTEntryNotFoundError as e:
    test("Clé inexistante → FMTEntryNotFoundError", True)
    test("FMTEntryNotFoundError.key correct",      e.key == "999")

# FMTPathError
try:
    doc.section("")
    test("Chemin vide → FMTPathError", False)
except fmt.FMTPathError:
    test("Chemin vide → FMTPathError", True)

# FMTSyntaxError : ']' manquant dans un sous-bloc
try:
    fmt.parse('"T":"T"\nsection:"s"\n[\nsection:"sub"\n[\n\'k\':1\n]\n')
    # Manque le ']' final pour 's'
    test("']' manquant → FMTSyntaxError", False)
except fmt.FMTSyntaxError:
    test("']' manquant → FMTSyntaxError", True)

# FMTError est la base de toutes les exceptions
test("FMTSectionNotFoundError hérite FMTError",
     issubclass(fmt.FMTSectionNotFoundError, fmt.FMTError))
test("FMTDepthError hérite FMTError",
     issubclass(fmt.FMTDepthError, fmt.FMTError))
test("FMTTypeError hérite FMTError",
     issubclass(fmt.FMTTypeError, fmt.FMTError))

# ══════════════════════════════════════════════════════════════════════════════
#  G10 — Mode strict
# ══════════════════════════════════════════════════════════════════════════════
group("G10 — Mode strict")

# En mode permissif (défaut) les lignes inconnues sont ignorées
contenu_mixte = '"T":"T"\nLIGNE INCONNUE\nsection:"s"\n[\n\'k\':1\n]\n'
doc_perm = fmt.parse(contenu_mixte, strict=False)
test("Mode permissif : ligne inconnue ignorée", doc_perm.has_section("s"))

# En mode strict elles lèvent FMTSyntaxError
try:
    fmt.parse(contenu_mixte, strict=True)
    test("Mode strict : ligne inconnue → FMTSyntaxError", False)
except fmt.FMTSyntaxError:
    test("Mode strict : ligne inconnue → FMTSyntaxError", True)

# Clé dupliquée : warning en mode permissif, erreur en strict
contenu_dup = '"T":"T"\nsection:"s"\n[\n\'k\':1\n\'k\':2\n]\n'
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    doc_dup = fmt.parse(contenu_dup, strict=False)
    test("Clé dupliquée → UserWarning (mode permissif)", len(w) == 1)
    test("Dernière valeur conservée",                    doc_dup.get("s", "k") == 2)

try:
    fmt.parse(contenu_dup, strict=True)
    test("Clé dupliquée strict → FMTSyntaxError", False)
except fmt.FMTSyntaxError:
    test("Clé dupliquée strict → FMTSyntaxError", True)

# ══════════════════════════════════════════════════════════════════════════════
#  G11 — Validateur
# ══════════════════════════════════════════════════════════════════════════════
group("G11 — Validateur (FMTValidator)")

schema_ok = {
    "sections": {
        "fr": {"required": True},
        "en": {"required": True},
        "config": {
            "required": True,
            "required_keys": ["debug", "version_api"],
            "subsections": {
                "server": {
                    "required": True,
                    "required_keys": ["host", "port"],
                    "subsections": {
                        "tls": {"required_keys": ["enabled"]}
                    }
                }
            }
        }
    },
    "metadata": {
        "infos": {"required_keys": ["version", "date"]}
    }
}

errors = fmt.validate(doc, schema_ok)
test("Schéma valide → aucune erreur",         errors == [])

# Schéma avec section manquante
schema_bad = {"sections": {"introuvable": {"required": True}}}
errors2 = fmt.validate(doc, schema_bad)
test("Section manquante → 1 erreur",          len(errors2) == 1)
test("Erreur mentionne le nom",               "introuvable" in errors2[0])

# Clé requise absente
schema_cle = {
    "sections": {"fr": {"required_keys": ["1", "99_absent"]}}
}
errors3 = fmt.validate(doc, schema_cle)
test("Clé requise absente → erreur",          any("99_absent" in e for e in errors3))

# Clés autorisées
schema_allow = {
    "sections": {"fr": {"allowed_keys": ["1", "2"]}}  # '3' non autorisée
}
errors4 = fmt.validate(doc, schema_allow)
test("Clé non autorisée → erreur",            any("'3'" in e for e in errors4))

# ══════════════════════════════════════════════════════════════════════════════
#  G12 — API raccourcis et paires
# ══════════════════════════════════════════════════════════════════════════════
group("G12 — API raccourcis et paires")

d12 = fmt.new("T", "T")
fr  = d12.add_section("fr")
en  = d12.add_section("en")
fr.append("Bonjour")
fr.append("Au revoir")
en.append("Hello")
en.append("Goodbye")

test("append auto key '1'",                   fr.get("1") == "Bonjour")
test("append auto key '2'",                   fr.get("2") == "Au revoir")
test("next_key après 2 entrées",              fr.next_key() == "3")

pairs = d12.get_pairs("fr", "en")
test("get_pairs retourne 2 paires",           len(pairs) == 2)
test("get_pairs tuple correct",               pairs[0] == ("Bonjour", "Hello"))

# append_to raccourci
key = d12.append_to("fr", "Merci")
test("append_to retourne la clé",             key == "3")
test("Valeur ajoutée via append_to",          d12.get("fr", "3") == "Merci")

# remove_entry
d12.remove_entry("fr", "3")
test("remove_entry supprime l'entrée",        not d12.section("fr").has("3"))

# set raccourci
d12.set("fr", "1", "MODIFIÉ")
test("set raccourci modifie valeur",          d12.get("fr", "1") == "MODIFIÉ")

# get_or_add_section
sub = d12.section("fr")
sub2 = d12.section("fr")
test("section() retourne même objet",         sub is sub2)

# ══════════════════════════════════════════════════════════════════════════════
#  G13 — Protocoles Python
# ══════════════════════════════════════════════════════════════════════════════
group("G13 — Protocoles Python (__eq__, __len__, __contains__, __iter__)")

sec_a = fmt.parse('"T":"T"\nsection:"s"\n[\n\'x\':1\n\'y\':2\n]\n').section("s")
sec_b = fmt.parse('"T":"T"\nsection:"s"\n[\n\'x\':1\n\'y\':2\n]\n').section("s")
sec_c = fmt.parse('"T":"T"\nsection:"s"\n[\n\'x\':99\n]\n').section("s")

test("__eq__ deux sections identiques",       sec_a == sec_b)
test("__eq__ deux sections différentes",      sec_a != sec_c)
test("__len__ retourne count()",              len(sec_a) == 2)
test("__contains__ clé présente",             "x" in sec_a)
test("__contains__ clé absente",              "z" not in sec_a)

items = list(sec_a)
test("__iter__ retourne paires (clé, val)",   items == [("x", 1), ("y", 2)])

# __eq__ sur FMT
doc_e1 = fmt.parse('"T":"T"\nsection:"s"\n[\n\'k\':1\n]\n')
doc_e2 = fmt.parse('"T":"T"\nsection:"s"\n[\n\'k\':1\n]\n')
doc_e3 = fmt.parse('"T":"T"\nsection:"s"\n[\n\'k\':9\n]\n')
test("FMT.__eq__ identiques",                 doc_e1 == doc_e2)
test("FMT.__eq__ différents",                 doc_e1 != doc_e3)

# ══════════════════════════════════════════════════════════════════════════════
#  G14 — Numéros de ligne réels dans les erreurs
# ══════════════════════════════════════════════════════════════════════════════
group("G14 — Numéros de ligne réels")

# Fichier avec commentaires : la ligne en erreur est la 7e dans le fichier brut
# mais après prétraitement ce pourrait être la 2e — on vérifie que c'est 7.
contenu_lignes = (
    "# commentaire 1\n"      # ligne 1  (commentaire, ignoré)
    "# commentaire 2\n"      # ligne 2  (commentaire, ignoré)
    "# commentaire 3\n"      # ligne 3  (commentaire, ignoré)
    "# commentaire 4\n"      # ligne 4  (commentaire, ignoré)
    "# commentaire 5\n"      # ligne 5  (commentaire, ignoré)
    "# commentaire 6\n"      # ligne 6  (commentaire, ignoré)
    "section:\"s\"\n"        # ligne 7  ← pas de titre avant → erreur ici
    "[\n]\n"
)
try:
    fmt.parse(contenu_lignes, strict=True)
except fmt.FMTSyntaxError as e:
    test("Numéro de ligne réel = 7",          e.line_number == 7)

# ══════════════════════════════════════════════════════════════════════════════
#  Résumé
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{'═' * 54}")
pct = (_passed / _total * 100) if _total else 0
if _failed == 0:
    print(f"{BOLD}{GREEN}✅  {_passed}/{_total} tests réussis — 100% OK{RESET}")
else:
    print(
        f"{BOLD}{RED}❌  {_passed}/{_total} réussis — {_failed} échec(s) "
        f"({pct:.0f}%){RESET}"
    )
print(f"{'═' * 54}")

sys.exit(0 if _failed == 0 else 1)
