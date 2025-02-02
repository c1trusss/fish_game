import random
import os
import sys
from time import time
import sqlite3
from datetime import datetime

import pygame

from PyQt6 import uic
from PyQt6.QtWidgets import QApplication, QDialog


class Time:

    def __init__(self, seconds=0):

        """
        Класс для работы со временем
        :param seconds: время в секундах
        """

        self.time = seconds
        self.seconds = seconds % 60
        self.minutes = seconds // 60

    def __str__(self):

        return f"{self.minutes:02d}:{self.seconds:02d}"


class Database:

    def __init__(self):

        """
        Класс для работы с БД
        """

        self.connection = sqlite3.connect("fish.db")
        self.cursor = self.connection.cursor()

    def execute(self, sql: str, parameters=tuple()):

        """
        "Удобный" execute. Позволяет сохранить изменения, не вызывая команду commit.
        :param sql:
        :param parameters:
        :return:
        """

        result = self.cursor.execute(sql, parameters)
        self.connection.commit()
        return result

    def get_record(self, mode: str):

        sql = f"""SELECT time FROM {mode}"""

        times = [t[0] for t in self.execute(sql).fetchall() if t[0]]
        if times:
            record = min(times)
        else:
            record = 0

        return Time(record)


class Board:

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.board = [[-1] * width for _ in range(height)]

        self.left = 30
        self.top = 30
        self.cell_size = 50

    # настройка внешнего вида
    def set_view(self, left, top, cell_size):
        self.left = left
        self.top = top
        self.cell_size = cell_size

    def draw_cell(self, surface, x, y, fill=None):

        if isinstance(fill, str):
            hooks = pygame.sprite.Group()
            fishhook = pygame.sprite.Sprite()
            fishhook.image = pygame.transform.scale(load_image(f"{fill}.png"), (40, 40))
            fishhook.rect = fishhook.image.get_rect()

            xpos, ypos = self.left + x * self.cell_size + 5, self.top + y * self.cell_size + 5

            fishhook.rect.x = xpos
            fishhook.rect.y = ypos

            hooks.add(fishhook)

            hooks.draw(screen)

        elif fill:

            pygame.draw.rect(
                surface,
                fill,
                (
                    self.left + x * self.cell_size + 1,
                    self.top + y * self.cell_size + 1,
                    self.cell_size - 2,
                    self.cell_size - 2
                )
            )

        else:

            pygame.draw.rect(
                surface,
                (255, 255, 255),
                (
                    self.left + x * self.cell_size,
                    self.top + y * self.cell_size,
                    self.cell_size,
                    self.cell_size
                ),
                1
            )

    def render(self, surface):
        for y in range(self.height):
            for x in range(self.width):
                self.draw_cell(surface, x, y)
                cell = self.board[y][x]

                # Определение цвета
                color = (0, 0, 0)
                if cell == 10:
                    color = (255, 0, 0)
                elif cell == 2:
                    color = (0, 0, 255)

                self.draw_cell(surface, x, y, fill=color)

    def get_cell(self, mouse_pos):

        x = (mouse_pos[0] - self.left) // self.cell_size
        y = (mouse_pos[1] - self.top) // self.cell_size
        if 0 <= x < self.width and 0 <= y < self.height:
            return x, y
        else:
            return -1, -1

    def on_click(self, cell_coords):
        x, y = cell_coords

    def get_click(self, mouse_pos):
        cell = self.get_cell(mouse_pos)
        self.on_click(cell)


