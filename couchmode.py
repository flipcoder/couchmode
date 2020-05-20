#!/usr/bin/env python3

import sys, os
import subprocess
from glm import ivec2, vec3, vec4
import pygame
from dataclasses import dataclass
import xdg.DesktopEntry
import xdg.IconTheme
import random
from PIL import Image, ImageFilter
import threading
import yaml
import datetime
import gi
from collections import defaultdict

gi.require_version("Rsvg", "2.0")
from gi.repository import Rsvg as rsvg
import cairo
import math

BLACK = (0, 0, 0)
LIGHT_GRAY = pygame.Color("lightgray")
DARK_GRAY = pygame.Color("darkgray")
WHITE = (255, 255, 255)


class CEC(threading.Thread):
    def run(self):
        self.buttons = set()
        self.proc = subprocess.Popen(
            "cec-client", stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )
        while self.proc.poll() is None:
            line = self.proc.stdout.readline()
            if b"key pressed" in line:
                line = line[line.find(b"key pressed: ") + len("key pressed: ") :]
                line = line[: line.find(b" ")]
                # print(line)
                self.buttons.add(line)
            elif b"key released" in line:
                line = line[line.find(b"key released: ") + len("key released: ") :]
                line = line[: line.find(b" ")]
                # print(b'- ' + line)
                if line in self.buttons:
                    self.buttons.remove(line)

    def write(self, msg):
        self.proc.stdin.write(msg + "\n")

    def stop(self):
        try:
            self.proc.terminate()
        except:
            pass
        try:
            self.proc.stdin.close()
        except:
            pass


@dataclass
class Entry:
    name: str
    icon_fn: str
    run: str
    entry: xdg.DesktopEntry = None
    icon: any = None


