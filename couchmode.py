#!/usr/bin/env python3

import sys, os
import subprocess
from glm import ivec2, vec2, vec3, vec4
with open(os.devnull, 'w') as devnull:
    # suppress pygame messages
    stdout = sys.stdout
    sys.stdout = devnull
    import pygame
    sys.stdout = stdout
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


        self.fullscreen = self.cfg.get("fullscreen", False)
        self.theme = self.cfg.get("theme", None)
        self.browser = self.cfg.get("browser", None)
        self.res = ivec2(*self.cfg.get("resolution", (1920, 1080)))
        
        self.icon_sz = ivec2(self.cfg.get("icon_size", ivec2(self.res[0]/12.3)))

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
        self.flags = pygame.DOUBLEBUF | \
            pygame.FULLSCREEN if self.fullscreen else 0
        self.screen = pygame.display.set_mode(
            self.res, self.flags
        )
        pygame.key.set_repeat(100, 100)
        self.page = 0
        self.pages = [pygame.Surface(self.res).convert_alpha()]
        for page in self.pages:
            page.fill((0,0,0,0))
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
        self.tray_sz = ivec2(self.res[0] // 60)
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
        self.border = ivec2(
            self.res[0] // 4,
            self.res[0] // 32
        )
        # self.padding = ivec2(176, 96)
        # self.padding = ivec2(self.res[0] // 12, self.res[1] // 20)
        # self.padding = ivec2(0,0)
        # self.y_wrap = self.res[0] - self.icon_sz[0] - self.padding[0] * 2 - self.border * 2
        self.grid = [4,3]
        # self.y_wrap = self.res[0] - self.icon_sz[0] - self.padding[0] // 2
        # grid = y_wrap // (self.res[0] - self.icon_sz[0])
        
        # print(grid)

        pygame.font.init()
        pygame.joystick.init()

        self.joysticks = [
            pygame.joystick.Joystick(x) for x in range(pygame.joystick.get_count())
        ]
        self.joy_axis = defaultdict(lambda: [0, 0])
        for joy in self.joysticks:
            joy.init()

        self.font = pygame.font.Font(pygame.font.get_default_font(), self.res[0] // 80)

        w, h = self.icon_sz
        self.selector_sz = ivec2(
            w + self.border.x // 6,
            h + self.border.y // 4 + self.border.y
        )
        # self.selector_sz = ivec2(self.selector_sz * (self.res[0]/1920))
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
        page,
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
        # page.set_alpha(None)
        
        page.blit(
            textbuf,
            pos
            + ivec2(-textbuf.get_rect()[2] // 2 + shadow_offset[0], shadow_offset[1]),
        )

        # text
        textbuf = self.font.render(text, True, color)
        page.blit(textbuf, pos + ivec2(-textbuf.get_rect()[2] // 2, 0))

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
            self.selection = self.selection - min(self.selection, self.grid[0])
            self.dirty = True
        if arrows[3]:
            self.selection = min(self.selection + self.grid[0], len(self.my_apps) - 1)
            self.dirty = True

    def builtin(self, app):
        if app == "desktop":
            self.done = True
        else:
            print("Not yet implemented")
            self.done = True

    def update(self, dt):
        self.dirty = True
        
        self.run = None
        # date = subprocess.check_output(['date', '+%l:%M %p'])[:-1]
        date = datetime.datetime.now().strftime("%l:%M %p")
        if self.last_date != date:
            self.last_date = date
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
                    return False
                if btn == b"exit":
                    self.done = True
                    return False
                if btn == b"select":
                    self.run = self.apps[self.my_apps[self.selection]].run
                    if self.run.startswith("@"):
                        self.builtin(self.run[1:])
                    return False
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
            return False

        if self.run:
            pygame.mouse.set_visible(True)
            pygame.display.quit()
            params = filter(lambda x: not x.startswith("%"), self.run.split())
            try:
                subprocess.check_call(params)
            except subprocess.CalledProcessError:
                pass
            self.screen = pygame.display.set_mode(
                self.res, self.flags
            )
            pygame.mouse.set_visible(False)
            self.dirty = True
            return False
        
        return True

    def render(self):
        if self.dirty:
            page = self.pages[self.page]

            # self.screen.fill(BLACK)
            w, h = self.icon_sz
            padding = self.res / 6
            
            self.screen.blit(self.background, (0, 0))

            page.fill((0,0,0,0))
            page.blit(self.panel, (0, -self.panel_sz[1] // 2))

            self.write(page, self.date, ivec2(self.res[0] / 2, 8))

            for i, icon in enumerate(self.tray[::-1]):
                page.blit(
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

                icon_entry_sz = ivec2(
                    self.selector_sz[0] + w + padding[0],
                    self.selector_sz[1] + h + padding[1]
                )

                screen_mid = ivec2(self.res[0] // 2, self.res[1] // 2)
                x_idx = (i % self.grid[0])
                y_idx = (i // self.grid[0])
                x_ofs = x_idx*icon_entry_sz.x // 2
                y_ofs = y_idx*icon_entry_sz.y // 2
                x = screen_mid.x + x_ofs
                y = screen_mid.y + y_ofs

                x -= self.grid[0] * icon_entry_sz.x//4 - padding[0]//4
                y -= self.grid[1] * icon_entry_sz.y//4

                y += self.panel_sz[1] // 2

                if self.selection == i:
                    page.blit(
                        self.selector,
                        (
                            x + (w - self.selector_sz[0]) // 2,
                            y + (h - self.selector_sz[1]) // 2 + self.border.y//2,
                            self.selector_sz[0],
                            self.selector_sz[1],
                        ),
                    )
                
                if app.icon:
                    ax, ay = x, y
                    # img = pygame.transform.scale(app.icon, ivec2(w - t, h - t))
                    page.blit(app.icon, (x, y))
                    name = app.name
                    self.write(page, name, ivec2(w // 2 + x, y + h + 16))
                
            # page.set_alpha(128)
            # page = pygame.transform.scale(page, ivec2(self.res[0] - t, self.res[1] - t))
            self.screen.blit(page, (0,0))
            pygame.display.flip()
            self.dirty = False

    def run(self):
        self.done = False
        self.last_date = None
        self.date = None
        
        self.t = self.dt = 0
        
        while not self.done:
            dt = self.clock.tick(60)
            self.t += dt * 0.1
            if not self.update(dt):
                break

            self.render()
                
        self.cec.stop()


def prop(name, line):
    name += "="
    if line.startswith(name):
        return line[len(name) :]
    return None


if __name__ == "__main__":
    homescreen = Homescreen()
    homescreen.run()