class FishGame(Board):

    def __init__(self, mines):
        super().__init__(10, 10)
        for i in range(mines):
            x, y = random.randrange(0, self.width), random.randrange(0, self.height)
            if self.board[y][x] == -1:
                self.board[y][x] = -10

    def mines_around(self, x, y):

        """
        Определение количества крючков вокруг конкретной клетки
        :param x: номер клетки по x
        :param y: номер клетки по y
        :return: количество крючков
        """

        neighbours = [(x - 1, y - 1),
                      (x, y - 1),
                      (x + 1, y - 1),
                      (x - 1, y),
                      (x + 1, y),
                      (x - 1, y + 1),
                      (x, y + 1),
                      (x + 1, y + 1)]
        cnt = 0
        for n in neighbours:
            try:
                if n[0] < 0 or n[1] < 0:
                    raise IndexError()
                if abs(self.board[n[1]][n[0]]) == 10:
                    cnt += 1
            except IndexError:
                pass

        return cnt

    def open_cell(self, x, y):

        neighbours = [(x - 1, y - 1),
                      (x, y - 1),
                      (x + 1, y - 1),
                      (x - 1, y),
                      (x + 1, y),
                      (x - 1, y + 1),
                      (x, y + 1),
                      (x + 1, y + 1)]

        mines = self.mines_around(x, y)
        if self.board[y][x] == -10:
            for xb in range(self.width):
                for yb in range(self.height):
                    if self.board[yb][xb] == -10:
                        self.board[yb][xb] = 10
        else:
            self.board[y][x] = mines

        if self.board[y][x] != 10:
            self.display_number(x, y)
        else:
            return

        # Рекурсивный поиск свободных клеток поблизости
        for n in neighbours:
            if mines == 0:
                try:
                    if n[0] < 0 or n[1] < 0:
                        raise IndexError()
                    if self.board[n[1]][n[0]] == -1 and self.board[n[1]][n[0]] != -10:
                        self.open_cell(n[0], n[1])
                except IndexError:
                    pass

    def win(self):
        return all(self.board[y][x] != -1 for x in range(self.width) for y in range(self.height))

    def lose(self):
        return any(self.board[y][x] == 10 for x in range(self.width) for y in range(self.height))

    def on_click(self, cell_coords):
        global fish_game, running, playing, time_start, clock, last_opened_cell
        if cell_coords and cell_coords != (-1, -1) and playing:
            super().on_click(cell_coords)
            self.open_cell(*cell_coords)
            last_opened_cell = cell_coords
        x, y = cell_coords
        if x == y == -1:
            x, y = pygame.mouse.get_pos()
            if new_game.rect.collidepoint(x, y):

                fish_game = FishGame(mines=mines)
                clock = pygame.time.Clock()

                running = True
                playing = True
                time_start = time()
            elif choose_level.rect.collidepoint(x, y):
                pass

    def render(self, surface, current_pos):
        xpos, ypos = current_pos
        for y in range(self.height):
            for x in range(self.width):
                self.draw_cell(surface, x, y)
                cell = self.board[y][x]
                match cell:
                    case 1:
                        color = (255, 255, 255)
                    case 2:
                        color = (0, 255, 0)
                    case _:
                        color = (189, 54, 61)
                if cell == 10 or (self.win() and cell == -10):
                    self.draw_cell(surface, x, y, fill="fishhook")
                elif cell != -1 and cell != -10:
                    self.draw_cell(surface, x, y)
                    if xpos == x and ypos == y:
                        self.draw_cell(surface, x, y, fill="fish")
                    self.display_number(x, y, color=color)
                else:
                    self.draw_cell(surface, x, y, fill=(76, 149, 217))

    def display_number(self, x, y, color=(100, 255, 100)):
        mines = self.mines_around(x, y)
        font = pygame.font.Font(None, 50)
        m_display = str(mines) if mines else ''
        text = font.render(m_display, True, color)
        screen.blit(text, (self.left + x * self.cell_size + 2, self.top + y * self.cell_size + 2))


class StartMenu(QDialog):

    def __init__(self):
        super().__init__()
        uic.loadUi("ui/start.ui", self)
        self.level = ""

        self.easyButton.clicked.connect(self.easy)
        self.mediumButton.clicked.connect(self.medium)
        self.hardButton.clicked.connect(self.hard)

    def easy(self):
        self.level = "easy"
        self.close()

    def medium(self):
        self.level = "medium"
        self.close()

    def hard(self):
        self.level = "hard"
        self.close()


def except_hook(cls, exception, traceback):
    sys.__excepthook__(cls, exception, traceback)


app = QApplication(sys.argv)
menu = StartMenu()
menu.show()
sys.excepthook = except_hook
app.exec()

# Ожидание выбора уровня
while not menu.level:
    pass


pygame.init()
size = width, height = 950, 600
screen = pygame.display.set_mode(size)

# Подбор кол-ва мин в зависимости от уровня
match menu.level:
    case "easy":
        mines = 5
    case "medium":
        mines = 10
    case "hard":
        mines = 15
    case _:
        mines = 0


