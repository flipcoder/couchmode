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
gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg as rsvg
import cairo
import math

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
                # print(line)
                self.buttons.add(line)
            elif b'key released' in line:
                line = line[line.find(b'key released: ') + len('key released: '):]
                line = line[:line.find(b' ')]
                # print(b'- ' + line)
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

icon_sz = ivec2(cfg.get('icon_size', 156))

fullscreen = cfg.get('fullscreen', False)
theme = cfg.get('theme', None)
browser = cfg.get('browser', None)

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
LIGHT_GRAY = pygame.Color('lightgray')
DARK_GRAY = pygame.Color('darkgray')
WHITE = (255, 255, 255)

def draw_selector(sz, col=(255,255,255)):
    w, h = sz
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surface)
    rad = 18.5
    deg = math.pi / 180
    x,y = 0,0
    ctx.new_sub_path()
    ctx.arc(x + w - rad, y + rad, rad, -90 * deg, 0 * deg)
    ctx.arc(x + w - rad, y + h - rad, rad, 0 * deg, 90 * deg)
    ctx.arc(x + rad, y + h - rad, rad, 90 * deg, 180 * deg)
    ctx.arc(x + rad, y + rad, rad, 180 * deg, 270 * deg)
    ctx.close_path()
    ctx.set_source_rgba(*(vec4(vec3(col)/255, 0.5)))
    ctx.fill_preserve()
    ctx.set_line_width(4.0)
    ctx.set_source_rgba(*(vec4(vec3(col)/255, 0.8)))
    ctx.stroke()
    im = Image.frombuffer('RGBA', (w,h), surface.get_data().tobytes(), 'raw', 'BGRA', 0, 0)
    buf = im.tobytes()
    return pygame.image.fromstring(buf, (w,h), 'RGBA').convert_alpha()

def draw_panel(sz, col=(0,0,0)):
    w, h = sz
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surface)
    rad = 18.5
    deg = math.pi / 180
    x,y = 0,0
    ctx.new_sub_path()
    ctx.arc(x + w - rad, y + rad, rad, -90 * deg, 0 * deg)
    ctx.arc(x + w - rad, y + h - rad, rad, 0 * deg, 90 * deg)
    ctx.arc(x + rad, y + h - rad, rad, 90 * deg, 180 * deg)
    ctx.arc(x + rad, y + rad, rad, 180 * deg, 270 * deg)
    ctx.close_path()
    ctx.set_source_rgba(*(vec4(vec3(col)/255, 0.5)))
    ctx.fill_preserve()
    # ctx.set_line_width(4.0)
    # ctx.set_source_rgba(*(vec4(vec3(col)/255, 0.8)))
    ctx.stroke()
    # scale = icon_sz[0]/dim[0]
    # ctx.scale(scale,scale)
    # svg.render_cairo(ctx)
    im = Image.frombuffer('RGBA', (w,h), surface.get_data().tobytes(), 'raw', 'BGRA', 0, 0)
    buf = im.tobytes()
    return pygame.image.fromstring(buf, (w,h), 'RGBA').convert_alpha()

def load_svg(fn, sz):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, *sz)
    ctx = cairo.Context(surface)
    svg = rsvg.Handle.new_from_file(fn)
    dim = svg.get_dimensions()
    dim = ivec2(dim.width, dim.height)
    scale = sz[0]/dim[0]
    ctx.scale(scale,scale)
    svg.render_cairo(ctx)
    im = Image.frombuffer('RGBA', tuple(sz), surface.get_data().tobytes(), 'raw', 'BGRA', 0, 0)
    buf = im.tobytes()
    return pygame.image.fromstring(buf, sz, 'RGBA').convert_alpha()

def load(entry):
    icon_fn = entry.icon_fn = os.path.expanduser(entry.icon_fn)
    if not icon_fn:
        return None
    try:
        fn = xdg.IconTheme.getIconPath(icon_fn, icon_sz[0], theme)
        # print(fn)
        if not fn:
            # fn = '/usr/share/icons/Faenza/apps/96/' + icon_fn + '.png'
            fn = '/usr/share/icons/Faenza/apps/scalable/' + icon_fn + '.svg'
            # fn = xdg.IconTheme.getIconPath(icon_fn, icon_sz[0], 'Adwaita')
    except TypeError:
        print('Type Error when loading', entry.name)
        return None
    # print('icon fn:', fn)
    if fn.endswith('.svg'):
        icon = load_svg(fn, icon_sz)
    elif fn.endswith('.png'):
        # icon = pygame.image.load(fn).convert_alpha()
        im = Image.open(fn)
        im = im.resize(tuple(icon_sz), Image.ANTIALIAS)
        buf = im.tobytes()
        icon = pygame.image.fromstring(buf, icon_sz, 'RGBA').convert_alpha()
        # icon = pygame.transform.scale(icon, icon_sz)
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
    screen = pygame.display.set_mode(resolution, pygame.FULLSCREEN if fullscreen else 0)
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
    background = background.filter(ImageFilter.GaussianBlur(radius=8))
    background = pygame.image.fromstring(background.tobytes(), background.size, background.mode)
    background = background.convert()

# my_apps = list(apps.keys()) # all
my_apps = cfg['apps']

tray = [
    '/usr/share/icons/Faenza/status/scalable/audio-volume-high.svg',
    '/usr/share/icons/Faenza/status/scalable/nm-signal-100.svg',
]
tray_sz = ivec2(32)
for i, fn in enumerate(tray):
    tray[i] = load_svg(tray[i], tray_sz)

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
        run = app.get('run', None)
        if run:
            run = os.path.expanduser(run)
        else:
            run = key
        web = app.get('web', None)
        if web:
            run = browser + ' ' + web
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
# y_offset = y_wrap // (resolution[0] - icon_sz[0])
y_offset = 5
# print(y_offset)

