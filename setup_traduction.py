"""Telecharge les modeles de traduction gratuits (Argos Translate) entre EN, ES, DE, FR."""
import argostranslate.package as pk

import json, pathlib
cfg = json.loads((pathlib.Path(__file__).parent / "config.json").read_text(encoding="utf-8"))
langs = [l for l in cfg["traduire_vers"] if l != "en"]
pk.update_package_index()
dispo = pk.get_available_packages()
voulu = {("en", l) for l in langs} | {(l, "en") for l in langs}
for p in dispo:
    if (p.from_code, p.to_code) in voulu:
        print(f"Installation {p.from_code} -> {p.to_code} ...")
        pk.install_from_path(p.download())
print("Traduction prete (toutes langues passent par l'anglais).")
