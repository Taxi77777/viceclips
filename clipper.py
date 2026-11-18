"""
ViceClips - bot de clipping GTA 6 automatique (gratuit)
Cherche les nouvelles videos GTA 6, trouve les meilleurs moments, fait des clips
9:16 sous-titres en plusieurs langues, range tout dans PRETS_A_PUBLIER/.

Lancer :  python clipper.py          (un cycle)
          python clipper.py --boucle (24h/24)
"""
import json, os, re, subprocess, sys, time, csv, wave, shutil, datetime, urllib.request, urllib.parse
from pathlib import Path

BASE = Path(__file__).resolve().parent
CFG = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
WORK = BASE / "_travail"
OUT = BASE / "PRETS_A_PUBLIER"
STATE = BASE / "deja_traites.json"
LOG = BASE / "journal_clips.csv"
WORK.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)

# Mots d'excitation par langue (bonus de score quand on les entend)
HYPE = {
    "en": ["oh my god", "what the", "no way", "bro", "let's go", "insane", "holy", "wtf", "are you kidding", "run", "crazy", "dude"],
    "es": ["dios mío", "qué", "no puede ser", "vamos", "increíble", "madre mía", "corre", "loco", "hostia", "wey", "brutal"],
    "de": ["alter", "krass", "was", "digga", "oh mein gott", "nein", "lauf", "geil", "wahnsinn", "junge", "los"],
    "pt": ["meu deus", "caramba", "mano", "não acredito", "corre", "olha isso", "que isso", "nossa", "bizarro"],
    "it": ["oddio", "mamma mia", "raga", "non ci credo", "corri", "assurdo", "frate", "ma che", "pazzesco"],
    "tr": ["aman allahım", "kardeşim", "yok artık", "koş", "inanılmaz", "abi", "vay", "oha", "nasıl ya"],
    "ru": ["боже", "блин", "братан", "не может быть", "беги", "жесть", "капец", "ого", "смотри"],
    "ar": ["يا الله", "والله", "لا لا", "شوف", "مستحيل", "يا رجال", "اركض", "يا ساتر", "ايش", "وش هذا"],
    "fr": ["putain", "wesh", "c'est quoi", "oh mon dieu", "frère", "vas-y", "incroyable", "cours", "non mais", "dingue", "sérieux"],
}
HOOKS = {
    "en": "He did NOT expect this in GTA 6",
    "es": "No esperaba ESTO en GTA 6",
    "de": "DAMIT hat er in GTA 6 nicht gerechnet",
    "fr": "Il s'attendait PAS à ça dans GTA 6",
    "ar": "ما توقع هذا أبداً في GTA 6",
    "pt": "Ele NÃO esperava isso no GTA 6",
    "it": "Non se lo aspettava in GTA 6",
    "tr": "GTA 6'da BUNU beklemiyordu",
    "ru": "Он НЕ ожидал такого в GTA 6",
}
FONT = "Liberation Sans" if os.environ.get("VICECLIPS_CLOUD") else "Arial"
YTDLP = [sys.executable, "-m", "yt_dlp"]


def log(msg):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {msg}", flush=True)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(s):
    STATE.write_text(json.dumps(s, indent=1))


def tg_creds():
    return (os.environ.get("TELEGRAM_BOT_TOKEN") or CFG.get("telegram_bot_token"),
            os.environ.get("TELEGRAM_CHAT_ID") or CFG.get("telegram_chat_id"))


def telegram_video(mp4, caption):
    """Envoie le clip sur Telegram (pour publier depuis le telephone)."""
    tok, chat = tg_creds()
    if not tok or not chat:
        return False
    r = run(["curl", "-s", "-F", f"chat_id={chat}", "-F", f"caption={caption[:1000]}",
             "-F", "supports_streaming=true", "-F", f"video=@{mp4}",
             f"https://api.telegram.org/bot{tok}/sendVideo"])
    ok = '"ok":true' in (r.stdout or "")
    if not ok:
        log("Telegram video: " + (r.stdout or r.stderr)[-200:])
    return ok


def telegram(text):
    tok, chat = tg_creds()
    if not tok or not chat:
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data, timeout=15)
    except Exception as e:
        log(f"Telegram: {e}")


# ---------- 1. Decouverte des videos ----------
def ytdlp_list(target, n):
    r = run(YTDLP + ["--flat-playlist", "--playlist-end", str(n), "-J", target])
    if r.returncode != 0:
        log(f"yt-dlp liste echouee: {target} -> {r.stderr[-200:]}")
        return []
    data = json.loads(r.stdout)
    return data.get("entries") or []


def discover(lang, conf, state):
    n = 15
    entries = []
    for ch in conf.get("channels", []):
        entries += [dict(e, _src=ch) for e in ytdlp_list(ch, 5)]
    if not conf.get("channels") and CFG.get("recherche_si_pas_de_channels"):
        q = urllib.parse.quote_plus(conf["recherche"])
        url = f"https://www.youtube.com/results?search_query={q}&sp=CAI%3D"  # tri : plus recentes
        entries += [dict(e, _src="recherche") for e in ytdlp_list(url, n)]
    out = []
    for e in entries:
        vid = e.get("id")
        if not vid or vid in state:
            continue
        dur = e.get("duration") or 0
        if dur and dur < CFG["duree_video_min_minutes"] * 60:
            continue
        out.append({"id": vid, "url": e.get("url") or f"https://www.youtube.com/watch?v={vid}",
                    "title": e.get("title", ""), "channel": e.get("channel") or e.get("uploader") or "",
                    "src": e["_src"]})
    return out[: CFG["videos_max_par_cycle_et_langue"]]


