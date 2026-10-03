"""Звук 3D-версии: процедурные wav (numpy) + звуковая система Panda3D.

Двигатель — одна петля, высота тона меняется по оборотам (play rate).
"""
import os
import wave

import numpy as np
from panda3d.core import Filename, AudioSound
from i18n import T

SR = 22050
BASE_RPM = 1500.0
DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")


def _write(name, w):
    path = os.path.join(DIR, name + ".wav")
    w = np.clip(w, -1, 1)
    a = (w * 30000).astype(np.int16)
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(a.tobytes())


def _engine(rpm):
    f = rpm / 60.0 * 2.0
    n_cycles = max(8, int(round(f * 1.0)))
    t = np.arange(int(SR * n_cycles / f)) / SR
    w = np.zeros_like(t)
    for k, a in ((1, 1.0), (2, 0.5), (3, 0.35), (4, 0.18), (6, 0.08)):
        w += a * np.sin(2 * np.pi * k * f * t + k)
    w += 0.35 * np.sin(np.pi * f * t)
    w += 0.3 * (np.sin(2 * np.pi * f * t) > 0.6).astype(float)
    rng = np.random.default_rng(3)
    noise = np.convolve(rng.standard_normal(len(t)), np.ones(6) / 6, mode="same")
    w += noise * 0.22
    return w / np.max(np.abs(w)) * 0.8


def _noise(dur, vol, low=False, decay=False, seed=0):
    n = int(SR * dur)
    w = np.random.default_rng(seed).standard_normal(n)
    if low:
        w = np.convolve(w, np.ones(20) / 20, mode="same") * 3
    if decay:
        w *= np.exp(-np.linspace(0, 6, n))
    return w * vol


def _tone(dur, f, vol, noise=0.0):
    t = np.arange(int(SR * dur)) / SR
    w = np.sign(np.sin(2 * np.pi * f * t)) * 0.3 + np.sin(2 * np.pi * f * 1.5 * t) * 0.3
    w += np.random.default_rng(1).standard_normal(len(t)) * noise
    env = np.minimum(1, np.minimum(t * 40, (dur - t) * 20))
    return w * vol * env


def _decay(dur, f, vol):
    t = np.arange(int(SR * dur)) / SR
    w = np.sin(2 * np.pi * f * t * (1 - t / dur * 0.5)) + np.random.default_rng(2).standard_normal(len(t)) * 0.2
    return w * vol * np.exp(-t * 6)


def generate():
    os.makedirs(DIR, exist_ok=True)
    if not os.path.exists(os.path.join(DIR, "bov.wav")):
        # «пшшш» перепускного клапана турбины: шипящий шум с быстрым затуханием
        n = int(SR * 0.45)
        w = np.random.default_rng(12).standard_normal(n)
        w = w - np.convolve(w, np.ones(8) / 8, mode="same")        # только высокие частоты
        tt_ = np.arange(n) / SR
        _write("bov", w * np.exp(-tt_ * 7) * np.minimum(1, tt_ * 60) * 0.5)
    if os.path.exists(os.path.join(DIR, "blitz.wav")):
        return
    t = lambda d: np.arange(int(SR * d)) / SR
    _write("engine", _engine(BASE_RPM))
    _write("rattle", _noise(1.0, 0.5, low=True, seed=4))
    tt = t(0.6)
    _write("crank", (np.sin(2 * np.pi * 180 * tt) * 0.3 + np.random.default_rng(5).standard_normal(len(tt)) * 0.1)
           * ((np.sin(2 * np.pi * 5 * tt) > 0) * 0.5 + 0.5) * 0.8)
    _write("rain", _noise(2.0, 0.25, seed=6))
    _write("skid", _tone(0.5, 1250, 0.25, noise=0.4))
    tt = t(0.08)
    _write("click", np.sin(2 * np.pi * 800 * tt) * np.exp(-tt * 80) * 0.7)
    _write("start", _noise(0.25, 0.4, low=True, seed=7))
    _write("stall", _decay(0.5, 60, 0.6))
    tt = t(0.12)
    _write("misfire", np.random.default_rng(8).standard_normal(len(tt)) * np.exp(-tt * 40) * 0.8)
    _write("crash", _noise(0.5, 0.9, decay=True, seed=9))
    _write("grind", _tone(0.4, 900, 0.3, noise=0.6))
    tt = t(0.5)
    _write("horn", (np.sign(np.sin(2 * np.pi * 330 * tt)) * 0.3 + np.sign(np.sin(2 * np.pi * 415 * tt)) * 0.3)
           * np.minimum(1, (0.5 - tt) * 30))
    tt = t(0.3)
    _write("cash", (np.sin(2 * np.pi * 1800 * tt) + np.sin(2 * np.pi * 2400 * tt)) * np.exp(-tt * 12) * 0.3)
    _write("door", _decay(0.2, 120, 0.5))
    _write("weld", _noise(1.2, 0.35, seed=10))
    tt = t(0.25)
    _write("tool", (np.sin(2 * np.pi * 1300 * tt) * 0.5 + np.sin(2 * np.pi * 2100 * tt) * 0.3) * np.exp(-tt * 25))
    tt = t(1.6)
    f = np.where((tt * 1.25) % 1 < 0.5, 440, 585)
    _write("police", np.sign(np.sin(np.cumsum(2 * np.pi * f / SR))) * 0.2)
    tt = t(0.4)
    _write("step", np.random.default_rng(11).standard_normal(len(tt)) * np.exp(-tt * 60) * 0.25)
    _write("blitz", _tone(0.12, 2600, 0.3))


