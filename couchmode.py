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

FULLSCREEN = False

class CEC(threading.Thread):
    def run(self):
        self.buttons = set()
        self.proc = subprocess.Popen(
            'cec-client', stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )
        self.proc.stdin.write(b'as\n')
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

icon_sz = (256, 256)

def load(entry):
    icon_fn = entry.icon_fn
    if not icon_fn:
        return None
    fn = xdg.IconTheme.getIconPath(icon_fn, icon_sz[0])
    if not fn:
        return None
    if fn.endswith('.svg'):
        try:
            svg = Parser.parse_file(fn)
        except:
            return None
        rast = Rasterizer()
        imbuf = rast.rasterize(svg, *icon_sz)
        im = Image.frombytes('RGBA', icon_sz, imbuf)
        icon = pygame.image.fromstring(im.tobytes(), icon_sz, im.mode).convert_alpha()
        icon = pygame.transform.scale(icon, icon_sz)
        pass
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
    pygame.display.set_caption('Couch Mode')
    found = False
    pygame.init()
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
        # with open(os.path.join(appdir, path), 'r') as f:
        #     cfg = f.readlines()
        de = xdg.DesktopEntry.DesktopEntry()
        # with open(os.path.join(appdir, path), 'r') as f:
        try:
            de.parse(os.path.join(appdir, path))
        except xdg.Exceptions.ParsingError:
            continue
        name = de.getName()
        run = de.getExec()
        icon_fn = de.getIcon()
        fn = os.path.splitext(path)[0].lower()
        print(fn)
        
        apps[fn] = entry = Entry(
            name,
            icon_fn,
            run,
            de
        )

start()

with open('config.yaml', 'r') as cfg:
    cfg = yaml.safe_load(cfg)
    try:
        fn = cfg['background']
        background = Image.open(os.path.expanduser(fn))
        # background = pygame.image.load(os.path.expanduser(fn))
    except pygame.error:
        background = None
    if background:
        background = background.filter(ImageFilter.GaussianBlur(radius=10))
        background = pygame.image.fromstring(background.tobytes(), background.size, background.mode)
        background = background.convert()
    my_apps = cfg['apps']

for app in my_apps:
    try:
        load(apps[app])
    except KeyError:
        pass
        # pygame.quit()
        # raise

done = False
select = 0

dirty = True
border = 16
padding = ivec2(64, 64)
y_wrap = resolution[0] - icon_sz[0] - padding[0]*2
y_offset = y_wrap // icon_sz[0]
print(y_offset)

while not done:
    run = None

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
        pygame.quit()
        params = filter(lambda x: not x.startswith('%'), run.split())
        subprocess.check_call(params)
        screen = pygame.display.set_mode(resolution, pygame.FULLSCREEN if FULLSCREEN else 0)
        dirty = True
        continue
                
    if dirty:
        dirty = False
        # screen.fill(BLACK)
        screen.blit(background, (0,0))
        for i in range(0, 50):
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
            if select == i:
                pygame.draw.rect(screen, pygame.Color('gray'), (x,y,*icon_sz), 8)
                
        pygame.display.flip()
        dirty = False
    
    clock.tick(15)

cec.stop()
