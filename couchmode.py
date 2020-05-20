#!/usr/bin/env python3

import sys, os
import subprocess
from glm import ivec2
import pygame
from dataclasses import dataclass
import xdg.DesktopEntry
import xdg.IconTheme
import random
from svg import Parser, Rasterizer, SVG
from PIL import Image, ImageFilter
import threading
import yaml
import datetime
import gi
gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg as rsvg
import cairo
import array

FULLSCREEN = False

class CEC(threading.Thread):
    def run(self):
        self.buttons = set()
        self.proc = subprocess.Popen(
            'cec-client', stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )
        # self.proc.stdin.write(b'as\n')
        while self.proc.poll() is None:
            line = self.proc.stdout.readline()
            if b'key pressed' in line:
                line = line[line.find(b'key pressed: ') + len('key pressed: '):]
                line = line[:line.find(b' ')]
                print(line)
                self.buttons.add(line)
            elif b'key released' in line:
                line = line[line.find(b'key released: ') + len('key released: '):]
                line = line[:line.find(b' ')]
                print(b'- ' + line)
                if line in self.buttons:
                    self.buttons.remove(line)
    
    def write(self, msg):
        self.proc.stdin.write(msg+'\n')
    
    def stop(self):
        try:
            self.proc.terminate()
        except:
            pass
        try:
            self.proc.stdin.close()
        except:
            pass

with open('config.yaml', 'r') as cfg:
    cfg = yaml.safe_load(cfg)

if 'icon_size' in cfg:
    icon_sz = ivec2(cfg['icon_size'])
else:
    icon_sz = ivec2(156)

theme = cfg.get('theme', None)

cec = CEC()
cec.start()

appdirs = [
    '/usr/share/applications/',
    '~/.local/share/applications/',
]

@dataclass
class Entry:
    name: str
    icon_fn: str
    run: str
    entry: xdg.DesktopEntry = None
    icon: any = None

apps = {}

BLACK = (0,0,0)

def load(entry):
    icon_fn = entry.icon_fn = os.path.expanduser(entry.icon_fn)
    if not icon_fn:
        return None
    try:
        fn = xdg.IconTheme.getIconPath(icon_fn, icon_sz[0], theme)
        print(fn)
        if not fn:
            # fn = '/usr/share/icons/Faenza/apps/96/' + icon_fn + '.png'
            fn = '/usr/share/icons/Faenza/apps/scalable/' + icon_fn + '.svg'
            # fn = xdg.IconTheme.getIconPath(icon_fn, icon_sz[0], 'Adwaita')
    except TypeError:
        print('Type Error when loading', entry.name)
        return None
    # print('icon fn:', fn)
    if fn.endswith('.svg'):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, *icon_sz)
        ctx = cairo.Context(surface)
        svg = rsvg.Handle.new_from_file(fn)
        dim = svg.get_dimensions()
        dim = ivec2(dim.width, dim.height)
        scale = icon_sz[0]/dim[0]
        ctx.scale(scale,scale)
        svg.render_cairo(ctx)
        im = Image.frombuffer('RGBA', tuple(icon_sz), surface.get_data().tobytes(), 'raw', 'BGRA', 0, 0)
        buf = im.tobytes()
        icon = pygame.image.fromstring(buf, icon_sz, 'RGBA').convert_alpha()
    elif fn.endswith('.png'):
        icon = pygame.image.load(fn).convert_alpha()
        icon = pygame.transform.scale(icon, icon_sz)
    else:
        return None
    entry.icon = icon
    return icon

def prop(name, line):
    name += '='
    if line.startswith(name):
        return line[len(name):]
    return None

def start():
    global resolution, screen, buf, clock, my_apps, apps

    resolution = ivec2(1920, 1080)
    found = False
    pygame.init()
    pygame.mouse.set_visible(False)
    pygame.display.set_caption('Couch Mode')
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
    screen = pygame.display.set_mode(resolution, pygame.FULLSCREEN if FULLSCREEN else 0)
    pygame.key.set_repeat(100, 100)
    # buf = pygame.Surface(resolution)
    # buf.fill((0,0,0))

    clock = pygame.time.Clock()

for appdir in appdirs:
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
        
        apps[fn] = entry = Entry(
            name,
            icon_fn,
            run,
            de
        )

start()

try:
    fn = cfg['background']
    background = Image.open(os.path.expanduser(fn))
    # background = pygame.image.load(os.path.expanduser(fn))
except pygame.error:
    background = None
if background:
    # background = background.resize((1920 + 64, 1080 + 64), Image.ANTIALIAS)
    background = background.filter(ImageFilter.GaussianBlur(radius=10))
    background = pygame.image.fromstring(background.tobytes(), background.size, background.mode)
    background = background.convert()

# my_apps = list(apps.keys()) # all
my_apps = cfg['apps']