def generate_locks():
    """Звуки замков (дописываются к уже созданным звукам, если их ещё нет)."""
    if os.path.exists(os.path.join(DIR, "handle.wav")):
        return
    t = lambda d: np.arange(int(SR * d)) / SR
    rng = np.random.default_rng(21)
    tt = t(0.18)
    thunk = lambda f, k: np.sin(2 * np.pi * f * tt) * np.exp(-tt * k)
    # центральный замок: два быстрых «клац» (запереть — ниже, отпереть — выше)
    for name, f in (("lock", 520), ("unlock", 760)):
        a = thunk(f, 55) * 0.5 + rng.standard_normal(len(tt)) * np.exp(-tt * 90) * 0.35
        out = np.zeros(int(SR * 0.32))
        out[:len(a)] += a
        out[int(SR * 0.09):int(SR * 0.09) + len(a)] += a * 0.8
        _write(name, out)
    # дёрнули запертую ручку: сухой щелчок и дребезг
    tt = t(0.25)
    _write("handle", (rng.standard_normal(len(tt)) * np.exp(-tt * 30) * 0.3 + np.sin(2 * np.pi * 300 * tt)
                      * np.exp(-tt * 20) * 0.3) * (np.sin(2 * np.pi * 22 * tt) > -0.3))
    # ключ в замке: короткий металлический скрежет
    tt = t(0.2)
    _write("key", rng.standard_normal(len(tt)) * np.exp(-tt * 18) * 0.18 * np.sin(2 * np.pi * 40 * tt) ** 2)


class Audio3D:
    ONE_SHOTS = ["click", "start", "stall", "misfire", "crash", "grind", "horn", "cash", "door", "weld",
                 "tool", "police", "blitz", "step", "bov", "lock", "unlock", "handle", "key"]

    def __init__(self, loader):
        self.ok = False
        try:
            generate()
            generate_locks()
            self.loader = loader
            self.loops = {n: self._load(n, loop=True) for n in ("engine", "rattle", "crank", "rain", "skid")}
            self.fx = {n: [self._load(n) for _ in range(3)] for n in self.ONE_SHOTS}
            self.fx_i = {n: 0 for n in self.ONE_SHOTS}
            for s in self.loops.values():
                s.setVolume(0)
                s.play()
            self.ok = True
        except Exception as e:  # без звука игра тоже работает
            print(T("Звук отключён:"), e)

    def _load(self, name, loop=False):
        s = self.loader.loadSfx(Filename.fromOsSpecific(os.path.join(DIR, name + ".wav")))
        s.setLoop(loop)
        return s

    def play(self, name, vol=1.0):
        if not self.ok or name not in self.fx:
            return
        i = self.fx_i[name]
        self.fx_i[name] = (i + 1) % 3
        s = self.fx[name][i]
        s.setVolume(vol)
        s.play()

    def engine(self, running, rpm, throttle, cranking, exhaust, volume=1.0, skid=False):
        if not self.ok:
            return
        e = self.loops["engine"]
        if running and rpm > 100:
            e.setPlayRate(max(0.35, min(4.5, rpm / BASE_RPM)))
            e.setVolume(min(1.0, (0.3 + 0.35 * throttle + 0.4 * (1 - exhaust)) * volume))
        else:
            e.setVolume(0)
        self.loops["rattle"].setVolume(min(1.0, (1 - exhaust) * 0.45 * volume) if running else 0)
        self.loops["crank"].setVolume(0.7 * volume if cranking else 0)
        self.loops["skid"].setVolume(0.35 * volume if skid else 0)

    def rain(self, amount):
        if self.ok:
            self.loops["rain"].setVolume(amount * 0.35)

    def silence(self):
        if self.ok:
            for n in ("engine", "rattle", "crank", "skid"):
                self.loops[n].setVolume(0)
