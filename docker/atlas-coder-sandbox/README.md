# Atlas coder sandbox (Docker)

Not tested in the cloud. The cloud session has no Docker. Test on your PC.
The start and stop logic (`src-tauri/src/sandbox.rs`) is tested with a fake `docker` program: 11 unit tests. A real Docker run is not tested.

## Start it (about 10 minutes the first time)

1. Open PowerShell in `F:\APP-DEV\projects\atlas-chat\docker\atlas-coder-sandbox`.
2. Make your settings file: `Copy-Item .env.example .env`
3. Open `.env`. Change the password. Save.
4. Build and start: `docker compose up -d --build`
5. Check state: `docker compose ps` (wait for `healthy`).
6. Open `http://127.0.0.1:6080/` in Firefox. Enter the password from `.env`.

## Show it inside Atlas

1. Open Atlas, go to the remote session panel.
2. Paste `http://127.0.0.1:6080/` in the noVNC field. Use `127.0.0.1`. Do not use `localhost`.
3. Click SAVE SESSION SETTINGS. The badge shows FRAME LOADED only if the port answers. Otherwise it shows NO ANSWER.
4. This needs the new Atlas build. Run `.\build-release.ps1` first.

## Atlas starts and stops it for you (new)

When Atlas opens, it runs `docker compose up -d` in this folder. When Atlas closes, it runs `docker compose stop`.

- There is only ever ONE container: `atlas-coder-sandbox-live`. Compose reuses it. Atlas never runs `docker run`.
- Atlas stops only what it started. A sandbox that was already running stays running when Atlas closes.
- Atlas never deletes a container. `docker compose stop` keeps the container and your `workspace` folder.
- Needs Docker Desktop. If Docker Desktop is still starting, Atlas tries again for 2 minutes.
- Password: if `.env` is missing, or still holds `change-me-first`, Atlas writes a random 8-character password into `.env`
  and writes it to the log. Only the first 8 characters count for VNC. A password you chose yourself is never changed.
- The first start builds the image (about 10 minutes). Later starts take seconds.
- The Operations panel opens `http://127.0.0.1:6080/` by default. Press REFRESH FRAME when the container is ready.
- Log: `F:\APP-DEV\data\Atlas Chat\logs\sandbox.log` (it says what Atlas did, or why it did nothing).
- Turn it off: `setx ATLAS_SANDBOX_AUTOSTART 0`, then restart Atlas. You can still use `docker compose up -d` by hand.
- If a container with the name `atlas-coder-sandbox-live` exists and Compose did not make it, Atlas changes nothing.
  The log shows the command to remove it: `docker rm -f atlas-coder-sandbox-live`.
- If another container uses port 6080 (for example the old `atlas-coder-sandbox`), the log says so. Stop that one first.

## What changed from your old command

| Old | New | Why |
|---|---|---|
| port open on all addresses | `127.0.0.1:6080` only | nobody on your network can see the desktop |
| no password | `VNC_PASSWORD` | the VNC server had no login |
| no limits | 2 CPU, 4 GB RAM, 512 processes | one agent cannot freeze your PC |
| 64 MB shared memory | 1 GB | Chrome stops crashing |
| 1920x1080 default | 1280x720 | less CPU for the picture stream |
| `:latest` image | your own image with tools | git, python, ripgrep are ready |

## Stop, reset, clean

- Stop: `docker compose down`
- See logs: `docker compose logs -f`
- Reset the desktop (your `workspace` folder stays): `docker compose down` then `docker compose up -d --build`

## Log lines you can ignore

- `CRIT Supervisor is running as root`: the base image needs root to start its services.
- `CRIT unix_http_server running without any HTTP authentication`: this socket is inside the container only.

## If the image has no tools

Why the build can fail: Docker Desktop copies your Windows proxy into builds, and apt then gets `502 Bad Gateway`.
The compose file switches the proxy off for the build only. A running container has no proxy and downloads fine.
Quick fix for a container that is already running: `docker exec atlas-coder-sandbox-live sh -c "apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates python3-pip build-essential ripgrep"` (lost when the container is recreated).


The build never fails on package downloads (a proxy can break them). The desktop then works, but `git`, `python3-pip` and
`ripgrep` are missing. Check: `docker exec atlas-coder-sandbox-live cat /etc/atlas-tools-missing`.
If that file exists, run `docker compose build --no-cache` and then `docker compose up -d` to try again.

## Known limits

- The base image `dorowu/ubuntu-desktop-lxde-vnc` has had no update since 2020. It is fine for a local sandbox. Do not expose it to the internet.
- After the first build, pin the base image. Run `docker inspect --format "{{index .RepoDigests 0}}" dorowu/ubuntu-desktop-lxde-vnc:latest` and put the result in `FROM`.
