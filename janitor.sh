#!/bin/zsh
# Dünner Wrapper (v.a. für launchd): launchd startet mit minimalem PATH, daher hier setzen,
# damit python3 / git / gh / xattr / osascript / swift gefunden werden.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "${0:A:h}" || exit 1
exec python3 janitor.py "$@" >> reports/run.log 2>&1
