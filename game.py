"""2D-версия (pygame): окно, сцены и звук поверх общей логики из state.py."""
import math

import pygame

from config import WIDTH, HEIGHT, FPS, TITLE, GAME_MIN_PER_SEC, WHITE
from state import GameState, WEEKDAYS_RU, RENT, OPEN_HOURS  # noqa: F401 (реэкспорт)
from sound import Sound
import ui


class Game(GameState):
    def __init__(self):
        pygame.init()
        self.sound = Sound()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.notifier = ui.Notifier()
        self.scenes = []
        self.running = True
        super().__init__()

    def notify(self, s, color=WHITE, t=5.0):
        self.notifier.push(s, color, t)

    def play_sound(self, name, vol=1.0):
        self.sound.play(name, vol)

    def engine_audio(self, inp):
        car = self.car
        self.sound.update_engine(car.running, car.rpm, inp.get("throttle", 0), car.cranking,
                                 car.c("exhaust") if car.has("exhaust") else 0.0,
                                 self._engine_volume(), skid=car.skidding and self.p.in_car)

    # ---------------------------------------------------------------- сцены
    def push(self, scene):
        self.scenes.append(scene)

    def pop(self):
        if self.scenes:
            self.scenes.pop()

    def replace(self, scene):
        self.scenes = [scene]

    def top(self):
        return self.scenes[-1] if self.scenes else None

    def run(self):
        from scenes_menu import TitleScene
        self.push(TitleScene(self))
        while self.running:
            dt = min(0.05, self.clock.tick(FPS) / 1000.0)
            self.t += dt
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                elif self.top():
                    self.top().handle(ev)
            sc = self.top()
            if sc is None:
                break
            if getattr(sc, "time_flows", False) and not self.game_over:
                self.advance(dt * GAME_MIN_PER_SEC)
                self.step_car(dt)
            else:
                self.sound.silence()
            sc.update(dt)
            if self.game_over and not getattr(sc, "is_game_over", False):
                from scenes_menu import GameOverScene
                self.replace(GameOverScene(self, self.game_over))
            self.notifier.update(dt)
            # отрисовка: нижние сцены для оверлеев
            stack = []
            for s in reversed(self.scenes):
                stack.append(s)
                if not getattr(s, "overlay", False):
                    break
            for s in reversed(stack):
                s.draw(self.screen)
            self.notifier.draw(self.screen)
            pygame.display.flip()
        pygame.quit()

    def _engine_volume(self):
        if self.p.in_car:
            return 1.0
        if type(self.top()).__name__ != "StreetScene" and type(self.top()).__name__ != "CarWorkScene":
            return 0.08
        d = math.hypot(self.p.x - self.car.x, self.p.y - self.car.y)
        return max(0.0, 0.7 - d / 80)
