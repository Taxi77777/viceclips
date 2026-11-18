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


def autoriser(cid, csec):
    params = {"client_id": cid, "redirect_uri": REDIRECT, "response_type": "code", "scope": SCOPE,
              "access_type": "offline", "prompt": "consent select_account"}
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    srv = http.server.HTTPServer(("127.0.0.1", PORT), Recepteur)
    Recepteur.code = None
    th = threading.Thread(target=srv.handle_request); th.start()
    print("    Google s'ouvre : choisis ouicab77 puis UNE chaine ViceClips (n'importe laquelle), puis Continuer.")
    webbrowser.open(url)
    th.join(); srv.server_close()
    if not Recepteur.code:
        print("    -> annule."); return None, None
    tok = post("https://oauth2.googleapis.com/token", {"code": Recepteur.code, "client_id": cid,
               "client_secret": csec, "redirect_uri": REDIRECT, "grant_type": "authorization_code"})
    req = urllib.request.Request("https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
                                 headers={"Authorization": f"Bearer {tok['access_token']}"})
    nom = json.loads(urllib.request.urlopen(req, timeout=30).read())["items"][0]["snippet"]["title"]
    lang = next((l for l in LANGUES if nom.strip().upper().endswith(l.upper())), None)
    return lang, (tok.get("refresh_token"), nom)


def main():
    cid, csec = trouver_client()
    fichier = os.path.join(ICI, "YOUTUBE_SECRET.txt")
    tokens = {}
    if os.path.exists(fichier):
        try:
            tokens = json.load(open(fichier, encoding="utf-8")).get("tokens", {})
        except Exception:
            tokens = {}
    while True:
        manquent = [l.upper() for l in LANGUES if l not in tokens]
        if not manquent:
            break
        print(f"\nDeja reliees : {', '.join(l.upper() for l in tokens) or 'aucune'}  |  Il manque : {', '.join(manquent)}")
        r = input("Entree = relier une chaine   |   f = finir maintenant : ").strip().lower()
        if r == "f":
            break
        lang, res = autoriser(cid, csec)
        if res is None:
            continue
        rt, nom = res
        if not lang:
            print(f"    !!! '{nom}' n'est pas une chaine ViceClips EN/ES/DE/FR/AR. Recommence avec la bonne.")
            continue
        if rt:
            tokens[lang] = rt
            print(f"    -> OK : {nom} reliee (langue {lang.upper()})")
        with open(fichier, "w", encoding="utf-8") as f:
            json.dump({"client_id": cid, "client_secret": csec, "tokens": tokens}, f)
    secret = json.dumps({"client_id": cid, "client_secret": csec, "tokens": tokens})
    with open(fichier, "w", encoding="utf-8") as f:
        f.write(secret)
    subprocess.run("clip", input=secret, text=True, shell=True)
    print("\n================================================")
    print(f" {len(tokens)} chaine(s) reliee(s) : {', '.join(t.upper() for t in tokens)}")
    print(" Le code est COPIE (et aussi dans YOUTUBE_SECRET.txt).")
    print(" Sur la page GitHub qui s'ouvre :")
    print("   Name   : YOUTUBE_SECRET")
    print("   Secret : Ctrl+V  puis  Add secret")
    print("================================================")
    webbrowser.open("https://github.com/Taxi77777/viceclips/settings/secrets/actions/new")
    input("\nEntree pour fermer...")


if __name__ == "__main__":
    main()
