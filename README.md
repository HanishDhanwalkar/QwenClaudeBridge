# Qwen Guest -> Claude Code local bridge

This project is a lightweight Windows prototype for routing Claude Code through a
Qwen guest session running in a dedicated Brave profile.

Design:
  Claude Code -> http://127.0.0.1:8787/v1/messages -> Python bridge
             -> dedicated Brave/Qwen tab -> Qwen web API

It deliberately avoids FastAPI, Flask, Selenium, and Playwright.

IMPORTANT
---------
This first package is a safe bootstrap/probe build. It can launch a dedicated
Brave profile, connect to its DevTools Protocol, find the Qwen tab, and expose
a local health/models endpoint. The exact Qwen streaming/event schema still
needs to be filled in from the Qwen DevTools EventStream you were asked to
capture. Do not put Qwen cookies/tokens into config files.

Requirements
------------
- Windows 10/11
- Python 3.10+ (3.11/3.12 recommended)
- Brave installed
- A Qwen guest session
- Claude Code, when we reach the adapter stage

Directory
---------
Put this folder somewhere permanent, for example:

    C:\QwenClaudeBridge

The script creates a separate browser profile automatically:

    C:\QwenClaudeBridge\brave-profile

This is NOT your normal Brave profile.

First run
---------
1. Open PowerShell.
2. cd C:\QwenClaudeBridge
3. Run:

       python server.py

4. The script should launch a dedicated Brave window.
5. In that window, open/log into the Qwen guest page if needed:
       https://chat.qwen.ai
6. Keep that Qwen tab open.
7. Check:
       http://127.0.0.1:8787/health

You can also use start.bat.

Brave
-----
The launcher searches common Brave installation paths. If it cannot find
Brave, set BRAVE_PATH in config.json.

Claude Code
-----------
Do NOT configure Claude Code against /v1/messages yet. The endpoint is
intentionally not enabled until the Qwen EventStream schema has been captured
and the translation layer is implemented.

After the adapter is implemented, the intended configuration will be:

    set ANTHROPIC_BASE_URL=http://127.0.0.1:8787
    set ANTHROPIC_AUTH_TOKEN=qwen-local
    claude

Security
--------
The server binds to 127.0.0.1 only. Do not change this to 0.0.0.0 unless you
understand the security implications.

Never paste cookies, Authorization headers, or session tokens into GitHub,
config.json, or chat.

Next step
---------
From Qwen DevTools:
Network -> completions?... -> EventStream

Send:
    Say exactly: HELLO123

Capture the EventStream (redact any secrets). That schema is required to
finish qwen_adapter.py and the Anthropic SSE translator.