def load_image(name, colorkey=None):
    fullname = os.path.join('data', name)

    if not os.path.isfile(fullname):
        print(f"Файл с изображением '{fullname}' не найден")
        sys.exit()
    image = pygame.image.load(fullname)
    image1 = pygame.transform.smoothscale(image, size)
    return image1


fish_game = FishGame(mines=mines)
clock = pygame.time.Clock()

running = True
playing = True
time_start = time()

# Отслеживание последнего хода для отображения рыбки
last_opened_cell = None, None

while running:

    # Время с начала игры
    time_now = int(time() - time_start)

    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

        if fish_game.win():
            msg = "Вы победили!!"
            playing = False

            # Запись рекорда в БД
            db = Database()
            db.execute(f"""INSERT INTO {menu.level}(time, date) VALUES (?, ?)""", (time_now, datetime.now()))

        if fish_game.lose():
            msg = "Вы проиграли!!!"
            playing = False

        if event.type == pygame.MOUSEBUTTONDOWN:
            fish_game.get_click(event.pos)

    # Загрузка фона
    image = load_image("sea.png")
    try:
        screen.blit(image, (0, 0))
    except pygame.error:
        print("Ошибка загрузки, перезапустите игру!")
        break

    border = not playing
    fish_game.render(screen, last_opened_cell)
    all_sprites = pygame.sprite.Group()
    if pygame.mouse.get_focused() or any(last_opened_cell):
        pygame.mouse.set_visible(False)
    fish = pygame.sprite.Sprite()
    fish.image = pygame.transform.scale(load_image("fish.png"), (50, 50))
    fish.rect = fish.image.get_rect()

    all_sprites.add(fish)
    x, y = pygame.mouse.get_pos()

    fish.rect.x = x
    fish.rect.y = y - 20

    other_sprites = pygame.sprite.Group()

    temp_fish = pygame.sprite.Sprite()
    temp_fish.image = pygame.transform.scale(load_image("temp_fish.png"), (50, 50))
    temp_fish.rect = temp_fish.image.get_rect()

    other_sprites.add(temp_fish)

    temp_fish.rect.x = x
    temp_fish.rect.y = y - 20

    # Секундомер
    if playing:
        font = pygame.font.Font(None, 100)
        minutes = time_now // 60
        seconds = time_now % 60
        time_text = font.render(f'{minutes:0>2}:{seconds:0>2}', True, "white")
        screen.blit(time_text, (600, 75))
    else:
        font = pygame.font.Font(None, 50)
        res_text = font.render(msg, True, "white")
        screen.blit(res_text, (600, 75))

    # Отображение рекорда
    db = Database()
    font = pygame.font.Font(None, 50)

    # Отображение рекорда
    record = db.get_record(menu.level)
    record_text = font.render(f"Рекорд: {record if record.time else 'нет'}", True, "white")
    screen.blit(record_text, (600, 180))

    # Отображение уровня игры
    level_text = font.render(f"Уровень: {menu.level.capitalize()}", True, "white")
    screen.blit(level_text, (600, 240))

    buttons = pygame.sprite.Group()

    # Кнопка новой игры
    new_game = pygame.sprite.Sprite()
    new_game.image = pygame.transform.scale(load_image("button.png"), (300, 100))
    new_game.rect = new_game.image.get_rect()
    new_game.mask = pygame.mask.from_surface(new_game.image)

    new_game.rect.x = 600
    new_game.rect.y = 430

    buttons.add(new_game)

    # Кнопка выбора уровня
    choose_level = pygame.sprite.Sprite()
    choose_level.image = pygame.transform.scale(load_image("choose_level.png"), (300, 100))
    choose_level.rect = choose_level.image.get_rect()
    choose_level.mask = pygame.mask.from_surface(choose_level.image)

    choose_level.rect.x = 600
    choose_level.rect.y = 320

    # buttons.add(choose_level)

    buttons.draw(screen)

    if pygame.sprite.spritecollideany(fish, buttons):
        pygame.mouse.set_visible(True)
    elif any(last_opened_cell):
        other_sprites.draw(screen)
    else:
        all_sprites.draw(screen)

    pygame.display.update()

    pygame.display.flip()
    clock.tick(144)


pygame.quit()
