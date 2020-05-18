# couchmode
App Launcher for Raspberry PIs and Linux HTPCs

## Install

- Install `cec-utils` for your distribution

- Install dependencies:

```
sudo pip3 install -r requirements.txt
```

## Configure

- config.yaml:

```yaml
apps:
    - kodi
    - chromium-browser
background: '~/path/to/background.png'
```

## Run

```
./couchmode.py
```