for i, app in enumerate(my_apps[:]):
    if type(app) is dict:
        key = list(app)[0]
        # print(key)
        # name = app[0]
        # info = app[1]
        # print('key',key)
        # print('app',app)
        app = app[key]
        # print(key)
        name = app.get('name', key)
        run = os.path.expanduser(app.get('run', key))
        if not run:
            web = app.get('web', None)
            if web:
                run = web + ' ' + run
        icon = app.get('icon', key)
        icon = os.path.expanduser(icon)
        apps[key] = entry = Entry(name, icon, run)
        # print('key', key)
        # print('entry', entry)
        my_apps[i] = key

for app in my_apps:
    try:
        # print('app2', app)
        load(apps[app])
    except ValueError as e:
        print(e)
        pass
    except KeyError as e:
        print(e)
        pass
        # pygame.quit()
        # raise

done = False
select = 0

dirty = True
border = 64
padding = ivec2(176, 96)
y_wrap = resolution[0] - icon_sz[0] - padding[0]*2
y_offset = y_wrap // (resolution[0] - icon_sz[0])
# print(y_offset)

pygame.font.init()
font = pygame.font.Font(pygame.font.get_default_font(), 24)

def write(text, pos, color=(255, 255, 255)):
    global screen, resolution
    pos = ivec2(*pos)
    
    # shadow
    textbuf = font.render(text, True, (0,0,0))
    screen.blit(textbuf, pos + ivec2(-textbuf.get_rect()[2]//2 + 2, 2))
    
    # text
    textbuf = font.render(text, True, color)
    screen.blit(textbuf, pos + ivec2(-textbuf.get_rect()[2]//2, 0))
    

last_date = None

while not done:
    run = None
    # date = subprocess.check_output(['date', '+%l:%M %p'])[:-1]
    date = datetime.datetime.now().strftime('%l:%M %p')
    if last_date != date:
        last_date = date
        dirty = True

    for btn in cec.buttons:
        if btn == b'left':
            select = max(0, select - 1)
            dirty = True
        if btn == b'right':
            select = min(len(my_apps)-1, select + 1)
            dirty = True
        if btn == b'down':
            select = select + min(len(my_apps)-1, y_offset)
            dirty = True
        if btn == b'up':
            select = select - min(select, y_offset)
            dirty = True
        if btn == b'back':
            done = True
            break
        if btn == b'exit':
            done = True
            break
        if btn == b'select':
            run = apps[my_apps[select]].run
            break

    cec.buttons.clear()
    
    if not run or not done:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                done = True
                break
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_LEFT:
                    select = max(0, select - 1)
                    dirty = True
                if ev.key == pygame.K_RIGHT:
                    select = min(len(my_apps)-1, select + 1)
                    dirty = True
                if ev.key == pygame.K_DOWN:
                    select = select + min(len(my_apps)-1, y_offset)
                    dirty = True
                if ev.key == pygame.K_UP:
                    select = select - min(select, y_offset)
                    dirty = True
                if ev.key == pygame.K_ESCAPE:
                    done = True
                    break
                if ev.key == pygame.K_RETURN:
                    run = apps[my_apps[select]].run
                    break
    if done:
        break
    
    if run:
        pygame.mouse.set_visible(True)
        pygame.display.quit()
        params = filter(lambda x: not x.startswith('%'), run.split())
        try:
            subprocess.check_call(params)
        except subprocess.CalledProcessError:
            pass
        screen = pygame.display.set_mode(resolution, pygame.FULLSCREEN if FULLSCREEN else 0)
        pygame.mouse.set_visible(False)
        dirty = True
        continue
                
    if dirty:
        # screen.fill(BLACK)
        screen.blit(background, (0,0))
        write(date, ivec2(resolution[0]/2, 16))
        
        for i in range(len(my_apps)):
            if i < 0:
                continue
            try:
                app = apps[my_apps[i]]
            except KeyError:
                break
            except IndexError:
                break
            # y_wrap = resolution[0] - icon_sz[0] - padding[0]*2
            iconb = icon_sz[0] + border * 2
            xx = i * iconb
            x = (xx % y_wrap) // iconb * iconb + padding[0]
            # print(y_offset)
            y = (xx // y_wrap) * iconb + padding[0]
            # ysz = i * icon_sz[1] + i * 2 * border
            # y = (xx // resolution[0]) * ysz
            # print(y)
            if app.icon:
                screen.blit(app.icon, (x, y))
                write(app.name, ivec2(icon_sz[0]//2 + x, y + icon_sz[1] + 16))
            if select == i:
                pygame.draw.rect(screen, pygame.Color('black'), (x+2,y+2,*icon_sz), 8)
                pygame.draw.rect(screen, pygame.Color('darkgray'), (x,y,*icon_sz), 8)
                
        pygame.display.flip()
        dirty = False
    
    clock.tick(15)

cec.stop()

