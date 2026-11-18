"""
ViceClips - Relier les chaines YouTube au bot (a lancer UNE fois sur ton PC).
1. Cherche le fichier client_secret_*.json (Telechargements ou ce dossier)
2. Pour chaque langue : ouvre Google, tu choisis la chaine ViceClips XX, tu cliques Autoriser
3. Fabrique UN code (YOUTUBE_SECRET) copie dans le presse-papiers + ouvre la page GitHub
Aucune dependance : Python standard uniquement.
"""
import glob, http.server, json, os, subprocess, sys, threading, urllib.parse, urllib.request, webbrowser

LANGUES = ["en", "es", "de", "fr", "ar"]
SCOPE = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"
PORT = 8765
REDIRECT = f"http://127.0.0.1:{PORT}/"
ICI = os.path.dirname(os.path.abspath(__file__))


def trouver_client():
    lieux = [ICI, os.path.join(os.path.expanduser("~"), "Downloads"),
             os.path.join(os.path.expanduser("~"), "Téléchargements")]
    for d in lieux:
        f = sorted(glob.glob(os.path.join(d, "client_secret*.json")), key=os.path.getmtime)
        if f:
            data = json.load(open(f[-1], encoding="utf-8"))
            c = data.get("installed") or data.get("web")
            print(f"Cle trouvee : {f[-1]}")
            return c["client_id"], c["client_secret"]
    sys.exit("Fichier client_secret_....json introuvable. Mets-le dans ce dossier ou dans Telechargements.")


class Recepteur(http.server.BaseHTTPRequestHandler):
    code = None

    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        Recepteur.code = (q.get("code") or [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = "OK ! Chaine reliee. Tu peux fermer cet onglet et revenir a la fenetre noire." if Recepteur.code \
            else "Refuse ou erreur. Reviens a la fenetre noire."
        self.wfile.write(f"<h2 style='font-family:sans-serif'>{msg}</h2>".encode())

    def log_message(self, *a):
        pass


def post(url, data):
    req = urllib.request.Request(url, urllib.parse.urlencode(data).encode())
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def autoriser(cid, csec, lang):
    params = {"client_id": cid, "redirect_uri": REDIRECT, "response_type": "code", "scope": SCOPE,
              "access_type": "offline", "prompt": "consent select_account"}
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    srv = http.server.HTTPServer(("127.0.0.1", PORT), Recepteur)
    Recepteur.code = None
    th = threading.Thread(target=srv.handle_request); th.start()
    print(f"\n>>> Chaine {lang.upper()} : dans Google, choisis le compte ouicab77 puis la chaine "
          f"« ViceClips {lang.upper()} », puis Autoriser.")
    print("    (Ecran 'Google n'a pas valide cette appli' : clique Continuer)")
    webbrowser.open(url)
    th.join(); srv.server_close()
    if not Recepteur.code:
        print("    -> pas d'autorisation, chaine ignoree."); return None
    tok = post("https://oauth2.googleapis.com/token", {"code": Recepteur.code, "client_id": cid,
               "client_secret": csec, "redirect_uri": REDIRECT, "grant_type": "authorization_code"})
    try:
        req = urllib.request.Request("https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
                                     headers={"Authorization": f"Bearer {tok['access_token']}"})
        nom = json.loads(urllib.request.urlopen(req, timeout=30).read())["items"][0]["snippet"]["title"]
        print(f"    -> OK, reliee a la chaine : {nom}")
        if lang.upper() not in nom.upper():
            print(f"    !!! Attention : ce n'est pas ViceClips {lang.upper()}. Relance l'outil si c'est une erreur.")
    except Exception:
        print("    -> OK")
    return tok.get("refresh_token")


def main():
    cid, csec = trouver_client()
    tokens = {}
    for lang in LANGUES:
        r = input(f"\nRelier ViceClips {lang.upper()} ? (Entree = oui, n = passer) ").strip().lower()
        if r == "n":
            continue
        t = autoriser(cid, csec, lang)
        if t:
            tokens[lang] = t
    secret = json.dumps({"client_id": cid, "client_secret": csec, "tokens": tokens})
    with open(os.path.join(ICI, "YOUTUBE_SECRET.txt"), "w", encoding="utf-8") as f:
        f.write(secret)
    try:
        subprocess.run("clip", input=secret, text=True, shell=True)
        copie = True
    except Exception:
        copie = False
    print("\n================================================")
    print(f" {len(tokens)} chaine(s) reliee(s) : {', '.join(t.upper() for t in tokens)}")
    print(" Le code est " + ("COPIE dans le presse-papiers." if copie else "dans YOUTUBE_SECRET.txt"))
    print(" Sur la page GitHub qui s'ouvre :")
    print("   Name   : YOUTUBE_SECRET")
    print("   Secret : Ctrl+V  puis  Add secret")
    print(" Ensuite supprime YOUTUBE_SECRET.txt de ce dossier.")
    print("================================================")
    webbrowser.open("https://github.com/Taxi77777/viceclips/settings/secrets/actions/new")
    input("\nEntree pour fermer...")


if __name__ == "__main__":
    main()
