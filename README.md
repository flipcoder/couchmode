# Couch Mode

Modern Homescreen for Raspberry PIs and Linux HTPCs.

This project is just a proof of concept, so don't expect much yet!

![](https://i.imgur.com/YM4rx0y.png)

## Install

- Install the following packages for your distribution:
    - python3
    - cec-utils
    - python3-gi-cairo
    - faenza-icon-theme

- Install dependencies:

```
sudo pip3 install -r requirements.txt
```

## Configure

### Basic

- config.yaml:

```yaml
apps:
    - kodi
    - chromium-browser
browser: vimb
background: '~/path/to/background.png'
```

### Advanced

- config.yaml:

```yaml
apps:
    - mail:
        name: 'Mail'
        icon: /usr/share/icons/Faenza/actions/scalable/mail-message-new.svg
        web: 'https://gmail.com'
    - files:
        name: 'Files'
        icon: '/usr/share/icons/Faenza/places/scalable/user-home.svg'
        run: 'pcmanfm'
    - vimb:
        icon: web-browser
        name: 'Web'
    - youtube:
        name: 'YouTube'
        web: 'https://www.youtube.com'
    - emulationstation:
        name: 'Emulation'
    - desktop:
        name: 'Desktop'
        icon: /usr/share/icons/Faenza/places/scalable/desktop.svg
        run: '@desktop'
    - kodi
    - steamlink
    - apps:
        name: 'Apps'
        run: '@apps'
        icon: system-software-installer
    - cheese:
        icon: /usr/share/icons/Faenza/devices/scalable/camera.svg
        name: Camera
    - weather:
        name: 'Weather'
        icon: /usr/share/icons/Faenza/status/scalable/weather-clear.svg
        run: '@weather'
    - shutdown:
        name: 'Shutdown'
        icon: /usr/share/icons/Faenza/actions/scalable/system-shutdown.svg
        run: 'poweroff'
browser: 'vimb'
background: '~/path/to/background.png'
fullscreen: true
```


## Run

```
./couchmode.py
```


## Progress

- [x] Proof of Concept
- [x] Keyboard Support
- [x] Gamepad Support
- [x] CEC Remote Support
- [ ] Joy2Key
- [ ] Multiple Pages
- [ ] Movable Icons
- [ ] Animations?
- [ ] System Apps

