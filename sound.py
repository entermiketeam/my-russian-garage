"""Процедурные звуки: двигатель (набор петель по оборотам), стартер, удары и т.д."""
import math
import random

import pygame

try:
    import numpy as np
except ImportError:  # игра работает и без звука
    np = None

SR = 22050
RPM_LEVELS = [700, 1100, 1600, 2200, 2900, 3700, 4600, 5600, 6400]


class Sound:
    def __init__(self):
        self.ok = False
        self.engine_ch = []
        self.fx = {}
        if np is None:
            return
        try:
            pygame.mixer.init(SR, -16, 2, 512)
            pygame.mixer.set_num_channels(32)
        except pygame.error:
            return
        self.ok = True
        self.channels = pygame.mixer.get_init()[2]
        self.engine = [self._make(self._engine_wave(r)) for r in RPM_LEVELS]
        self.engine_ch = []
        for i, snd in enumerate(self.engine):
            ch = pygame.mixer.Channel(i)
            ch.play(snd, loops=-1)
            ch.set_volume(0)
            self.engine_ch.append(ch)
        self.rattle_ch = pygame.mixer.Channel(len(self.engine))
        self.rattle_ch.play(self._make(self._noise(1.0, 0.5, low=True)), loops=-1)
        self.rattle_ch.set_volume(0)
        self.crank_ch = pygame.mixer.Channel(len(self.engine) + 1)
        self.crank = self._make(self._crank_wave())
        self.rain_ch = pygame.mixer.Channel(len(self.engine) + 2)
        self.rain_ch.play(self._make(self._noise(2.0, 0.25)), loops=-1)
        self.rain_ch.set_volume(0)
        self.skid_ch = pygame.mixer.Channel(len(self.engine) + 3)
        self.skid = self._make(self._tone(0.5, 1250, 0.25, noise=0.4))
        self.fx = {
            "click": self._make(self._click()),
            "start": self._make(self._noise(0.25, 0.4, low=True)),
            "stall": self._make(self._decay(0.5, 60, 0.6)),
            "misfire": self._make(self._pop()),
            "crash": self._make(self._noise(0.5, 0.9, decay=True)),
            "grind": self._make(self._tone(0.4, 900, 0.3, noise=0.6)),
            "horn": self._make(self._horn()),
            "cash": self._make(self._cash()),
            "door": self._make(self._decay(0.2, 120, 0.5)),
            "weld": self._make(self._noise(1.2, 0.35)),
            "tool": self._make(self._clank()),
            "police": self._make(self._siren()),
            "blitz": self._make(self._tone(0.12, 2600, 0.3)),
        }

    # ----------------------------------------------------------- синтез
    def _make(self, wave):
        wave = np.clip(wave, -1, 1)
        a = (wave * 32000).astype(np.int16)
        if self.channels == 2:
            a = np.column_stack([a, a])
        return pygame.sndarray.make_sound(np.ascontiguousarray(a))

    def _engine_wave(self, rpm):
        f = rpm / 60.0 * 2.0  # частота вспышек 4-цилиндрового 4-тактного
        n_cycles = max(8, int(round(f * 0.6)))
        dur = n_cycles / f
        t = np.arange(int(SR * dur)) / SR
        w = np.zeros_like(t)
        for k, a in ((1, 1.0), (2, 0.5), (3, 0.35), (4, 0.18), (6, 0.08)):
            w += a * np.sin(2 * np.pi * k * f * t + k)
        # «полупорядок» — неровная работа старого мотора
        w += 0.35 * np.sin(np.pi * f * t)
        pulse = (np.sin(2 * np.pi * f * t) > 0.6).astype(float)
        w += 0.3 * pulse
        rng = np.random.default_rng(rpm)
        noise = rng.standard_normal(len(t))
        noise = np.convolve(noise, np.ones(6) / 6, mode="same")
        w += noise * (0.15 + rpm / 15000)
        w /= np.max(np.abs(w))
        return w * 0.6

    def _noise(self, dur, vol, low=False, decay=False):
        n = int(SR * dur)
        w = np.random.standard_normal(n)
        if low:
            w = np.convolve(w, np.ones(20) / 20, mode="same") * 3
        if decay:
            w *= np.exp(-np.linspace(0, 6, n))
        return w * vol

    def _tone(self, dur, f, vol, noise=0.0):
        t = np.arange(int(SR * dur)) / SR
        w = np.sign(np.sin(2 * np.pi * f * t)) * 0.3 + np.sin(2 * np.pi * f * 1.5 * t) * 0.3
        w += np.random.standard_normal(len(t)) * noise
        env = np.minimum(1, np.minimum(t * 40, (dur - t) * 20))
        return w * vol * env

    def _decay(self, dur, f, vol):
        t = np.arange(int(SR * dur)) / SR
        w = np.sin(2 * np.pi * f * t * (1 - t / dur * 0.5)) + np.random.standard_normal(len(t)) * 0.2
        return w * vol * np.exp(-t * 6)

    def _crank_wave(self):
        dur = 0.6
        t = np.arange(int(SR * dur)) / SR
        whirr = np.sin(2 * np.pi * 180 * t) * 0.3 + np.random.standard_normal(len(t)) * 0.1
        chug = (np.sin(2 * np.pi * 5 * t) > 0).astype(float) * 0.5 + 0.5
        return whirr * chug * 0.8

    def _click(self):
        t = np.arange(int(SR * 0.08)) / SR
        return np.sin(2 * np.pi * 800 * t) * np.exp(-t * 80) * 0.7

    def _pop(self):
        t = np.arange(int(SR * 0.12)) / SR
        return np.random.standard_normal(len(t)) * np.exp(-t * 40) * 0.8

    def _horn(self):
        t = np.arange(int(SR * 0.5)) / SR
        w = np.sign(np.sin(2 * np.pi * 330 * t)) * 0.3 + np.sign(np.sin(2 * np.pi * 415 * t)) * 0.3
        return w * np.minimum(1, (0.5 - t) * 30)

    def _cash(self):
        t = np.arange(int(SR * 0.3)) / SR
        return (np.sin(2 * np.pi * 1800 * t) + np.sin(2 * np.pi * 2400 * t)) * np.exp(-t * 12) * 0.3

    def _clank(self):
        t = np.arange(int(SR * 0.25)) / SR
        return (np.sin(2 * np.pi * 1300 * t) * 0.5 + np.sin(2 * np.pi * 2100 * t) * 0.3) * np.exp(-t * 25)

    def _siren(self):
        t = np.arange(int(SR * 1.6)) / SR
        f = np.where((t * 1.25) % 1 < 0.5, 440, 585)
        ph = np.cumsum(2 * np.pi * f / SR)
        return np.sign(np.sin(ph)) * 0.2

    # ----------------------------------------------------------- управление
    def play(self, name, vol=1.0):
        if not self.ok or name not in self.fx:
            return
        ch = pygame.mixer.find_channel()
        if ch:
            ch.set_volume(vol)
            ch.play(self.fx[name])

    def update_engine(self, running, rpm, throttle, cranking, exhaust_cond, volume=1.0, skid=False):
        if not self.ok:
            return
        vols = [0.0] * len(RPM_LEVELS)
        if running and rpm > 100:
            if rpm <= RPM_LEVELS[0]:
                vols[0] = 1.0
            elif rpm >= RPM_LEVELS[-1]:
                vols[-1] = 1.0
            else:
                for i in range(len(RPM_LEVELS) - 1):
                    a, b = RPM_LEVELS[i], RPM_LEVELS[i + 1]
                    if a <= rpm <= b:
                        k = (rpm - a) / (b - a)
                        vols[i] = 1 - k
                        vols[i + 1] = k
                        break
        loud = (0.35 + 0.35 * throttle + 0.5 * (1 - exhaust_cond)) * volume
        for ch, v in zip(self.engine_ch, vols):
            ch.set_volume(min(1.0, v * loud))
        self.rattle_ch.set_volume(min(1.0, (1 - exhaust_cond) * 0.5 * volume) if running else 0)
        if cranking:
            if not self.crank_ch.get_busy():
                self.crank_ch.play(self.crank, loops=-1)
            self.crank_ch.set_volume(0.7 * volume)
        else:
            self.crank_ch.stop()
        if skid:
            if not self.skid_ch.get_busy():
                self.skid_ch.play(self.skid, loops=-1)
            self.skid_ch.set_volume(0.35 * volume)
        else:
            self.skid_ch.stop()

    def set_rain(self, amount):
        if self.ok:
            self.rain_ch.set_volume(amount * 0.35)

    def silence(self):
        if self.ok:
            for ch in self.engine_ch:
                ch.set_volume(0)
            self.rattle_ch.set_volume(0)
            self.crank_ch.stop()
            self.skid_ch.stop()
