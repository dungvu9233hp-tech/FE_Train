#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FE 日本語 IT 用語 - Ứng dụng học & thi thử từ vựng (Tkinter, không cần thư viện ngoài)

Chạy:  python fe_vocab_trainer.py
Cần:   Python 3.8+ (có tkinter) và file tuvung.txt đặt cùng thư mục.

Cấu trúc đề thi thử (đúng theo đề thi thật, tối đa 30 điểm):
  Phần 1: Nhìn tiếng Nhật -> viết cách đọc (1đ) + nghĩa tiếng Việt (2đ)   5 câu x 3đ = 15đ
  Phần 2: Nhìn tiếng Anh/alphabet -> viết cách đọc bằng Katakana          5 câu x 1đ =  5đ
  Phần 3: Nghe tiếng Nhật -> chọn nghĩa tiếng Việt                        5 câu x 1đ =  5đ
  Phần 4: Nhìn tiếng Việt -> chọn tiếng Nhật tương ứng                    5 câu x 1đ =  5đ
"""
import os
import re
import sys
import json
import random
import difflib
import platform
import tempfile
import threading
import subprocess
import unicodedata
import hashlib
import time
import urllib.parse
import urllib.request
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font as tkfont

# Thư mục cài đặt (nơi có .exe / .py) và thư mục dữ liệu người dùng
FROZEN = getattr(sys, "frozen", False)
APP_DIR = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)  # nơi PyInstaller giải nén tuvung.txt, icon.ico
if FROZEN and platform.system() == "Windows":
    # Như ứng dụng thường: tiến độ + giọng đọc lưu ở %APPDATA%, không ghi vào Program Files
    DATA_DIR = os.path.join(os.environ.get("APPDATA", APP_DIR), "FE_Vocab_Trainer")
else:
    DATA_DIR = APP_DIR
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except OSError:
    DATA_DIR = APP_DIR
PROGRESS_FILE = os.path.join(DATA_DIR, "progress.json")
AUDIO_DIR = os.path.join(DATA_DIR, "audio")  # mp3 giọng đọc đã tải, dùng offline


def find_vocab_file():
    for d in (DATA_DIR, APP_DIR, BUNDLE_DIR):
        p = os.path.join(d, "tuvung.txt")
        if os.path.exists(p):
            return p
    return os.path.join(APP_DIR, "tuvung.txt")


VOCAB_FILE = find_vocab_file()

PART_TITLES = {
    1: "Nhìn tiếng Nhật → viết cách đọc (1đ) và nghĩa tiếng Việt (2đ)",
    2: "Nhìn tiếng Anh / alphabet → viết cách đọc bằng Katakana (1đ)",
    3: "Nghe tiếng Nhật → chọn nghĩa tiếng Việt (1đ)",
    4: "Nhìn tiếng Việt → chọn tiếng Nhật tương ứng (1đ)",
}
PART_SHORT = {1: "Đọc + nghĩa", 2: "Katakana", 3: "Nghe → nghĩa", 4: "Việt → Nhật"}
Q_PER_PART = 5

# ======================================================================
#  LOGIC (không phụ thuộc giao diện)
# ======================================================================

def load_vocab(path):
    """Đọc tuvung.txt. Mỗi lần số thứ tự quay về 1 = bắt đầu một bài mới."""
    words, lesson = [], 0
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            parts = line.rstrip("\r\n").split("\t")
            if len(parts) < 4:
                continue
            no, jp, rd, mean = [p.strip() for p in parts[:4]]
            if not no.isdigit() or not jp:
                continue
            if int(no) == 1 or lesson == 0:
                lesson += 1
            if "," in mean:
                vi, en = [s.strip() for s in mean.split(",", 1)]
            else:
                vi, en = mean, ""
            words.append({"id": f"{lesson}-{no}", "lesson": lesson, "no": int(no),
                          "jp": jp, "reading": rd, "vi": vi, "en": en})
    return words


def is_alpha_word(jp):
    """Từ viết bằng chữ cái La-tinh/số (LAN, TCP/IP, IPv4, S/MIME...)."""
    return re.fullmatch(r"[A-Za-z0-9/\-\s]+", jp) is not None


def has_kanji(s):
    return any("\u4e00" <= c <= "\u9fff" for c in s)


def reading_variants(word):
    return [r for r in re.split(r"[／/]", word["reading"]) if r.strip()]


def tts_text(word):
    return reading_variants(word)[0].strip()


def kata2hira(s):
    return "".join(chr(ord(c) - 0x60) if "\u30a1" <= c <= "\u30f6" else c for c in s)


# ---------------------------------------------------------------- gõ romaji -> kana (không cần bộ gõ Nhật)
def _build_romaji():
    R = {}
    rows = {"": "あいうえお", "k": "かきくけこ", "g": "がぎぐげご", "s": "さしすせそ", "z": "ざじずぜぞ",
            "t": "たちつてと", "d": "だぢづでど", "n": "なにぬねの", "h": "はひふへほ", "b": "ばびぶべぼ",
            "p": "ぱぴぷぺぽ", "m": "まみむめも", "r": "らりるれろ"}
    for c, chars in rows.items():
        for v, ch in zip("aiueo", chars):
            R[c + v] = ch
    R.update({"ya": "や", "yu": "ゆ", "yo": "よ", "ye": "いぇ", "wa": "わ", "wo": "を", "wi": "うぃ",
              "we": "うぇ", "wu": "う", "shi": "し", "ji": "じ", "chi": "ち", "tsu": "つ", "fu": "ふ",
              "va": "ゔぁ", "vi": "ゔぃ", "vu": "ゔ", "ve": "ゔぇ", "vo": "ゔぉ",
              "fa": "ふぁ", "fi": "ふぃ", "fe": "ふぇ", "fo": "ふぉ",
              "tsa": "つぁ", "tsi": "つぃ", "tse": "つぇ", "tso": "つぉ",
              "thi": "てぃ", "thu": "てゅ", "dhi": "でぃ", "dhu": "でゅ", "twu": "とぅ", "dwu": "どぅ",
              "kwa": "くぁ", "gwa": "ぐぁ"})
    combos = {"ky": "き", "gy": "ぎ", "sh": "し", "sy": "し", "j": "じ", "jy": "じ", "zy": "じ", "ch": "ち",
              "cy": "ち", "ty": "ち", "dy": "ぢ", "ny": "に", "hy": "ひ", "by": "び", "py": "ぴ",
              "my": "み", "ry": "り"}
    for c, base in combos.items():
        for v, sm in zip("auo", "ゃゅょ"):
            R[c + v] = base + sm
    R.update({"she": "しぇ", "che": "ちぇ", "je": "じぇ"})
    for pre in ("x", "l"):
        for v, ch in zip("aiueo", "ぁぃぅぇぉ"):
            R[pre + v] = ch
        for v, ch in zip("yau", "ゃゅょ") if False else zip(("ya", "yu", "yo"), "ゃゅょ"):
            R[pre + v] = ch
        R[pre + "tu"] = R[pre + "tsu"] = "っ"
        R[pre + "wa"] = "ゎ"
    return R


_ROMAJI = _build_romaji()
_ROMAJI_MAX = max(len(k) for k in _ROMAJI)
_ROMAJI_PREFIX = {k[:i] for k in _ROMAJI for i in range(1, len(k))}
_DOUBLE = set("kgsztdhbpmrwfjvc")
_VOW = set("aiueo")


def hira2kata(s):
    return "".join(chr(ord(c) + 0x60) if "\u3041" <= c <= "\u3096" else c for c in s)


def romaji_to_kana(text, katakana=False, final=False):
    """Đổi romaji -> hiragana/katakana. final=False: phần romaji chưa gõ xong ở cuối được giữ nguyên."""
    s, n, i, out = text, len(text), 0, []
    while i < n:
        c = s[i]
        lc = c.lower()
        if c == "-":
            out.append("ー")
            i += 1
            continue
        if not (lc.isascii() and lc.isalpha()):
            out.append(c)
            i += 1
            continue
        hit = None
        for L in range(min(_ROMAJI_MAX, n - i), 0, -1):
            if s[i:i + L].lower() in _ROMAJI:
                hit = L
                break
        if hit:
            out.append(_ROMAJI[s[i:i + hit].lower()])
            i += hit
            continue
        nxt = s[i + 1].lower() if i + 1 < n else ""
        if lc == "n":
            if i + 1 >= n:
                if final:
                    out.append("ん")
                    i += 1
                    continue
                out.append(c)
                break
            if nxt == "n":
                after = s[i + 2].lower() if i + 2 < n else ""
                if after in _VOW or after == "y":
                    out.append("ん")
                    i += 1
                elif after == "":
                    if final:
                        out.append("ん")
                        i += 2
                    else:
                        out.append(s[i:])
                        break
                else:
                    out.append("ん")
                    i += 2
                continue
            if nxt == "'":
                out.append("ん")
                i += 2
                continue
            if nxt not in _VOW and nxt != "y":
                out.append("ん")
                i += 1
                continue
        if nxt == lc and lc in _DOUBLE:
            out.append("っ")
            i += 1
            continue
        if lc == "t" and nxt == "c" and s[i + 2:i + 3].lower() == "h":
            out.append("っ")
            i += 1
            continue
        if s[i:].lower() in _ROMAJI_PREFIX:  # chưa gõ xong (vd "sh", "ky", "ts")
            out.append(s[i:])
            break
        out.append(c)
        i += 1
    res = "".join(out)
    return hira2kata(res) if katakana else res



def norm_reading(s, fold_kana=True):
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[\s・･.,，、]", "", s).lower()
    return kata2hira(s) if fold_kana else s


def reading_ok(user, word, strict_katakana=False):
    u = norm_reading(user, fold_kana=not strict_katakana)
    if not u:
        return False
    return any(u == norm_reading(r, fold_kana=not strict_katakana)
               for r in reading_variants(word))


def strip_accents(s):
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s.lower())


def meaning_ok(user, word):
    """Chấp nhận gõ không dấu và sai chính tả nhẹ (độ giống >= 88%)."""
    u, c = strip_accents(user), strip_accents(word["vi"])
    if not u or not c:
        return False
    return u == c or difflib.SequenceMatcher(None, u, c).ratio() >= 0.88


def make_exam(selected, all_words, parts=(1, 2, 3, 4), n=Q_PER_PART, rng=random):
    """Sinh đề thi từ các từ đã chọn."""
    def uniq(ws):
        seen, out = set(), []
        for w in ws:
            if w["jp"] not in seen:
                seen.add(w["jp"])
                out.append(w)
        return out

    sel, pool_all = uniq(selected), uniq(all_words)
    used = set()

    def pick(pool, k, fill=True):
        cand = [w for w in pool if w["jp"] not in used]
        rng.shuffle(cand)
        chosen = cand[:k]
        if fill and len(chosen) < k:
            rest = [w for w in sel if w["jp"] not in used and w not in chosen]
            rng.shuffle(rest)
            chosen += rest[:k - len(chosen)]
        for w in chosen:
            used.add(w["jp"])
        return chosen

    non_alpha = [w for w in sel if not is_alpha_word(w["jp"])]
    kanji = [w for w in non_alpha if has_kanji(w["jp"])]
    alpha = [w for w in sel if is_alpha_word(w["jp"])]

    qs = []
    for p in parts:
        if p == 1:
            ws = pick(kanji if len(kanji) >= n else non_alpha, n)
            qs += [{"part": 1, "word": w, "ans": {}} for w in ws]
        elif p == 2:
            ws = pick(alpha, n, fill=False)
            qs += [{"part": 2, "word": w, "ans": {}} for w in ws]
        elif p == 3:
            for w in pick(sel, n):
                vi_pool = [x["vi"] for x in uniq(sel) if x["vi"] != w["vi"]]
                vi_pool = list(dict.fromkeys(vi_pool))
                if len(vi_pool) < 3:
                    vi_pool = list(dict.fromkeys(x["vi"] for x in pool_all if x["vi"] != w["vi"]))
                opts = rng.sample(vi_pool, 3) + [w["vi"]]
                rng.shuffle(opts)
                qs.append({"part": 3, "word": w, "ans": {}, "options": opts,
                           "correct": opts.index(w["vi"])})
        elif p == 4:
            for w in pick(sel, n):
                same_type = [x["jp"] for x in pool_all
                             if x["jp"] != w["jp"] and is_alpha_word(x["jp"]) == is_alpha_word(w["jp"])
                             and x["vi"] != w["vi"]]
                if len(same_type) < 3:
                    same_type = [x["jp"] for x in pool_all if x["jp"] != w["jp"] and x["vi"] != w["vi"]]
                opts = rng.sample(list(dict.fromkeys(same_type)), 3) + [w["jp"]]
                rng.shuffle(opts)
                qs.append({"part": 4, "word": w, "ans": {}, "options": opts,
                           "correct": opts.index(w["jp"])})
    return qs


FLAG_DEFS = {
    1: [("r", "Cách đọc", 1), ("m", "Nghĩa", 2)],
    2: [("k", "Katakana", 1)],
    3: [("c", "Chọn đúng", 1)],
    4: [("c", "Chọn đúng", 1)],
}


def grade(q):
    w, a, p = q["word"], q["ans"], q["part"]
    if p == 1:
        q["flags"] = {"r": reading_ok(a.get("r", ""), w), "m": meaning_ok(a.get("m", ""), w)}
    elif p == 2:
        q["flags"] = {"k": reading_ok(a.get("k", ""), w, strict_katakana=True)}
    else:
        q["flags"] = {"c": a.get("choice", -1) == q["correct"]}


def points(q):
    return sum(pt for key, _, pt in FLAG_DEFS[q["part"]] if q["flags"].get(key))


def max_points(q):
    return sum(pt for _, _, pt in FLAG_DEFS[q["part"]])


# ---------------------------------------------------------------- tiến độ
def load_progress():
    try:
        with open(PROGRESS_FILE, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    d.setdefault("review", [])
    d.setdefault("history", [])
    return d


def save_progress(d):
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


# ---------------------------------------------------------------- giọng đọc (TTS offline)
TTS = {"ok": None}  # None = đang kiểm tra


def _run(cmd, **kw):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kw)


def _win_flags():
    return 0x08000000 if platform.system() == "Windows" else 0  # CREATE_NO_WINDOW


def has_local_voice():
    sysname = platform.system()
    try:
        if sysname == "Windows":
            ps = ("Add-Type -AssemblyName System.Speech;"
                  "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                  "($s.GetInstalledVoices()|Where-Object{$_.Enabled -and "
                  "$_.VoiceInfo.Culture.Name -like 'ja*'}|Measure-Object).Count")
            r = _run(["powershell", "-NoProfile", "-Command", ps], creationflags=_win_flags())
            return r.stdout.decode(errors="ignore").strip() not in ("", "0")
        if sysname == "Darwin":
            r = _run(["say", "-v", "?"])
            return "ja_JP" in r.stdout.decode(errors="ignore")
        for exe in ("espeak-ng", "espeak", "spd-say"):
            if _which(exe):
                return True
    except Exception:
        pass
    return False


def _which(exe):
    from shutil import which
    return which(exe)


def speak_local(text):
    sysname = platform.system()
    try:
        if sysname == "Windows":
            safe = text.replace("'", "''")
            script = ("Add-Type -AssemblyName System.Speech\r\n"
                      "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer\r\n"
                      "$v=$s.GetInstalledVoices()|Where-Object{$_.Enabled -and $_.VoiceInfo.Culture.Name -like 'ja*'}|Select-Object -First 1\r\n"
                      f"if($v){{$s.SelectVoice($v.VoiceInfo.Name);$s.Rate=-1;$s.Speak('{safe}');exit 0}}else{{exit 3}}\r\n")
            with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8-sig") as f:
                f.write(script)
                path = f.name
            try:
                r = _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path],
                         creationflags=_win_flags())
                return r.returncode == 0
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass
        if sysname == "Darwin":
            return _run(["say", "-v", "Kyoko", text]).returncode == 0
        for cmd in (["espeak-ng", "-v", "ja", text], ["espeak", "-v", "ja", text],
                    ["spd-say", "-l", "ja", "-w", text]):
            if _which(cmd[0]):
                return _run(cmd).returncode == 0
    except Exception:
        pass
    return False


# ---- Giọng đọc online (Google TTS) – dùng khi máy không có giọng Nhật
def audio_path(text):
    return os.path.join(AUDIO_DIR, hashlib.md5(text.encode("utf-8")).hexdigest() + ".mp3")


def is_cached(text):
    p = audio_path(text)
    return os.path.exists(p) and os.path.getsize(p) > 500


def fetch_online_mp3(text):
    os.makedirs(AUDIO_DIR, exist_ok=True)
    path = audio_path(text)
    if is_cached(text):
        return path
    url = ("https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=ja&q="
           + urllib.parse.quote(text))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        data = r.read()
    if len(data) < 500:
        raise ValueError("empty audio")
    with open(path, "wb") as f:
        f.write(data)
    return path


def play_mp3(path):
    sysname = platform.system()
    if sysname == "Windows":
        import ctypes
        mci = ctypes.windll.winmm.mciSendStringW
        alias = "fetts%d" % os.getpid()
        mci("close " + alias, None, 0, 0)
        if mci('open "%s" type mpegvideo alias %s' % (path, alias), None, 0, 0) != 0:
            return False
        try:
            return mci("play " + alias + " wait", None, 0, 0) == 0
        finally:
            mci("close " + alias, None, 0, 0)
    if sysname == "Darwin":
        return _run(["afplay", path]).returncode == 0
    for cmd in (["mpg123", "-q", path], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                ["mpv", "--no-video", "--really-quiet", path]):
        if _which(cmd[0]):
            return _run(cmd).returncode == 0
    return False


def speak_online(text):
    try:
        return play_mp3(fetch_online_mp3(text))
    except Exception as e:
        print("TTS online lỗi:", e, file=sys.stderr)
        return False


def online_available():
    try:
        fetch_online_mp3("ネット")
        return True
    except Exception:
        return False


def has_ja_voice():
    return has_local_voice() or online_available()


def speak_blocking(text):
    if is_cached(text):  # đã tải sẵn -> phát offline ngay
        try:
            if play_mp3(audio_path(text)):
                return True
        except Exception:
            pass
    return speak_local(text) or speak_online(text)


_speak_lock = threading.Lock()


def speak_async(text):
    def run():
        with _speak_lock:
            speak_blocking(text)
    threading.Thread(target=run, daemon=True).start()


# ======================================================================
#  GIAO DIỆN
# ======================================================================
BG = "#f4f6fb"
INK = "#1e293b"
MUTED = "#64748b"
LINE = "#cbd5e1"
ACCENT = "#2563eb"
GOOD = "#15803d"
BAD = "#b91c1c"


def pick_jp_font(root):
    fams = set(tkfont.families(root))
    for f in ("Meiryo UI", "Meiryo", "MS UI Gothic", "Yu Gothic UI", "Hiragino Sans", "Hiragino Kaku Gothic ProN",
              "Noto Sans CJK JP", "Noto Sans JP", "TakaoPGothic", "IPAexGothic", "MS Gothic"):
        if f in fams:
            return f
    return "TkDefaultFont"


def pick_ui_font(root):
    fams = set(tkfont.families(root))
    for f in ("Segoe UI", "Helvetica Neue", "Arial", "DejaVu Sans"):
        if f in fams:
            return f
    return "TkDefaultFont"


class ScrollFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg=BG)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.win, width=e.width))
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.bind_all("<MouseWheel>", self._wheel)
        self.bind_all("<Button-4>", lambda e: self._scroll(-3))
        self.bind_all("<Button-5>", lambda e: self._scroll(3))

    def _scroll(self, n):
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(n, "units")

    def _wheel(self, e):
        step = -1 * (e.delta // 120) if abs(e.delta) >= 120 else -1 * e.delta
        self._scroll(step * 3 if abs(e.delta) >= 120 else step)


class App(tk.Tk):
    def __init__(self, words):
        super().__init__()
        self.title("FE 日本語 IT 用語 – Luyện từ vựng")
        self.geometry("1100x740")
        self.minsize(900, 620)
        self.configure(bg=BG)
        try:
            self.iconbitmap(os.path.join(BUNDLE_DIR, "icon.ico"))
        except Exception:
            pass
        self.JP = pick_jp_font(self)
        self.UI = pick_ui_font(self)

        self.words = words
        self.lessons = sorted({w["lesson"] for w in words})
        self.progress = load_progress()
        self.tab = "flash"
        self.exam = None
        self.exam_running = False
        self.v = {}

        self._style()
        self.lesson_vars = {l: tk.BooleanVar(value=True) for l in self.lessons}
        self.fc_dir = tk.StringVar(value="Nhật → Việt")
        self.fc_shuffle = tk.BooleanVar(value=False)
        self.fc_review = tk.BooleanVar(value=False)
        self.fc_deck, self.fc_idx, self.fc_flipped = [], 0, False
        self.exam_mode = tk.IntVar(value=0)

        self._build_layout()
        self.bind("<space>", self._on_space)
        self.bind("<Left>", lambda e: self._arrow(-1))
        self.bind("<Right>", lambda e: self._arrow(1))
        threading.Thread(target=lambda: TTS.update(ok=has_ja_voice()), daemon=True).start()
        self.show_flash()

    # ------------------------------------------------------------ style
    def _style(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure(".", background=BG, foreground=INK, font=(self.UI, 11))
        st.configure("TButton", padding=(12, 7), font=(self.UI, 11))
        st.configure("Accent.TButton", background=ACCENT, foreground="white", padding=(16, 9),
                     font=(self.UI, 12, "bold"))
        st.map("Accent.TButton", background=[("active", "#1d4ed8")])
        st.configure("Nav.TRadiobutton", padding=(16, 8), font=(self.UI, 12, "bold"))
        st.configure("Treeview", rowheight=30, font=(self.JP, 11))
        st.configure("Treeview.Heading", font=(self.UI, 11, "bold"))
        st.configure("Side.TLabelframe", background=BG)
        st.configure("Side.TLabelframe.Label", background=BG, font=(self.UI, 11, "bold"))

    # ------------------------------------------------------------ layout
    def _build_layout(self):
        head = tk.Frame(self, bg=ACCENT)
        head.pack(fill="x")
        tk.Label(head, text="FE 日本語 IT 用語", bg=ACCENT, fg="white",
                 font=(self.JP, 17, "bold")).pack(side="left", padx=16, pady=10)
        self.nav = tk.StringVar(value="flash")
        navf = tk.Frame(head, bg=ACCENT)
        navf.pack(side="right", padx=10)
        for text, val in (("📖 Học thẻ", "flash"), ("📋 Danh sách", "list"), ("📝 Thi thử", "exam")):
            tk.Radiobutton(navf, text=text, value=val, variable=self.nav, indicatoron=0,
                           command=self._switch, bg=ACCENT, fg="white", selectcolor="#1e40af",
                           activebackground="#1d4ed8", activeforeground="white", bd=0, relief="flat",
                           font=(self.UI, 12, "bold"), padx=16, pady=8).pack(side="left", padx=2)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=12, pady=10)

        side = ttk.Labelframe(body, text=" Phạm vi từ vựng ", style="Side.TLabelframe", padding=10)
        side.pack(side="left", fill="y", padx=(0, 12))
        for l in self.lessons:
            n = sum(1 for w in self.words if w["lesson"] == l)
            ttk.Checkbutton(side, text=f"Bài {l}  ({n} từ)", variable=self.lesson_vars[l],
                            command=self._scope_changed).pack(anchor="w", pady=2)
        bf = ttk.Frame(side)
        bf.pack(fill="x", pady=(10, 4))
        ttk.Button(bf, text="Tất cả", command=lambda: self._set_all(True)).pack(side="left", expand=True, fill="x")
        ttk.Button(bf, text="Bỏ hết", command=lambda: self._set_all(False)).pack(side="left", expand=True, fill="x", padx=(4, 0))
        self.scope_lbl = ttk.Label(side, foreground=MUTED)
        self.scope_lbl.pack(anchor="w", pady=(8, 0))
        self.review_lbl = ttk.Label(side, foreground=MUTED)
        self.review_lbl.pack(anchor="w")
        self.audio_lbl = ttk.Label(side, foreground=MUTED)
        self.audio_lbl.pack(anchor="w", pady=(8, 2))
        ttk.Button(side, text="⬇ Tải sẵn giọng đọc", command=self.download_audio).pack(fill="x")

        self.content = ttk.Frame(body)
        self.content.pack(side="left", fill="both", expand=True)
        self._update_scope_label()

    def clear(self):
        for c in self.content.winfo_children():
            c.destroy()

    def selected(self):
        return [w for w in self.words if self.lesson_vars[w["lesson"]].get()]

    def _update_scope_label(self):
        self.scope_lbl.config(text=f"Đã chọn: {len(self.selected())} từ")
        self.review_lbl.config(text=f"Cần ôn ⭐: {len(self.progress['review'])} từ")
        texts = {tts_text(w) for w in self.words}
        self.audio_lbl.config(text=f"Giọng đã tải: {sum(1 for t in texts if is_cached(t))}/{len(texts)}")

    def _set_all(self, val):
        for v in self.lesson_vars.values():
            v.set(val)
        self._scope_changed()

    def _scope_changed(self):
        self._update_scope_label()
        if self.exam_running:
            return
        self._refresh_tab()

    def _switch(self):
        if self.exam_running and self.nav.get() == "exam":
            return
        if self.exam_running and self.nav.get() != "exam":
            if not messagebox.askyesno("Đang làm bài", "Bài thi chưa nộp sẽ bị hủy. Rời khỏi?"):
                self.nav.set("exam")
                return
            self.exam_running = False
            self.exam, self.v = None, {}
        self._refresh_tab()

    def _refresh_tab(self):
        t = self.nav.get()
        {"flash": self.show_flash, "list": self.show_list, "exam": self.show_exam_setup}[t]()

    def _on_space(self, e):
        if self.tab == "flash" and not isinstance(self.focus_get(), (tk.Entry, ttk.Entry, ttk.Combobox)):
            self.fc_flip()
            return "break"

    def _arrow(self, d):
        if self.tab == "flash" and not isinstance(self.focus_get(), (tk.Entry, ttk.Entry, ttk.Combobox)):
            self.fc_move(d)

    def download_audio(self):
        texts = sorted({tts_text(w) for w in self.words})
        todo = [t for t in texts if not is_cached(t)]
        if not todo:
            messagebox.showinfo("Tải sẵn giọng đọc", "Đã tải đủ toàn bộ giọng đọc, có thể dùng offline.")
            return
        if not messagebox.askyesno("Tải sẵn giọng đọc",
                                   f"Cần tải {len(todo)} file âm thanh (cần có mạng, vài phút).\n"
                                   f"Lưu vào thư mục:\n{AUDIO_DIR}\n\nBắt đầu?"):
            return
        st = {"done": 0, "fail": 0, "total": len(todo), "cancel": False, "end": False, "abort": False}

        def worker():
            consecutive = 0
            for t in todo:
                if st["cancel"]:
                    break
                ok = False
                for attempt in range(2):
                    try:
                        fetch_online_mp3(t)
                        ok = True
                        break
                    except Exception:
                        time.sleep(1.0)
                if ok:
                    st["done"] += 1
                    consecutive = 0
                else:
                    st["fail"] += 1
                    consecutive += 1
                    if consecutive >= 5:
                        st["abort"] = True
                        break
                time.sleep(0.25)
            st["end"] = True

        win = tk.Toplevel(self)
        win.title("Tải sẵn giọng đọc")
        win.geometry("420x160")
        win.transient(self)
        win.resizable(False, False)
        lbl = ttk.Label(win, text="Đang tải...")
        lbl.pack(pady=(18, 6))
        pb = ttk.Progressbar(win, maximum=st["total"], length=360)
        pb.pack(pady=6)
        btn = ttk.Button(win, text="Dừng", command=lambda: st.update(cancel=True))
        btn.pack(pady=10)
        threading.Thread(target=worker, daemon=True).start()

        def poll():
            pb["value"] = st["done"] + st["fail"]
            lbl.config(text=f"Đã tải {st['done']}/{st['total']}" + (f"  ·  lỗi {st['fail']}" if st["fail"] else ""))
            if st["end"]:
                self._update_scope_label()
                if st["abort"]:
                    lbl.config(text="Dừng vì lỗi liên tiếp – kiểm tra mạng rồi thử lại.")
                elif st["cancel"]:
                    lbl.config(text=f"Đã dừng ({st['done']}/{st['total']}). Bấm tải lại để tiếp tục.")
                else:
                    lbl.config(text=f"Xong! Tải {st['done']}/{st['total']}" + (f", lỗi {st['fail']}" if st["fail"] else "") + ".")
                btn.config(text="Đóng", command=win.destroy)
                return
            win.after(200, poll)
        poll()

    def attach_romaji(self, entry, var, katakana):
        skip = {"Return", "Tab", "Left", "Right", "Home", "End", "Up", "Down", "Escape",
                "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"}

        def on_key(ev):
            if ev.keysym in skip:
                return
            txt = var.get()
            if entry.index("insert") != len(txt):
                return
            new = romaji_to_kana(txt, katakana, False)
            if new != txt:
                var.set(new)
                entry.icursor("end")

        def on_out(ev):
            txt = var.get()
            new = romaji_to_kana(txt, katakana, True)
            if new != txt:
                var.set(new)
        entry.bind("<KeyRelease>", on_key)
        entry.bind("<FocusOut>", on_out)

    def say(self, word):
        speak_async(tts_text(word))

    # ============================================================ HỌC THẺ
    def show_flash(self):
        self.tab = "flash"
        self.clear()
        f = self.content
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Chế độ:").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.fc_dir, values=["Nhật → Việt", "Việt → Nhật"],
                          state="readonly", width=13)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self.fc_render())
        ttk.Checkbutton(bar, text="Xáo trộn", variable=self.fc_shuffle, command=self.fc_build).pack(side="left", padx=8)
        ttk.Checkbutton(bar, text="Chỉ từ cần ôn ⭐", variable=self.fc_review, command=self.fc_build).pack(side="left", padx=8)
        self.fc_counter = ttk.Label(bar, foreground=MUTED)
        self.fc_counter.pack(side="right")

        card = tk.Frame(f, bg="white", highlightbackground=LINE, highlightthickness=2, cursor="hand2")
        card.pack(fill="both", expand=True, pady=6)
        inner = tk.Frame(card, bg="white")
        inner.place(relx=0.5, rely=0.5, anchor="center")
        mk = lambda font, fg: tk.Label(inner, bg="white", fg=fg, font=font, wraplength=640, justify="center")
        self.l_jp = mk((self.JP, 46, "bold"), INK)
        self.l_rd = mk((self.JP, 26), ACCENT)
        self.l_vi = mk((self.UI, 28, "bold"), INK)
        self.l_en = mk((self.UI, 18), MUTED)
        self.l_hint = mk((self.UI, 11), "#94a3b8")
        for l in (self.l_jp, self.l_rd, self.l_vi, self.l_en):
            l.pack(pady=6)
        self.l_hint.pack(pady=(24, 0))
        for w in (card, inner, self.l_jp, self.l_rd, self.l_vi, self.l_en, self.l_hint):
            w.bind("<Button-1>", lambda e: self.fc_flip())

        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=(6, 0))
        ttk.Button(btns, text="◀ Trước", command=lambda: self.fc_move(-1)).pack(side="left")
        ttk.Button(btns, text="🔊 Nghe", command=self.fc_say).pack(side="left", padx=6)
        ttk.Button(btns, text="Lật thẻ (Space)", command=self.fc_flip).pack(side="left", padx=6)
        self.star_btn = ttk.Button(btns, command=self.fc_star)
        self.star_btn.pack(side="left", padx=6)
        ttk.Button(btns, text="Sau ▶", command=lambda: self.fc_move(1)).pack(side="right")
        self.fc_build()

    def fc_build(self):
        ws = self.selected()
        if self.fc_review.get():
            rv = set(self.progress["review"])
            ws = [w for w in ws if w["id"] in rv]
        ws = list(ws)
        if self.fc_shuffle.get():
            random.shuffle(ws)
        self.fc_deck, self.fc_idx, self.fc_flipped = ws, 0, False
        self.fc_render()

    def fc_render(self):
        for l in (self.l_jp, self.l_rd, self.l_vi, self.l_en):
            l.config(text="")
        if not self.fc_deck:
            self.l_vi.config(text="Không có từ nào để hiển thị", fg=MUTED)
            self.l_hint.config(text="Hãy chọn ít nhất một bài (hoặc bỏ lọc 'Chỉ từ cần ôn')")
            self.fc_counter.config(text="0 / 0")
            self.star_btn.config(text="☆ Cần ôn")
            return
        w = self.fc_deck[self.fc_idx]
        self.l_vi.config(fg=INK)
        jp_to_vi = self.fc_dir.get().startswith("Nhật")
        if jp_to_vi:
            self.l_jp.config(text=w["jp"])
            if self.fc_flipped:
                self.l_rd.config(text=w["reading"])
                self.l_vi.config(text=w["vi"])
                self.l_en.config(text=w["en"])
        else:
            self.l_vi.config(text=w["vi"])
            if self.fc_flipped:
                self.l_jp.config(text=w["jp"])
                self.l_rd.config(text=w["reading"])
                self.l_en.config(text=w["en"])
        self.l_hint.config(text="" if self.fc_flipped else "Nhấn vào thẻ hoặc phím Space để lật")
        self.fc_counter.config(text=f"{self.fc_idx + 1} / {len(self.fc_deck)}  ·  Bài {w['lesson']}")
        self.star_btn.config(text="⭐ Đã đánh dấu ôn" if w["id"] in self.progress["review"] else "☆ Đánh dấu cần ôn")

    def fc_flip(self):
        if self.fc_deck:
            self.fc_flipped = not self.fc_flipped
            self.fc_render()

    def fc_move(self, d):
        if self.fc_deck:
            self.fc_idx = (self.fc_idx + d) % len(self.fc_deck)
            self.fc_flipped = False
            self.fc_render()

    def fc_say(self):
        if self.fc_deck:
            self.say(self.fc_deck[self.fc_idx])

    def fc_star(self):
        if not self.fc_deck:
            return
        wid = self.fc_deck[self.fc_idx]["id"]
        rv = self.progress["review"]
        rv.remove(wid) if wid in rv else rv.append(wid)
        save_progress(self.progress)
        self._update_scope_label()
        self.fc_render()

    # ============================================================ DANH SÁCH
    def show_list(self):
        self.tab = "list"
        self.clear()
        f = self.content
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="🔍 Tìm:").pack(side="left")
        self.q_var = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=self.q_var, width=32)
        ent.pack(side="left", padx=6)
        self.q_var.trace_add("write", lambda *a: self._fill_list())
        ttk.Button(bar, text="🔊 Nghe từ đang chọn", command=self._list_say).pack(side="right")

        cols = ("no", "jp", "rd", "vi", "en", "ls")
        tv = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
        for c, t, w, a in (("no", "#", 40, "center"), ("jp", "日本語", 190, "w"), ("rd", "Cách đọc", 220, "w"),
                           ("vi", "Tiếng Việt", 220, "w"), ("en", "English", 190, "w"), ("ls", "Bài", 45, "center")):
            tv.heading(c, text=t)
            tv.column(c, width=w, anchor=a)
        sb = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        tv.bind("<Double-1>", lambda e: self._list_say())
        self.tv = tv
        self._fill_list()

    def _fill_list(self):
        self.tv.delete(*self.tv.get_children())
        q = strip_accents(self.q_var.get()) if self.q_var.get() else ""
        raw = self.q_var.get().strip().lower()
        self.list_map = {}
        for w in self.selected():
            hay = " ".join([w["jp"], w["reading"], w["vi"], w["en"]]).lower()
            if raw and raw not in hay and (not q or q not in strip_accents(hay)):
                continue
            iid = self.tv.insert("", "end", values=(w["no"], w["jp"], w["reading"], w["vi"], w["en"], w["lesson"]))
            self.list_map[iid] = w

    def _list_say(self):
        sel = self.tv.selection()
        if sel:
            self.say(self.list_map[sel[0]])

    # ============================================================ THI THỬ: SETUP
    def show_exam_setup(self):
        self.tab = "exam"
        self.exam_running = False
        self.clear()
        f = self.content
        ttk.Label(f, text="Thi thử – Bài 1: Từ vựng FE", font=(self.UI, 20, "bold")).pack(anchor="w")
        ttk.Label(f, foreground=MUTED, text="Đề được sinh ngẫu nhiên từ các bài đã chọn ở cột bên trái. "
                  "Kết quả chỉ hiện sau khi nộp bài.").pack(anchor="w", pady=(2, 12))

        box = ttk.Labelframe(f, text=" Chọn đề ", style="Side.TLabelframe", padding=12)
        box.pack(fill="x")
        opts = [(0, "Đề đầy đủ – 4 phần, 20 câu, tối đa 30 điểm"),
                (1, "Chỉ Phần 1 – " + PART_TITLES[1] + "  [15đ]"),
                (2, "Chỉ Phần 2 – " + PART_TITLES[2] + "  [5đ]"),
                (3, "Chỉ Phần 3 – " + PART_TITLES[3] + "  [5đ]"),
                (4, "Chỉ Phần 4 – " + PART_TITLES[4] + "  [5đ]")]
        for v, t in opts:
            ttk.Radiobutton(box, text=t, value=v, variable=self.exam_mode).pack(anchor="w", pady=3)

        tips = ("Mẹo khi làm bài:\n"
                "• Phần 1: gõ romaji, app tự đổi sang hiragana (không cần bộ gõ tiếng Nhật); nghĩa tiếng Việt gõ có dấu hoặc không dấu đều được.\n"
                "• Phần 2: gõ romaji, app tự đổi sang katakana (ví dụ LAN → ran → ラン). Có thể dán katakana nếu có sẵn.\n"
                "• Phần 3: bấm 🔊 để nghe. Phần 3–4: chọn 1 trong 4 đáp án.\n"
                "• Sau khi nộp, bạn có thể tự đổi đúng/sai nếu hệ thống chấm quá chặt.")
        ttk.Label(f, text=tips, foreground=MUTED, justify="left").pack(anchor="w", pady=12)

        row = ttk.Frame(f)
        row.pack(anchor="w", pady=4)
        ttk.Button(row, text="▶  Bắt đầu làm bài", style="Accent.TButton", command=self.start_exam).pack(side="left")
        ttk.Label(row, text=f"   ({len(self.selected())} từ trong phạm vi)", foreground=MUTED).pack(side="left")

        hist = self.progress["history"][-5:]
        if hist:
            ttk.Label(f, text="Lịch sử gần đây", font=(self.UI, 12, "bold")).pack(anchor="w", pady=(18, 4))
            for h in reversed(hist):
                ttk.Label(f, text=f"{h['t']}   ·   {h['mode']}   ·   {h['score']} / {h['max']} điểm",
                          foreground=MUTED).pack(anchor="w")

    def start_exam(self):
        sel = self.selected()
        if len(sel) < 8:
            messagebox.showwarning("Chưa đủ từ", "Hãy chọn thêm bài (ít nhất vài chục từ) để sinh đề.")
            return
        m = self.exam_mode.get()
        parts = (1, 2, 3, 4) if m == 0 else (m,)
        qs = make_exam(sel, self.words, parts)
        if not qs:
            messagebox.showwarning("Không sinh được đề",
                                   "Phạm vi từ vựng hiện tại không có từ phù hợp cho phần này "
                                   "(ví dụ Phần 2 cần các từ viết bằng chữ cái như LAN, TCP/IP...).")
            return
        self.exam = {"qs": qs, "i": 0, "mode": "Đề đầy đủ" if m == 0 else f"Phần {m}"}
        self.exam_running = True
        self.render_question()

    # ============================================================ THI THỬ: LÀM BÀI
    def save_current(self):
        if not self.exam or not self.v:
            return
        q = self.exam["qs"][self.exam["i"]]
        p = q["part"]
        if p == 1:
            q["ans"] = {"r": romaji_to_kana(self.v["r"].get(), False, True), "m": self.v["m"].get()}
        elif p == 2:
            q["ans"] = {"k": romaji_to_kana(self.v["k"].get(), True, True)}
        else:
            q["ans"] = {"choice": self.v["c"].get()}

    def render_question(self):
        self.clear()
        ex = self.exam
        qs, i = ex["qs"], ex["i"]
        q = qs[i]
        w, p, a = q["word"], q["part"], q["ans"]
        f = self.content
        self.v = {}

        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Label(top, text=f"Câu {i + 1} / {len(qs)}", font=(self.UI, 13, "bold")).pack(side="left")
        ttk.Label(top, text=f"Tối đa {sum(max_points(x) for x in qs)} điểm", foreground=MUTED).pack(side="right")
        pb = ttk.Progressbar(f, maximum=len(qs), value=i + 1)
        pb.pack(fill="x", pady=6)
        ttk.Label(f, text=f"Phần {p}: {PART_TITLES[p]}", foreground=ACCENT,
                  font=(self.UI, 11, "bold"), wraplength=780).pack(anchor="w", pady=(0, 8))

        card = tk.Frame(f, bg="white", highlightbackground=LINE, highlightthickness=2)
        card.pack(fill="both", expand=True)
        inner = tk.Frame(card, bg="white")
        inner.place(relx=0.5, rely=0.46, anchor="center")

        first_entry = None
        if p == 1:
            tk.Label(inner, text=w["jp"], bg="white", fg=INK, font=(self.JP, 44, "bold"), wraplength=720).pack(pady=(0, 18))
            self.v["r"], self.v["m"] = tk.StringVar(value=a.get("r", "")), tk.StringVar(value=a.get("m", ""))
            g = tk.Frame(inner, bg="white")
            g.pack()
            tk.Label(g, text="Cách đọc (hiragana):", bg="white", font=(self.UI, 12)).grid(row=0, column=0, sticky="e", pady=6, padx=8)
            e1 = ttk.Entry(g, textvariable=self.v["r"], width=34, font=(self.JP, 16))
            e1.grid(row=0, column=1, pady=6)
            self.attach_romaji(e1, self.v["r"], False)
            tk.Label(g, text="Nghĩa tiếng Việt:", bg="white", font=(self.UI, 12)).grid(row=1, column=0, sticky="e", pady=6, padx=8)
            e2 = ttk.Entry(g, textvariable=self.v["m"], width=34, font=(self.UI, 16))
            e2.grid(row=1, column=1, pady=6)
            e1.bind("<Return>", lambda e: e2.focus_set())
            e2.bind("<Return>", lambda e: self.next_q())
            tk.Label(inner, text="Gõ romaji, ô sẽ tự đổi sang hiragana (vd: setsuzoku → せつぞく).\n"
                     "ん = nn hoặc n rồi Tab/Enter  ·  っ = gõ đôi phụ âm (kk, tt)  ·  ー = dấu -",
                     bg="white", fg=MUTED, font=(self.UI, 10), justify="center").pack(pady=(14, 0))
            first_entry = e1
        elif p == 2:
            tk.Label(inner, text=w["jp"], bg="white", fg=INK, font=(self.UI, 48, "bold")).pack(pady=(0, 18))
            self.v["k"] = tk.StringVar(value=a.get("k", ""))
            tk.Label(inner, text="Viết cách đọc bằng Katakana:", bg="white", font=(self.UI, 12)).pack()
            e = ttk.Entry(inner, textvariable=self.v["k"], width=30, font=(self.JP, 20), justify="center")
            e.pack(pady=8)
            self.attach_romaji(e, self.v["k"], True)
            e.bind("<Return>", lambda e: self.next_q())
            tk.Label(inner, text="Gõ romaji, ô sẽ tự đổi sang katakana (vd: ran → ラン, thi-shi- → ティーシー).\n"
                     "ン = nn hoặc n rồi Tab/Enter  ·  ッ = gõ đôi phụ âm  ·  ー = dấu -  ·  ティ = thi, ディ = dhi",
                     bg="white", fg=MUTED, font=(self.UI, 10), justify="center").pack(pady=(6, 0))
            first_entry = e
        else:
            self.v["c"] = tk.IntVar(value=a.get("choice", -1))
            if p == 3:
                if TTS["ok"] is False:
                    tk.Label(inner, text=f"⚠ Máy chưa có giọng đọc tiếng Nhật.\nTừ cần nghe: {w['jp']}",
                             bg="white", fg=BAD, font=(self.JP, 14), justify="center").pack(pady=10)
                else:
                    tk.Label(inner, text="🔊", bg="white", font=(self.UI, 40)).pack()
                    ttk.Button(inner, text="Nghe lại", command=lambda: self.say(w)).pack(pady=(0, 10))
                    self.after(350, lambda ww=w: self.say(ww))
            else:
                tk.Label(inner, text=w["vi"], bg="white", fg=INK, font=(self.UI, 30, "bold"),
                         wraplength=700).pack(pady=(0, 14))
            font = (self.UI, 15) if p == 3 else (self.JP, 16)
            for k, opt in enumerate(q["options"]):
                tk.Radiobutton(inner, text=f"  {'ABCD'[k]}.  {opt}", value=k, variable=self.v["c"],
                               indicatoron=0, anchor="w", font=font, width=44, bd=1, relief="solid",
                               bg="white", selectcolor="#dbeafe", activebackground="#eff6ff",
                               padx=10, pady=8).pack(pady=4)

        nav = ttk.Frame(f)
        nav.pack(fill="x", pady=(10, 0))
        if i > 0:
            ttk.Button(nav, text="◀ Câu trước", command=self.prev_q).pack(side="left")
        ttk.Button(nav, text="Hủy bài", command=self.cancel_exam).pack(side="left", padx=8)
        last = i == len(qs) - 1
        ttk.Button(nav, text="Nộp bài ✔" if last else "Câu sau ▶", style="Accent.TButton",
                   command=self.finish_exam if last else self.next_q).pack(side="right")
        if first_entry is not None:
            self.after(100, first_entry.focus_set)

    def next_q(self):
        self.save_current()
        if self.exam["i"] < len(self.exam["qs"]) - 1:
            self.exam["i"] += 1
            self.render_question()
        else:
            self.finish_exam()

    def prev_q(self):
        self.save_current()
        self.exam["i"] -= 1
        self.render_question()

    def cancel_exam(self):
        if messagebox.askyesno("Hủy bài", "Hủy bài thi hiện tại?"):
            self.exam_running = False
            self.exam, self.v = None, {}
            self.show_exam_setup()

    def _answered(self, q):
        a = q["ans"]
        if q["part"] == 1:
            return bool(a.get("r", "").strip() or a.get("m", "").strip())
        if q["part"] == 2:
            return bool(a.get("k", "").strip())
        return a.get("choice", -1) >= 0

    def finish_exam(self):
        self.save_current()
        blank = sum(1 for q in self.exam["qs"] if not self._answered(q))
        if blank and not messagebox.askyesno("Nộp bài", f"Còn {blank} câu chưa trả lời. Vẫn nộp bài?"):
            return
        self.v = {}
        for q in self.exam["qs"]:
            grade(q)
        rv = self.progress["review"]
        for q in self.exam["qs"]:
            if points(q) < max_points(q) and q["word"]["id"] not in rv:
                rv.append(q["word"]["id"])
        self.exam_running = False
        self.show_results(first=True)

    # ============================================================ KẾT QUẢ
    def total(self):
        qs = self.exam["qs"]
        return sum(points(q) for q in qs), sum(max_points(q) for q in qs)

    def update_score(self):
        s, m = self.total()
        self.score_lbl.config(text=f"{s} / {m} điểm", foreground=GOOD if s >= 0.6 * m else BAD)
        parts = []
        for p in (1, 2, 3, 4):
            qs = [q for q in self.exam["qs"] if q["part"] == p]
            if qs:
                parts.append(f"Phần {p}: {sum(points(q) for q in qs)}/{sum(max_points(q) for q in qs)}")
        self.part_lbl.config(text="    ".join(parts))

    def show_results(self, first=False):
        self.clear()
        f = self.content
        head = ttk.Frame(f)
        head.pack(fill="x")
        ttk.Label(head, text="Kết quả:", font=(self.UI, 16, "bold")).pack(side="left")
        self.score_lbl = ttk.Label(head, font=(self.UI, 26, "bold"))
        self.score_lbl.pack(side="left", padx=12)
        ttk.Button(head, text="Làm đề mới", style="Accent.TButton", command=self.show_exam_setup).pack(side="right")
        self.part_lbl = ttk.Label(f, foreground=MUTED)
        self.part_lbl.pack(anchor="w", pady=(2, 2))
        ttk.Label(f, foreground=MUTED,
                  text="Các từ làm sai đã được đánh dấu ⭐ cần ôn. Nếu hệ thống chấm sai, bỏ/tick ô bên dưới để sửa điểm.").pack(anchor="w", pady=(0, 6))
        self.update_score()
        if first:
            s, m = self.total()
            self.progress["history"].append({"t": datetime.now().strftime("%d/%m %H:%M"),
                                             "mode": self.exam["mode"], "score": s, "max": m})
            self.progress["history"] = self.progress["history"][-30:]
            save_progress(self.progress)
            self._update_scope_label()

        sf = ScrollFrame(f)
        sf.pack(fill="both", expand=True)
        for n, q in enumerate(self.exam["qs"], 1):
            self._result_row(sf.inner, n, q)

    def _result_row(self, parent, n, q):
        w, p, a = q["word"], q["part"], q["ans"]
        row = tk.Frame(parent, bg="white", highlightbackground=LINE, highlightthickness=1)
        row.pack(fill="x", pady=4, padx=(0, 8))
        pad = {"anchor": "w", "padx": 10}
        tk.Label(row, text=f"Câu {n} · Phần {p} ({PART_SHORT[p]})", bg="white", fg=MUTED,
                 font=(self.UI, 10, "bold")).pack(pady=(6, 0), **pad)
        L = lambda t, fg=INK, font=None: tk.Label(row, text=t, bg="white", fg=fg, justify="left", wraplength=760,
                                                  font=font or (self.JP, 12)).pack(**pad)
        if p == 1:
            L(w["jp"], font=(self.JP, 20, "bold"))
            L(f"Đáp án: {w['reading']}   —   {w['vi']}   ({w['en']})", GOOD)
            L(f"Bạn trả lời: {a.get('r', '') or '(trống)'}   —   {a.get('m', '') or '(trống)'}", MUTED)
        elif p == 2:
            L(w["jp"], font=(self.UI, 20, "bold"))
            L(f"Đáp án: {w['reading']}", GOOD)
            L(f"Bạn trả lời: {a.get('k', '') or '(trống)'}", MUTED)
        elif p == 3:
            L(f"🔊 {w['jp']}  ({w['reading']})", font=(self.JP, 16, "bold"))
            L(f"Đáp án: {q['options'][q['correct']]}", GOOD)
            ch = a.get("choice", -1)
            L(f"Bạn chọn: {q['options'][ch] if ch >= 0 else '(trống)'}", MUTED)
        else:
            L(w["vi"], font=(self.UI, 16, "bold"))
            L(f"Đáp án: {w['jp']}  ({w['reading']})", GOOD)
            ch = a.get("choice", -1)
            L(f"Bạn chọn: {q['options'][ch] if ch >= 0 else '(trống)'}", MUTED)

        fr = tk.Frame(row, bg="white")
        fr.pack(anchor="w", padx=10, pady=(2, 8))
        for key, label, pt in FLAG_DEFS[p]:
            var = tk.BooleanVar(value=q["flags"][key])

            def cb(k=key, v=var, qq=q):
                qq["flags"][k] = v.get()
                self.update_score()
            tk.Checkbutton(fr, text=f"{label} đúng ({pt}đ)", variable=var, command=cb, bg="white",
                           activebackground="white", font=(self.UI, 11)).pack(side="left", padx=(0, 14))


# ======================================================================
def main():
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor: chữ nét trên màn hình độ phân giải cao
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
    path = VOCAB_FILE
    if not os.path.exists(path):
        r = tk.Tk()
        r.withdraw()
        messagebox.showinfo("Chọn file từ vựng", "Không tìm thấy tuvung.txt cạnh chương trình.\nHãy chọn file từ vựng.")
        path = filedialog.askopenfilename(title="Chọn tuvung.txt", filetypes=[("Text", "*.txt"), ("All", "*.*")])
        r.destroy()
        if not path:
            return
    words = load_vocab(path)
    if not words:
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("Lỗi", "File từ vựng trống hoặc sai định dạng (STT <tab> Nhật <tab> Đọc <tab> Việt, English).")
        return
    App(words).mainloop()


if __name__ == "__main__":
    main()