def video_info(url):
    r = run(YTDLP + ["-J", "--no-playlist", url])
    return json.loads(r.stdout) if r.returncode == 0 else None


# ---------- 2. Analyse audio (pics d'energie) ----------
def download_audio(url, dest):
    h = int(CFG.get("heures_max_analysees", 4) * 3600)
    r = run(YTDLP + ["-f", "ba/b", "--download-sections", f"*0-{h}", "-x", "--audio-format", "wav", "--postprocessor-args",
             "ffmpeg:-ac 1 -ar 16000", "-o", str(dest.with_suffix(".%(ext)s")), url])
    return dest if dest.exists() else None


def energy_peaks(wav_path, n_windows, win):
    import numpy as np
    with wave.open(str(wav_path)) as w:
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    sec = len(a) // sr
    if sec < win * 2:
        return []
    rms = np.sqrt((a[: sec * sr].reshape(sec, sr) ** 2).mean(axis=1) + 1e-9)
    db = 20 * np.log10(rms + 1e-9)
    def smooth(x, k):
        k = min(k, len(x))
        return np.convolve(x, np.ones(k), mode="same") / np.convolve(np.ones(len(x)), np.ones(k), mode="same")
    db[db < np.percentile(db, 5)] = np.percentile(db, 5)  # ignore les silences complets
    base = smooth(db, 120)  # niveau moyen local (2 min)
    excite = np.clip(db - base, 0, None)
    score = smooth(excite, win)
    edge = min(60, sec // 10)
    score[:edge] = 0; score[-edge:] = 0  # evite intro/outro
    picks = []
    order = np.argsort(score)[::-1]
    for c in order:
        if len(picks) >= n_windows:
            break
        if all(abs(c - p) > win * 1.5 for p in picks):
            picks.append(int(c))
    return sorted(picks), sec


# ---------- 3. Transcription ----------
_model = None


def transcribe(wav_path, start, dur, lang):
    global _model
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return []
    if _model is None:
        try:
            _model = WhisperModel(CFG.get("modele_whisper", "small"), device="auto", compute_type="int8")
        except Exception:
            _model = WhisperModel(CFG.get("modele_whisper", "small"), device="cpu", compute_type="int8")
    seg_wav = wav_path.with_name(f"seg_{start}.wav")
    run(["ffmpeg", "-y", "-ss", str(start), "-t", str(dur), "-i", str(wav_path), str(seg_wav)])
    segs, _ = _model.transcribe(str(seg_wav), language=lang, word_timestamps=True, vad_filter=True)
    words = []
    for s in segs:
        for w in (s.words or []):
            words.append({"t0": w.start, "t1": w.end, "w": w.word.strip()})
    seg_wav.unlink(missing_ok=True)
    return words


def hype_bonus(words, lang):
    txt = " ".join(w["w"] for w in words).lower()
    return sum(txt.count(k) for k in HYPE.get(lang, []))


# ---------- 4. Sous-titres ASS ----------
def ass_time(t):
    t = max(0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def make_ass(lines, hook, path):
    """lines = [(t0, t1, texte)]"""
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{FONT},78,&H0000FFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,2,60,60,560,1
Style: Hook,{FONT},70,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,3,18,0,8,60,60,230,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = [f"Dialogue: 1,{ass_time(0)},{ass_time(3.2)},Hook,,0,0,0,,{hook.upper()}"]
    for t0, t1, txt in lines:
        txt = txt.replace("{", "").replace("}", "").replace("\n", " ").strip()
        if txt:
            ev.append(f"Dialogue: 0,{ass_time(t0)},{ass_time(t1)},Sub,,0,0,0,,{{\\fad(60,60)}}{txt.upper()}")
    Path(path).write_text(head + "\n".join(ev) + "\n", encoding="utf-8")


def group_words(words, offset, size=3):
    out = []
    for i in range(0, len(words), size):
        g = words[i:i + size]
        out.append((g[0]["t0"] - offset, g[-1]["t1"] - offset + 0.05, " ".join(w["w"] for w in g)))
    return out


_translators = {}


def translate(text, src, dst):
    if src == dst or not text.strip():
        return text
    try:
        import argostranslate.translate as at
        return at.translate(text, src, dst)
    except Exception:
        return None


def translated_lines(words, offset, src, dst):
    """Traduit par phrase (blocs de ~8 mots) et garde le timing du bloc."""
    out = []
    for i in range(0, len(words), 8):
        g = words[i:i + 8]
        tr = translate(" ".join(w["w"] for w in g), src, dst)
        if tr is None:
            return None
        out.append((g[0]["t0"] - offset, g[-1]["t1"] - offset + 0.05, tr))
    return out


# ---------- 5. Rendu 9:16 ----------
def download_section(url, start, end, dest):
    run(YTDLP + ["-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]/b",
         "--download-sections", f"*{start}-{end}", "--force-keyframes-at-cuts",
         "--merge-output-format", "mp4", "-o", str(dest), url])
    return dest.exists()


def render(src, ass, dest):
    vf = ("split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
          "boxblur=25:2,eq=brightness=-0.12[bg];[b]scale=1080:-2[fg];"
          "[bg][fg]overlay=(W-w)/2:(H-h)/2-80,ass=" + ass.name)
    r = run(["ffmpeg", "-y", "-i", src.name, "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "21", "-c:a", "aac", "-b:a", "160k", "-r", "30", "-movflags", "+faststart",
             str(dest.resolve())], cwd=str(src.parent))
    if r.returncode != 0:
        log("ffmpeg: " + r.stderr[-300:])
    return dest.exists()


def write_caption(dest_txt, lang, video, hook):
    ch = video.get("channel") or "streamer"
    tags = CFG["langues"].get(lang, {}).get("hashtags", "#GTA6")
    credit = {"en": "Credit", "es": "Crédito", "de": "Credit", "fr": "Crédit", "ar": "المصدر", "pt": "Créditos", "it": "Credit", "tr": "Kaynak", "ru": "Автор"}.get(lang, "Credit")
    dest_txt.write_text(f"{hook} 😱\n\n🎥 {credit}: {ch}\n\n{tags}\n\nSource: {video['url']}\n", encoding="utf-8")


def log_csv(row):
    new = not LOG.exists()
    with LOG.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        if new:
            w.writerow(["date", "langue", "fichier", "chaine", "source", "debut_s", "publie_le", "lien_publication", "campagne"])
        w.writerow(row)


# ---------- 6. Traitement d'une video ----------
def process(video, lang):
    vid = video["id"]
    d = WORK / vid; d.mkdir(exist_ok=True)
    log(f"[{lang}] {video['title'][:70]} ({video['channel']})")
    wav = download_audio(video["url"], d / "audio.wav")
    if not wav:
        log("  audio introuvable, on passe"); return 0
    win = CFG["duree_clip_secondes"]
    res = energy_peaks(wav, CFG["clips_par_video"] * 2, win)
    if not res:
        return 0
    picks, total = res
    cands = []
    for c in picks:
        start = max(0, c - win // 2); dur = win
        words = transcribe(wav, start, dur, lang)
        score = hype_bonus(words, lang) * 3 + len(words) / 20
        cands.append((score, start, dur, words))
    cands.sort(key=lambda x: -x[0])
    made = 0
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    for i, (score, start, dur, words) in enumerate(cands[: CFG["clips_par_video"]], 1):
        raw = d / f"raw_{i}.mp4"
        if not download_section(video["url"], start, start + dur, raw):
            log(f"  clip {i}: telechargement rate"); continue
        for tgt in [lang] + [t for t in CFG["traduire_vers"] if t != lang]:
            if tgt == lang:
                lines = group_words(words, start)
            else:
                if not words:
                    continue
                lines = translated_lines(words, start, lang, tgt)
                if lines is None:
                    continue
            hook = HOOKS.get(tgt, HOOKS["en"])
            ass = d / f"sub_{i}_{tgt}.ass"
            make_ass(lines, hook, ass)
            od = OUT / tgt.upper(); od.mkdir(exist_ok=True)
            name = f"{stamp}_{re.sub(r'[^A-Za-z0-9]+', '', video['channel'])[:20]}_{vid}_{i}"
            mp4 = od / f"{name}.mp4"
            if render(raw, ass, mp4):
                write_caption(od / f"{name}.txt", tgt, video, hook)
                telegram_video(mp4, f"[{tgt.upper()}] " + (od / f"{name}.txt").read_text(encoding="utf-8"))
                log_csv([datetime.datetime.now().isoformat(timespec="minutes"), tgt, mp4.name,
                         video["channel"], video["url"], start, "", "", ""])
                made += 1
                log(f"  OK {tgt.upper()} -> {mp4.name}")
    shutil.rmtree(d, ignore_errors=True)
    return made


def cycle():
    state = load_state()
    total = 0
    for lang, conf in CFG["langues"].items():
        if not conf.get("actif", True):
            continue
        for v in discover(lang, conf, state):
            try:
                total += process(v, lang)
            except Exception as e:
                log(f"  erreur: {e}")
            state[v["id"]] = datetime.datetime.now().isoformat()
            save_state(state)
    log(f"Cycle termine : {total} clips prets dans {OUT}")
    if total:
        telegram(f"ViceClips : {total} nouveaux clips GTA 6 prets a publier.")
    return total


if __name__ == "__main__":
    if "--boucle" in sys.argv:
        while True:
            try:
                cycle()
            except Exception as e:
                log(f"Erreur cycle: {e}")
            log(f"Pause {CFG['intervalle_minutes']} min...")
            time.sleep(CFG["intervalle_minutes"] * 60)
    else:
        cycle()
