# fmt — Format de fichier structuré .fmt

Module Python pour lire, écrire et manipuler les fichiers `.fmt`,
un format texte hiérarchique avec sections imbriquées et types natifs.

## Installation

pip install git+https://github.com/bono-p/format_v2.git@main

## Exemple rapide

import fmt

doc = fmt.load("data.fmt")
doc.get("config/database", "host")   # accès imbriqué

## Documentation complète

Voir [DOCUMENTATION.md](DOCUMENTATION.md)

## Licence

LGPL v3 — © 2026 TonPseudo
Contributions bienvenues, modifications du module → code public obligatoire.
