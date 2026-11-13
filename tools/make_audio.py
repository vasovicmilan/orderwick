"""Generates ALL game sounds (effects + music) from code, so they are 100% ours (no licence, no third-party copyright).

    python tools/make_audio.py            # writes assets/audio/sfx/*.wav and assets/audio/music/*.ogg

Principles against fatigue (audio fatigue):
  * every effect exists in several slightly different pitches; the game picks a different one each time;
  * card pairing plays a PENTATONIC scale that climbs in a row (C D E G A ...), so every move is another note and never a dissonance;
  * the music is quiet, drumless, slow (70-85 BPM), marimba/kalimba/vibes/pad; several songs in random order with pauses.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "audio"
SR = 44100
PENTA = [0, 2, 4, 7, 9]                       # major pentatonic (semitones from the tonic)


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def t_axis(dur: float) -> np.ndarray:
    return np.arange(int(SR * dur)) / SR


def fade(x: np.ndarray, a: float = 0.003, r: float = 0.01) -> np.ndarray:
    n = len(x)
    na, nr = min(n, int(a * SR)), min(n, int(r * SR))
    x = x.copy()
    if na:
        x[:na] *= np.linspace(0, 1, na)
    if nr:
        x[-nr:] *= np.linspace(1, 0, nr)
    return x


def lowpass(x, cutoff, order=2):
    b, a = signal.butter(order, cutoff / (SR / 2), "low")
    return signal.lfilter(b, a, x)


def highpass(x, cutoff, order=2):
    b, a = signal.butter(order, cutoff / (SR / 2), "high")
    return signal.lfilter(b, a, x)


def bandpass(x, lo, hi, order=2):
    b, a = signal.butter(order, [lo / (SR / 2), hi / (SR / 2)], "band")
    return signal.lfilter(b, a, x)


def pitch(x: np.ndarray, ratio: float) -> np.ndarray:
    """Pitch change (and duration) by resampling; enough for small differences of +-6%."""
    n = int(len(x) / ratio)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)


# ---------------------------------------------------------------------------- instrumenti ------
def marimba(freq: float, dur: float = 0.6, vel: float = 1.0) -> np.ndarray:
    t = t_axis(dur)
    y = (np.sin(2 * np.pi * freq * t) * np.exp(-t / 0.32)
         + 0.38 * np.sin(2 * np.pi * freq * 3.93 * t) * np.exp(-t / 0.10)
         + 0.12 * np.sin(2 * np.pi * freq * 9.2 * t) * np.exp(-t / 0.035))
    click = np.random.default_rng(int(freq)).normal(0, 1, len(t)) * np.exp(-t / 0.004) * 0.06
    return fade(lowpass(y + click, 7000), 0.002, 0.05) * vel


def kalimba(freq: float, dur: float = 0.9, vel: float = 1.0) -> np.ndarray:
    t = t_axis(dur)
    y = (np.sin(2 * np.pi * freq * t) * np.exp(-t / 0.45)
         + 0.25 * np.sin(2 * np.pi * freq * 5.4 * t) * np.exp(-t / 0.05)
         + 0.08 * np.sin(2 * np.pi * freq * 2.0 * t) * np.exp(-t / 0.2))
    return fade(y, 0.001, 0.08) * vel


def vibes(freq: float, dur: float = 1.6, vel: float = 1.0) -> np.ndarray:
    """Vibraphone: a clean tone with a gentle tremolo."""
    t = t_axis(dur)
    trem = 1 + 0.18 * np.sin(2 * np.pi * 5.0 * t)
    y = (np.sin(2 * np.pi * freq * t) * np.exp(-t / 0.9) + 0.18 * np.sin(2 * np.pi * freq * 4.0 * t) * np.exp(-t / 0.25)) * trem
    return fade(y, 0.002, 0.12) * vel


def pluck(freq: float, dur: float = 0.7, vel: float = 1.0) -> np.ndarray:
    """Drveni "pluck" (Karplus-Strong): topao, malo suv ton."""
    n = int(SR * dur)
    period = max(2, int(SR / freq))
    buf = np.random.default_rng(int(freq * 10)).uniform(-1, 1, period)
    out = np.empty(n)
    for i in range(n):
        out[i] = buf[i % period]
        buf[i % period] = 0.4975 * (buf[i % period] + buf[(i + 1) % period])
    return fade(lowpass(out, 5000), 0.001, 0.08) * vel


def bell(freq: float, dur: float = 1.4, vel: float = 1.0) -> np.ndarray:
    t = t_axis(dur)
    y = sum(a * np.sin(2 * np.pi * freq * m * t) * np.exp(-t / d)
            for m, a, d in ((1.0, 1.0, 0.7), (2.76, 0.45, 0.35), (5.4, 0.2, 0.18), (8.93, 0.08, 0.1)))
    return fade(y, 0.001, 0.15) * vel


def pad(freq: float, dur: float, vel: float = 1.0, seed: int = 0) -> np.ndarray:
    t = t_axis(dur)
    y = np.zeros_like(t)
    for d in (-0.07, 0.0, 0.06):                      # tri blago razdesena sinusa = topao "chorus"
        y += np.sin(2 * np.pi * freq * 2 ** (d / 12) * t + seed)
    env = np.minimum(1.0, t / 1.2) * np.minimum(1.0, (dur - t) / 1.5).clip(0)
    return lowpass(y / 3, 1800) * env * vel


def reverb(x: np.ndarray, wet: float = 0.22, length: float = 1.4, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(SR * length)
    ir = rng.normal(0, 1, n) * np.exp(-np.arange(n) / (SR * length / 4.5))
    ir = lowpass(ir, 4500)
    ir /= np.abs(ir).max()
    tail = signal.fftconvolve(x, ir)[: len(x) + n // 2]
    tail /= max(np.abs(tail).max(), 1e-9)
    base = np.pad(x, (0, len(tail) - len(x)))
    return base * (1 - wet) + tail * wet * np.abs(x).max()


def mix(parts: list[tuple[float, np.ndarray]], total: float) -> np.ndarray:
    out = np.zeros(int(SR * total))
    for start, snd in parts:
        i = int(start * SR)
        end = min(len(out), i + len(snd))
        if i < len(out):
            out[i:end] += snd[: end - i]
    return out


def norm(x: np.ndarray, peak: float) -> np.ndarray:
    return x / max(np.abs(x).max(), 1e-9) * peak


# ---------------------------------------------------------------------------- efekti ----------
def sfx_pick() -> np.ndarray:
    t = t_axis(0.07)
    rng = np.random.default_rng(3)
    y = highpass(rng.normal(0, 1, len(t)), 2500) * np.exp(-t / 0.012) * 0.5 + np.sin(2 * np.pi * 1500 * t) * np.exp(-t / 0.02) * 0.4
    return fade(y)


def sfx_place() -> np.ndarray:
    t = t_axis(0.16)
    f = 210 * np.exp(-t * 9) + 120
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.05)
    y += np.random.default_rng(5).normal(0, 1, len(t)) * np.exp(-t / 0.006) * 0.15
    return fade(lowpass(y, 2200), 0.001, 0.03)


def sfx_reveal() -> np.ndarray:
    t = t_axis(0.11)
    rng = np.random.default_rng(7)
    n = rng.normal(0, 1, len(t))
    y = bandpass(n, 1200, 5000) * np.sin(np.pi * t / t[-1]) ** 2 * 0.5
    return fade(y)


def sfx_invalid() -> np.ndarray:
    t = t_axis(0.2)
    f = np.where(t < 0.1, 262.0, 196.0)
    y = (np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.5 + np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.exp(-(t % 0.1) / 0.05)
    return fade(lowpass(y, 1200), 0.003, 0.04) * 0.6


def sfx_undo() -> np.ndarray:
    return mix([(0.0, marimba(hz(67), 0.4)), (0.11, marimba(hz(64), 0.45) * 0.9)], 0.6)


def sfx_rescue() -> np.ndarray:
    notes = [72, 76, 79, 84, 88]
    return reverb(mix([(0.07 * i, kalimba(hz(n), 0.8, 0.8)) for i, n in enumerate(notes)], 1.2), 0.25)


def sfx_win() -> np.ndarray:
    parts = [(0.0, marimba(hz(60), 1.0)), (0.13, marimba(hz(64), 1.0)), (0.26, marimba(hz(67), 1.0)),
             (0.39, marimba(hz(72), 1.4)), (0.52, marimba(hz(76), 1.6)), (0.52, bell(hz(84), 1.6, 0.45))]
    return reverb(mix(parts, 2.3), 0.3, 1.6)


def sfx_unlock() -> np.ndarray:
    return reverb(mix([(0.0, bell(hz(79), 1.4, 0.9)), (0.18, bell(hz(86), 1.6, 0.8))], 1.9), 0.25)


def sfx_achievement() -> np.ndarray:
    return reverb(mix([(0.0, bell(hz(72), 1.2, 0.8)), (0.14, bell(hz(79), 1.2, 0.8)),
                       (0.28, bell(hz(84), 1.8, 0.9)), (0.28, marimba(hz(72), 1.0, 0.5))], 2.1), 0.28)


def sfx_column_done() -> np.ndarray:
    """Cela kolona slozena: najsvecaniji efekat - zvonki akord + marimba."""
    parts = [(0.0, marimba(hz(67), 1.2, 0.9)), (0.0, bell(hz(79), 1.8, 0.55)), (0.07, marimba(hz(72), 1.2, 0.85)),
             (0.14, marimba(hz(76), 1.2, 0.85)), (0.21, bell(hz(88), 2.0, 0.5)), (0.21, marimba(hz(79), 1.4, 0.8))]
    return reverb(mix(parts, 2.6), 0.28, 1.5)


def sfx_ui_move() -> np.ndarray:
    t = t_axis(0.045)
    return fade(np.sin(2 * np.pi * 900 * t) * np.exp(-t / 0.012) * 0.5, 0.001, 0.01)


def sfx_ui_click() -> np.ndarray:
    t = t_axis(0.09)
    y = np.sin(2 * np.pi * 520 * t) * np.exp(-t / 0.03) + 0.4 * np.sin(2 * np.pi * 1040 * t) * np.exp(-t / 0.015)
    return fade(lowpass(y, 3000) * 0.6, 0.001, 0.02)


def sfx_ui_back() -> np.ndarray:
    t = t_axis(0.09)
    return fade(np.sin(2 * np.pi * 380 * t) * np.exp(-t / 0.03) * 0.6, 0.001, 0.02)


def sfx_restart() -> np.ndarray:
    rng = np.random.default_rng(11)
    t = t_axis(0.35)
    sweep = bandpass(rng.normal(0, 1, len(t)), 600, 3000) * np.sin(np.pi * t / t[-1])
    return fade(sweep * 0.5, 0.01, 0.05)


# pitch variants: (name, function, pitch ratios, peak)
VARIANTS = {
    "pick": (sfx_pick, [0.92, 0.96, 1.0, 1.04, 1.08], 0.55),
    "place": (sfx_place, [0.9, 0.95, 1.0, 1.05, 1.1], 0.8),
    "reveal": (sfx_reveal, [0.9, 1.0, 1.1], 0.4),
    "invalid": (sfx_invalid, [0.95, 1.0, 1.05], 0.6),
    "undo": (sfx_undo, [1.0], 0.7),
    "rescue": (sfx_rescue, [1.0], 0.7),
    "win": (sfx_win, [1.0], 0.8),
    "unlock": (sfx_unlock, [1.0], 0.7),
    "achievement": (sfx_achievement, [1.0], 0.75),
    "restart": (sfx_restart, [0.95, 1.05], 0.5),
    "column_done": (sfx_column_done, [0.97, 1.0, 1.03], 1.0),
    "ui_move": (sfx_ui_move, [0.94, 1.0, 1.06], 0.35),
    "ui_click": (sfx_ui_click, [0.96, 1.0, 1.04], 0.5),
    "ui_back": (sfx_ui_back, [0.96, 1.0, 1.04], 0.5),
}


def write_wav(path: Path, x: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(str(path), SR, (np.clip(x, -1, 1) * 32767).astype(np.int16))


def make_sfx() -> int:
    n = 0
    for name, (fn, ratios, peak) in VARIANTS.items():
        base = fn()
        for i, r in enumerate(ratios):
            write_wav(OUT / "sfx" / f"{name}_{i}.wav", norm(pitch(base, r) if r != 1.0 else base, peak))
            n += 1
    # card pairing: a climbing pentatonic scale (C4..A5) in three timbres (marimba, kalimba, wooden pluck);
    # the game picks a different timbre for each pairing and slightly changes the volume
    for tag, fn in (("pairA", marimba), ("pairB", kalimba), ("pairC", pluck)):
        for i in range(10):
            midi = 60 + PENTA[i % 5] + 12 * (i // 5)
            write_wav(OUT / "sfx" / f"{tag}_{i}.wav", norm(reverb(fn(hz(midi), 0.7), 0.15, 0.8), 0.7))
            n += 1
    return n


# ---------------------------------------------------------------------------- muzika ----------
TRACKS = [
    # ime, tonika (midi), bpm, progresija (stepeni dur lestvice: 0=I, 5=vi, 3=IV, 4=V), karakter
    ("morning_deck", 60, 78, [0, 5, 3, 4], "marimba"),
    ("quiet_orchard", 67, 72, [0, 3, 5, 4], "kalimba"),
    ("slow_harvest", 65, 84, [5, 3, 0, 4], "marimba"),
    ("soft_table", 62, 76, [0, 4, 5, 3], "kalimba"),
    ("clover_hill", 62, 74, [0, 3, 4, 5], "vibes"),
    ("evening_tea", 69, 70, [5, 3, 0, 4], "vibes"),
    ("paper_boats", 58, 82, [0, 4, 3, 0], "marimba"),
    ("lantern_walk", 64, 72, [0, 5, 4, 3], "kalimba"),
]
MAJOR = [0, 2, 4, 5, 7, 9, 11]


def chord_tones(root: int, degree: int) -> list[int]:
    base = root + MAJOR[degree % 7]
    third = root + MAJOR[(degree + 2) % 7] + (12 if (degree + 2) >= 7 else 0)
    fifth = root + MAJOR[(degree + 4) % 7] + (12 if (degree + 4) >= 7 else 0)
    return [base, third, fifth]


def compose(name: str, root: int, bpm: int, prog: list[int], lead: str, bars: int = 32) -> np.ndarray:
    rng = np.random.default_rng(abs(hash(name)) % (2 ** 32) if False else sum(map(ord, name)))
    beat = 60.0 / bpm
    bar_len = 4 * beat
    total = bars * bar_len + 4.0
    L = np.zeros(int(SR * total))
    R = np.zeros_like(L)

    def put(snd: np.ndarray, start: float, pan: float = 0.0) -> None:
        i = int(start * SR)
        end = min(len(L), i + len(snd))
        if i >= len(L):
            return
        gl, gr = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        L[i:end] += snd[: end - i] * gl
        R[i:end] += snd[: end - i] * gr

    lead_fn = {"marimba": marimba, "kalimba": kalimba, "vibes": vibes}[lead]
    arp_fn = kalimba if lead in ("marimba", "vibes") else marimba
    scale = [root + p + 12 * o for o in (0, 1) for p in PENTA]          # pentatonika, 2 oktave
    for bar in range(bars):
        deg = prog[bar % len(prog)]
        tones = chord_tones(root, deg)
        t0 = bar * bar_len
        # pad: whole bar, soft
        for k, tone in enumerate(tones):
            put(pad(hz(tone - 12), bar_len + 1.0, 0.09, seed=k), t0, pan=-0.3 + 0.3 * k)
        # bass: first and third beat (the 3rd is sometimes skipped)
        put(marimba(hz(tones[0] - 24), 1.2, 0.5), t0, 0.0)
        if rng.random() < 0.75:
            put(marimba(hz(tones[2] - 24), 1.0, 0.35), t0 + 2 * beat, 0.0)
        # arpeggio: eighth notes, quiet, with rests (never the same bar twice in a row)
        pattern = rng.choice([[0, 1, 2, 1], [0, 2, 1, 2], [2, 1, 0, 1], [0, 1, 2, 3]])
        for step in range(8):
            if rng.random() < 0.3:
                continue
            idx = int(pattern[step % 4])
            tone = tones[idx % 3] + 12 * (1 + (idx // 3) + int(rng.random() < 0.2))
            put(arp_fn(hz(tone), 0.9, 0.22 + 0.08 * rng.random()), t0 + step * beat / 2, pan=rng.uniform(-0.6, 0.6))
        # melody: every second/third bar, 2-4 pentatonic notes, calm
        if bar % 2 == 0 and rng.random() < 0.8 and bar >= 2:
            pos = int(rng.integers(3, 8))
            when = t0 + beat * float(rng.choice([0, 0.5, 1.0]))
            for _ in range(int(rng.integers(2, 5))):
                put(lead_fn(hz(scale[pos]), 1.2, 0.4), when, pan=0.25)
                when += beat * float(rng.choice([1.0, 1.5, 2.0]))
                pos = int(np.clip(pos + rng.choice([-2, -1, -1, 1, 1, 2]), 0, len(scale) - 1))
        # quiet shaker (odd bars only, barely audible)
        if bar % 2 == 1:
            for b in range(4):
                n = bandpass(rng.normal(0, 1, int(0.05 * SR)), 5000, 9000) * np.exp(-np.arange(int(0.05 * SR)) / (SR * 0.012))
                put(n * 0.03, t0 + (b + 0.5) * beat, pan=0.4)
    # zajednicki reverb preko oba kanala
    L = reverb(L, 0.25, 1.8, seed=2)[: len(L)]
    R = reverb(R, 0.25, 1.8, seed=3)[: len(R)]
    stereo = np.stack([L, R], 1)
    stereo = stereo / np.abs(stereo).max() * 0.55
    fi, fo = int(2.0 * SR), int(3.0 * SR)
    stereo[:fi] *= np.linspace(0, 1, fi)[:, None]
    stereo[-fo:] *= np.linspace(1, 0, fo)[:, None]
    return stereo


TARGET_LUFS = -20.0


def loudness_filter(wav: Path) -> str:
    """Two-pass EBU R128 normalisation (ffmpeg loudnorm, linear mode): measure first, then apply an exact gain."""
    import json
    base = f"loudnorm=I={TARGET_LUFS}:TP=-2:LRA=11"
    probe = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav), "-af", base + ":print_format=json",
                            "-f", "null", "-"], capture_output=True, text=True, check=True).stderr
    m = json.loads(probe[probe.rindex("{"):probe.rindex("}") + 1])
    return (base + f":measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
            f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")


def make_music() -> int:
    (OUT / "music").mkdir(parents=True, exist_ok=True)
    for name, root, bpm, prog, lead in TRACKS:
        stereo = compose(name, root, bpm, prog, lead)
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / f"{name}.wav"
            wavfile.write(str(wav), SR, (stereo * 32767).astype(np.int16))
            norm_filter = loudness_filter(wav)                       # every song ends up at the same loudness
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-af", norm_filter,
                            "-c:a", "libvorbis", "-q:a", "3", str(OUT / "music" / f"{name}.ogg")], check=True)
        print("music", name, f"{len(stereo) / SR:.0f}s")
    return len(TRACKS)


def main() -> None:
    np.random.seed(0)
    print("sfx files:", make_sfx())
    if "--no-music" not in sys.argv:
        print("tracks:", make_music())


if __name__ == "__main__":
    main()
