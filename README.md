# Couch Mode

App Launcher for Raspberry PIs and Linux HTPCs

![](https://i.imgur.com/PT7kB5a.png)

## Install

- Install the following packages for your distribution:
    - cec-utils
    - python3-gi-cairo
    - faenza-icon-theme

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