class Homescreen:
    def __init__(self):
        with open("config.yaml", "r") as cfg:
            self.cfg = yaml.safe_load(cfg)

        self.icon_sz = ivec2(self.cfg.get("icon_size", 156))

        self.fullscreen = self.cfg.get("fullscreen", False)
        self.theme = self.cfg.get("theme", None)
        self.browser = self.cfg.get("browser", None)
        self.res = ivec2(*self.cfg.get("resolution", (1920, 1080)))

        self.cec = CEC()
        self.cec.start()

        self.appdirs = [
            "/usr/share/applications/",
            "~/.local/share/applications/",
        ]

        self.apps = {}

        for appdir in self.appdirs:
            appdir = os.path.expanduser(appdir)
            for path in os.listdir(appdir):
                de = xdg.DesktopEntry.DesktopEntry()
                try:
                    de.parse(os.path.join(appdir, path))
                except xdg.Exceptions.ParsingError:
                    continue
                name = de.getName()
                run = os.path.expanduser(de.getExec())
                icon_fn = de.getIcon()
                fn = os.path.splitext(path)[0].lower()
                # print(fn)

                self.apps[fn] = entry = Entry(name, icon_fn, run, de)

        found = False
        pygame.init()
        pygame.mouse.set_visible(False)
        pygame.display.set_caption("Couch Mode")
        # drivers = ['fbcon', 'directfb', 'svgalib']
        # for driver in drivers:
        #     if not os.getenv('SDL_VIDEODRIVER'):
        #         os.putenv('SDL_VIDEODRIVER', driver)
        #     try:
        #         pygame.init()
        #     except pygame.error:
        #         continue
        #     found = True
        #     break
        # if not found:
        #     pygame.quit()
        #     sys.exit(1)
        #     return None
        self.screen = pygame.display.set_mode(
            self.res, pygame.FULLSCREEN if self.fullscreen else 0
        )
        pygame.key.set_repeat(100, 100)
        # buf = pygame.Surface(self.res)
        # buf.fill((0,0,0))

        self.clock = pygame.time.Clock()

        try:
            fn = self.cfg["background"]
            self.background = Image.open(os.path.expanduser(fn))
            # self.background = pygame.image.load(os.path.expanduser(fn))
        except pygame.error:
            self.background = None
        if self.background:
            # self.background = self.background.resize((1920 + 64, 1080 + 64), Image.ANTIALIAS)
            self.background = self.background.filter(ImageFilter.GaussianBlur(radius=8))
            self.background = pygame.image.fromstring(
                self.background.tobytes(), self.background.size, self.background.mode
            )
            self.background = self.background.convert()

        # my_apps = list(apps.keys()) # all
        self.my_apps = self.cfg["apps"]

        self.tray = [
            "/usr/share/icons/Faenza/status/scalable/audio-volume-high.svg",
            "/usr/share/icons/Faenza/status/scalable/nm-signal-100.svg",
        ]
        self.tray_sz = ivec2(32)
        for i, fn in enumerate(self.tray):
            self.tray[i] = self.load_svg(fn, self.tray_sz)

        for i, app in enumerate(self.my_apps[:]):
            if type(app) is dict:
                key = list(app)[0]
                # print(key)
                # name = app[0]
                # info = app[1]
                # print('key',key)
                # print('app',app)
                app = app[key]
                # print(key)
                name = app.get("name", key)
                run = app.get("run", None)
                if run:
                    run = os.path.expanduser(run)
                else:
                    run = key
                web = app.get("web", None)
                if web:
                    run = self.browser + " " + web
                icon = app.get("icon", key)
                icon = os.path.expanduser(icon)
                self.apps[key] = entry = Entry(name, icon, run)
                # print('key', key)
                # print('entry', entry)
                self.my_apps[i] = key

        self.selection = 0

        self.dirty = True
        self.border = 64
        self.padding = ivec2(176, 96)
        self.y_wrap = self.res[0] - self.icon_sz[0] - self.padding[0] * 2
        # y_offset = y_wrap // (self.res[0] - self.icon_sz[0])
        self.y_offset = 5
        # print(y_offset)

        pygame.font.init()
        pygame.joystick.init()

        self.joysticks = [
            pygame.joystick.Joystick(x) for x in range(pygame.joystick.get_count())
        ]
        self.joy_axis = defaultdict(lambda: [0, 0])
        for joy in self.joysticks:
            joy.init()

        self.font = pygame.font.Font(pygame.font.get_default_font(), 24)

        w, h = self.icon_sz
        self.selector_sz = ivec2(w + self.border // 4, h + self.border // 4 + 42)
        self.selector = self.draw_selector(self.selector_sz)
        self.panel_sz = ivec2(self.res[0], 76)
        self.panel = self.draw_panel(self.panel_sz)
        # self.selector.set_alpha(128)
        # self.selector = pygame.Surface(icon_sz).convert_alpha()
        # self.selector.fill((0,0,0))

        for app in self.my_apps:
            try:
                # print('app2', app)
                self.load(self.apps[app])
            except ValueError as e:
                print(e)
                pass
            except KeyError as e:
                print(e)
                pass
                # pygame.quit()
                # raise

    def draw_selector(self, sz, col=(255, 255, 255)):
        w, h = sz
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        ctx = cairo.Context(surface)
        rad = 18.5
        deg = math.pi / 180
        x, y = 0, 0
        ctx.new_sub_path()
        ctx.arc(x + w - rad, y + rad, rad, -90 * deg, 0 * deg)
        ctx.arc(x + w - rad, y + h - rad, rad, 0 * deg, 90 * deg)
        ctx.arc(x + rad, y + h - rad, rad, 90 * deg, 180 * deg)
        ctx.arc(x + rad, y + rad, rad, 180 * deg, 270 * deg)
        ctx.close_path()
        ctx.set_source_rgba(*(vec4(vec3(col) / 255, 0.5)))
        ctx.fill_preserve()
        ctx.set_line_width(4.0)
        ctx.set_source_rgba(*(vec4(vec3(col) / 255, 0.8)))
        ctx.stroke()
        im = Image.frombuffer(
            "RGBA", (w, h), surface.get_data().tobytes(), "raw", "BGRA", 0, 0
        )
        buf = im.tobytes()
        return pygame.image.fromstring(buf, (w, h), "RGBA").convert_alpha()

    def draw_panel(self, sz, col=(0, 0, 0)):
        w, h = sz
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        ctx = cairo.Context(surface)
        rad = 18.5
        deg = math.pi / 180
        x, y = 0, 0
        ctx.new_sub_path()
        ctx.arc(x + w - rad, y + rad, rad, -90 * deg, 0 * deg)
        ctx.arc(x + w - rad, y + h - rad, rad, 0 * deg, 90 * deg)
        ctx.arc(x + rad, y + h - rad, rad, 90 * deg, 180 * deg)
        ctx.arc(x + rad, y + rad, rad, 180 * deg, 270 * deg)
        ctx.close_path()
        ctx.set_source_rgba(*(vec4(vec3(col) / 255, 0.5)))
        ctx.fill_preserve()
        # ctx.set_line_width(4.0)
        # ctx.set_source_rgba(*(vec4(vec3(col)/255, 0.8)))
        ctx.stroke()
        # scale = self.icon_sz[0]/dim[0]
        # ctx.scale(scale,scale)
        # svg.render_cairo(ctx)
        im = Image.frombuffer(
            "RGBA", (w, h), surface.get_data().tobytes(), "raw", "BGRA", 0, 0
        )
        buf = im.tobytes()
        return pygame.image.fromstring(buf, (w, h), "RGBA").convert_alpha()

    def load_svg(self, fn, sz):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, *sz)
        ctx = cairo.Context(surface)
        svg = rsvg.Handle.new_from_file(fn)
        dim = svg.get_dimensions()
        dim = ivec2(dim.width, dim.height)
        scale = sz[0] / dim[0]
        ctx.scale(scale, scale)
        svg.render_cairo(ctx)
        im = Image.frombuffer(
            "RGBA", tuple(sz), surface.get_data().tobytes(), "raw", "BGRA", 0, 0
        )
        buf = im.tobytes()
        return pygame.image.fromstring(buf, sz, "RGBA").convert_alpha()

    def load(self, entry):
        icon_fn = entry.icon_fn = os.path.expanduser(entry.icon_fn)
        if not icon_fn:
            return None
        try:
            fn = xdg.IconTheme.getIconPath(icon_fn, self.icon_sz[0], self.theme)
            # print(fn)
            if not fn:
                # fn = '/usr/share/icons/Faenza/apps/96/' + icon_fn + '.png'
                fn = "/usr/share/icons/Faenza/apps/scalable/" + icon_fn + ".svg"
                # fn = xdg.IconTheme.getIconPath(icon_fn, self.icon_sz[0], 'Adwaita')
        except TypeError:
            print("Type Error when loading", entry.name)
            return None
        # print('icon fn:', fn)
        if fn.endswith(".svg"):
            icon = self.load_svg(fn, self.icon_sz)
        elif fn.endswith(".png"):
            # icon = pygame.image.load(fn).convert_alpha()
            im = Image.open(fn)
            im = im.resize(tuple(self.icon_sz), Image.ANTIALIAS)
            buf = im.tobytes()
            icon = pygame.image.fromstring(buf, self.icon_sz, "RGBA").convert_alpha()
            # icon = pygame.transform.scale(icon, self.icon_sz)
        else:
            return None
        entry.icon = icon
        return icon

    def write(
        self,
        text,
        pos,
        color=(255, 255, 255),
        shadow=(0, 0, 0),
        shadow_offset=ivec2(1, 1),
        underline=False,
    ):
        pos = ivec2(*pos)

        if underline:
            self.font.set_underline(True)

        # shadow
        textbuf = self.font.render(text, True, shadow)
        self.screen.blit(
            textbuf,
            pos
            + ivec2(-textbuf.get_rect()[2] // 2 + shadow_offset[0], shadow_offset[1]),
        )

        # text
        textbuf = self.font.render(text, True, color)
        self.screen.blit(textbuf, pos + ivec2(-textbuf.get_rect()[2] // 2, 0))

        if underline:
            self.font.set_underline(False)

    def move(self, arrows):
        if arrows[0]:
            self.selection = max(0, self.selection - 1)
            self.dirty = True
        if arrows[1]:
            self.selection = min(len(self.my_apps) - 1, self.selection + 1)
            self.dirty = True
        if arrows[2]:
            self.selection = self.selection - min(self.selection, self.y_offset)
            self.dirty = True
        if arrows[3]:
            self.selection = min(self.selection + self.y_offset, len(self.my_apps) - 1)
            self.dirty = True

    def builtin(self, app):
        if app == "desktop":
            self.done = True
        else:
            print("Not yet implemented")
            self.done = True

    def run(self):
        self.done = False

        last_date = None

        while not self.done:
            self.run = None
            # date = subprocess.check_output(['date', '+%l:%M %p'])[:-1]
            date = datetime.datetime.now().strftime("%l:%M %p")
            if last_date != date:
                last_date = date
                self.dirty = True

            if self.cec.buttons:
                self.move(
                    (
                        b"left" in self.cec.buttons,
                        b"right" in self.cec.buttons,
                        b"up" in self.cec.buttons,
                        b"down" in self.cec.buttons,
                    )
                )

                for btn in self.cec.buttons:
                    if btn == b"back":
                        self.done = True
                        break
                    if btn == b"exit":
                        self.done = True
                        break
                    if btn == b"select":
                        self.run = self.apps[self.my_apps[select]].run
                        if self.run.startswith("@"):
                            self.builtin(self.run[1:])
                        break
                self.cec.buttons.clear()

            joy_move = defaultdict(lambda: False)
            if not self.run or not self.done:
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        self.done = True
                        break
                    elif ev.type == pygame.KEYDOWN:
                        self.move(
                            (
                                ev.key == pygame.K_LEFT,
                                ev.key == pygame.K_RIGHT,
                                ev.key == pygame.K_UP,
                                ev.key == pygame.K_DOWN,
                            )
                        )
                        if ev.key == pygame.K_ESCAPE:
                            self.done = True
                            break
                        if ev.key == pygame.K_RETURN:
                            self.run = self.apps[self.my_apps[self.selection]].run
                            if self.run.startswith("@"):
                                self.builtin(self.run[1:])
                            break
                    elif ev.type == pygame.JOYAXISMOTION:  # pygame.JOYHATMOTION):
                        threshold = 0.75
                        # axis = ev.axis % 2
                        axis = ev.axis
                        dr = axis % 2
                        if dr not in self.joy_axis:
                            self.joy_axis[axis] = 0
                            if abs(ev.value) < 0.1:
                                continue
                        if ev.value < -threshold:
                            if self.joy_axis[axis] != -1:
                                # print(axis, ev.value)
                                if dr == 0:
                                    self.move((1, 0, 0, 0))
                                else:
                                    self.move((0, 0, 1, 0))
                                self.joy_axis[axis] = -1
                        elif ev.value > threshold:
                            if self.joy_axis[axis] != 1:
                                # print(axis, ev.value)
                                if dr == 0:
                                    self.move((0, 1, 0, 0))
                                else:
                                    self.move((0, 0, 0, 1))
                                self.joy_axis[axis] = 1
                        else:
                            self.joy_axis[axis] = 0
                    elif ev.type == pygame.JOYBUTTONDOWN:
                        self.run = self.apps[self.my_apps[self.selection]].run
                        if self.run.startswith("@"):
                            self.builtin(self.run[1:])
                        break

            if self.done:
                break

            if self.run:
                pygame.mouse.set_visible(True)
                pygame.display.quit()
                params = filter(lambda x: not x.startswith("%"), self.run.split())
                try:
                    subprocess.check_call(params)
                except subprocess.CalledProcessError:
                    pass
                self.screen = pygame.display.set_mode(
                    self.res, pygame.FULLSCREEN if self.fullscreen else 0
                )
                pygame.mouse.set_visible(False)
                self.dirty = True
                continue

            if self.dirty:

                # self.screen.fill(BLACK)
                w, h = self.icon_sz

                self.screen.blit(self.background, (0, 0))

                self.screen.blit(self.panel, (0, -self.panel_sz[1] // 2))

                self.write(date, ivec2(self.res[0] / 2, 8))

                for i, icon in enumerate(self.tray[::-1]):
                    self.screen.blit(
                        icon,
                        (self.res[0] - ((i + 1) * self.tray_sz[0]) - i * 12 - 24, 2),
                    )

                for i in range(len(self.my_apps)):
                    if i < 0:
                        continue
                    try:
                        app = self.apps[self.my_apps[i]]
                    except KeyError:
                        break
                    except IndexError:
                        break

                    iconb = w + self.border * 2
                    xx = i * iconb
                    x = (xx % self.y_wrap) // iconb * iconb + self.padding[0]

                    # center
                    x += self.padding[0] // 4 + self.padding[0] // 2

                    y = (xx // self.y_wrap) * iconb + self.padding[0]

                    pad = 8
                    if self.selection == i:
                        self.screen.blit(
                            self.selector,
                            (
                                x + (w - self.selector_sz[0]) // 2,
                                y + (h - self.selector_sz[0]) // 2,
                                self.selector_sz[0],
                                self.selector_sz[1],
                            ),
                        )
                    if app.icon:
                        self.screen.blit(app.icon, (x, y))
                        name = app.name
                        self.write(name, ivec2(w // 2 + x, y + h + 16))

                pygame.display.flip()
                self.dirty = False

            self.clock.tick(15)

        self.cec.stop()


def prop(name, line):
    name += "="
    if line.startswith(name):
        return line[len(name) :]
    return None


if __name__ == "__main__":
    homescreen = Homescreen()
    homescreen.run()
