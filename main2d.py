"""Старая 2D-версия игры (вид сверху, pygame).  Запуск: python3 main2d.py"""
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from game import Game

if __name__ == "__main__":
    Game().run()
    sys.exit()