pygame.font.init()
pygame.joystick.init()
joysticks = [pygame.joystick.Joystick(x) for x in range(pygame.joystick.get_count())]
joy_last_dir = 0
for joy in joysticks:
    joy.init()

font = pygame.font.Font(pygame.font.get_default_font(), 24)

selector_sz = ivec2(icon_sz[0] + border//4, icon_sz[1] + border//4 + 42)
selector = draw_selector(selector_sz)
panel_sz = ivec2(resolution[0], 76)
panel = draw_panel(panel_sz)
# selector.set_alpha(128)
# selector = pygame.Surface(icon_sz).convert_alpha()
# selector.fill((0,0,0))

def write(text, pos, color=(255, 255, 255), shadow=(0,0,0), shadow_offset=ivec2(1,1), underline=False):
    global screen, resolution
    pos = ivec2(*pos)
    
    if underline:
        font.set_underline(True)
    
    # shadow
    textbuf = font.render(text, True, shadow)
    screen.blit(textbuf, pos + ivec2(-textbuf.get_rect()[2]//2 + shadow_offset[0], shadow_offset[1]))
    
    # text
    textbuf = font.render(text, True, color)
    screen.blit(textbuf, pos + ivec2(-textbuf.get_rect()[2]//2, 0))
    
    if underline:
        font.set_underline(False)
    

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
                    if run == '@desktop':
                        done = True
                    break
            elif ev.type == pygame.JOYAXISMOTION:
                if ev.axis % 2 == 0:
                    if ev.value < -0.2:
                        if joy_last_dir != 1:
                            select = max(0, select - 1)
                            dirty = True
                            joy_last_dir = -1
                    if ev.value > 0.2:
                        if joy_last_dir != 1:
                            select = min(len(my_apps)-1, select + 1)
                            dirty = True
                            joy_last_dir = 1
                    else:
                        joy_last_dir = 0
                else:
                    pass
                    # if ev.value < -0.2:
                    #     select = select + min(len(my_apps)-1, y_offset)
                    #     dirty = True
                    # if ev.value > 0.2:
                    #     select = select - min(select, y_offset)
                    #     dirty = True
            elif ev.type == pygame.JOYBUTTONDOWN:
                run = apps[my_apps[select]].run
                if run == '@desktop':
                    done = True
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
        screen = pygame.display.set_mode(resolution, pygame.FULLSCREEN if fullscreen else 0)
        pygame.mouse.set_visible(False)
        dirty = True
        continue
                
    if dirty:
        
        # screen.fill(BLACK)
        w, h = icon_sz
        
        screen.blit(background, (0,0))
        
        screen.blit(panel, (0, -panel_sz[1]//2))
        
        write(date, ivec2(resolution[0]/2, 8))
        
        for i, icon in enumerate(tray[::-1]):
            screen.blit(icon, (resolution[0] - ((i+1) * tray_sz[0]) - i*12 - 24, 2))
        
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
            iconb = w + border * 2
            xx = i * iconb
            x = (xx % y_wrap) // iconb * iconb + padding[0]
            
            #center
            x += padding[0] // 4 + padding[0] // 2
            
            # print(y_offset)
            y = (xx // y_wrap) * iconb + padding[0]
            # ysz = i * icon_sz[1] + i * 2 * border
            # y = (xx // resolution[0]) * ysz
            # print(y)
            pad = 8
            if select ==  i:
                screen.blit(selector, (x + (w-selector_sz[0])//2, y + (h-selector_sz[0])//2,selector_sz[0],selector_sz[1]))
            if app.icon:
                screen.blit(app.icon, (x, y))
                name = app.name
                pad = max(len(name), pad)
                # print(pad)
                # if len(name) < 16:
                #     pad = 16 - len(name)
                #     name = ' ' * (pad//2) + name + ' ' * (pad//2)
                write(name, ivec2(w//2 + x, y + h + 16)) #, underline=(select == i))
            # if select == i:
            #     pad += 2
                # pygame.draw.aaline(screen, pygame.Color('white'), (x+2,y+h+8), (x+w, y+h+8))
                # pygame.draw.aaline(screen, pygame.Color('black'), (x+2,y+h+10), (x+w, y+h+10))
                # pygame.draw.aaline(screen, pygame.Color('white'), (x+2,y+h+48), (x+w, y+h+48))
                # pygame.draw.aaline(screen, pygame.Color('black'), (x+2,y+h+50), (x+w, y+h+50))
                # write(' '*16, ivec2(icon_sz[0]//2 + x, y + 16 * 2), BLACK, underline=True)
                # write(' '*16, ivec2(icon_sz[0]//2 + x, y + 16 * 2 + 2), WHITE, underline=True)
                # write('_'*pad, ivec2(w//2 + x, y + h - 12), LIGHT_GRAY, DARK_GRAY, shadow_offset=(0,1), underline=True)
                # write('_'*pad, ivec2(w//2 + x, y + h + 16 + 2), DARK_GRAY, LIGHT_GRAY, shadow_offset=(0,1), underline=True)
            # if select == i:
            #     pygame.draw.rect(screen, pygame.Color('black'), (x+2,y+2,*icon_sz), 8)
            #     pygame.draw.rect(screen, pygame.Color('darkgray'), (x,y,*icon_sz), 8)
                
        pygame.display.flip()
        dirty = False
    
    clock.tick(15)

cec.stop()

