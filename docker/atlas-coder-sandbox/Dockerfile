# Atlas coder sandbox: a small Linux desktop that you view in the browser.
# Base image is old (Ubuntu 20.04) but it works. See README.md for the steps.
FROM dorowu/ubuntu-desktop-lxde-vnc:latest

# Package downloads can fail inside a build behind a proxy (seen 2026-11-12: "502 Bad Gateway" from Docker Desktop's
# proxy, once on focal-backports, which then made "apt-get update" return an error and skipped the whole install).
# So this one step:
#  1. removes the expired Google Chrome source (its key breaks "apt update");
#  2. reads packages from one fixed mirror, not the mirror:// list, and drops focal-backports (not needed);
#  3. turns off HTTP pipelining (many proxies answer it with 502) and retries each download;
#  4. tries the install up to 3 times and does NOT stop when "apt-get update" reports one failed repository;
#  5. NEVER fails the build. If the tools cannot be installed, the desktop still works and the file
#     /etc/atlas-tools-missing says so. Run "docker compose build --no-cache" later to try again.
RUN rm -f /etc/apt/sources.list.d/google-chrome.list \
 && ( sed -i 's|mirror://mirrors.ubuntu.com/mirrors.txt|http://archive.ubuntu.com/ubuntu|; /-backports/d' /etc/apt/sources.list || true ) \
 && ( ok=0; \
      for try in 1 2 3; do \
        apt-get -o Acquire::http::Pipeline-Depth=0 -o Acquire::Retries=5 update; \
        if apt-get -o Acquire::http::Pipeline-Depth=0 -o Acquire::Retries=5 install -y --no-install-recommends \
             git curl ca-certificates python3-pip build-essential ripgrep; then ok=1; break; fi; \
        sleep 5; \
      done; \
      if [ "$ok" != 1 ]; then echo "apt failed during the image build: git, python3-pip, ripgrep are NOT installed" > /etc/atlas-tools-missing; fi ) \
 ; apt-get clean ; rm -rf /var/lib/apt/lists/*

# Agents work in /workspace. Compose mounts a host folder here.
WORKDIR /workspace
