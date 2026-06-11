#!/usr/bin/env python3
"""One-shot BARC Discord server setup via the Discord REST API.

Usage:
  DISCORD_TOKEN=<bot token> python3 setup_discord.py
Requires the bot to be in exactly one server (the fresh BARC server)
with Administrator permission.
"""

import os
import sys
import time
import json
import urllib.request

API = "https://discord.com/api/v10"
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    sys.exit("Set DISCORD_TOKEN env var")

HEADERS = {
    "Authorization": f"Bot {TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "BARCSetup (https://tjacobs.github.io/barc, 1.0)",
}

# Permission bits
VIEW = 1 << 10          # VIEW_CHANNEL
SEND = 1 << 11          # SEND_MESSAGES
CONNECT = 1 << 20


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(API + path, data=data, headers=HEADERS, method=method)
    while True:
        try:
            with urllib.request.urlopen(r) as resp:
                return json.loads(resp.read() or "{}")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry = json.loads(e.read()).get("retry_after", 1)
                time.sleep(retry + 0.2)
                continue
            print(f"ERROR {e.code} on {method} {path}: {e.read().decode()}")
            raise


def main():
    guilds = req("GET", "/users/@me/guilds")
    if len(guilds) != 1:
        sys.exit(f"Expected bot in exactly 1 server, found {len(guilds)}: "
                 f"{[g['name'] for g in guilds]}")
    gid = guilds[0]["id"]
    print(f"Setting up server: {guilds[0]['name']} ({gid})")

    everyone = gid  # @everyone role id == guild id

    # --- Roles ---
    builder = req("POST", f"/guilds/{gid}/roles",
                  {"name": "Builder", "color": 0xE8FF47, "hoist": True,
                   "mentionable": True})["id"]
    guest = req("POST", f"/guilds/{gid}/roles",
                {"name": "Guest", "color": 0x666666})["id"]
    print("Roles created: Builder, Guest")

    def overwrites(read_only_for_guests=False, announce=False):
        ow = []
        if read_only_for_guests:
            ow.append({"id": guest, "type": 0, "deny": str(SEND), "allow": "0"})
        if announce:
            ow.append({"id": everyone, "type": 0, "deny": str(SEND), "allow": "0"})
            ow.append({"id": builder, "type": 0, "allow": str(SEND), "deny": "0"})
        return ow

    structure = [
        ("WELCOME", [], [
            ("start-here", "Pinned rules, what BARC is, how to get the Builder role", {}),
            ("introductions", "Post your background, what you build, what you're working on", {}),
        ]),
        ("GENERAL", [], [
            ("announcements", "Events, news, admin", {"announce": True}),
            ("general-chat", "Open discussion", {"slowmode": 30}),
            ("off-topic", "Anything non-robotics", {}),
        ]),
        ("BUILDS", overwrites(read_only_for_guests=True), [
            ("show-and-tell", "Post your builds, work in progress, videos, photos", {}),
            ("build-help", "Ask technical questions, get unblocked", {}),
            ("build-logs", "Ongoing project threads, one per project", {}),
        ]),
        ("RESEARCH & TECH", overwrites(read_only_for_guests=True), [
            ("papers", "Share and discuss research papers", {}),
            ("hardware", "Interesting new components, sensors, actuators, compute", {}),
            ("software", "Simulators, python, perception, machine learning", {}),
            ("cool-finds", "Videos, tweets, blogs worth sharing", {}),
        ]),
        ("EVENTS", [], [
            ("meetups", "Logistics for Palo Alto in-person events", {}),
            ("event-ideas", "Propose topics, demos, formats", {}),
            ("past-events", "Photos and notes from previous meetups", {}),
        ]),
        ("COLLABORATION", [], [
            ("project-board", "Looking for collaborators, or have a project to staff", {}),
            ("research-collab", "Coordinating shared research or joint builds", {}),
        ]),
    ]

    for cat_name, cat_ow, channels in structure:
        cat = req("POST", f"/guilds/{gid}/channels",
                  {"name": cat_name, "type": 4, "permission_overwrites": cat_ow})
        for name, topic, opts in channels:
            body = {"name": name, "type": 0, "parent_id": cat["id"], "topic": topic}
            if opts.get("slowmode"):
                body["rate_limit_per_user"] = opts["slowmode"]
            if opts.get("announce"):
                body["permission_overwrites"] = overwrites(announce=True)
            req("POST", f"/guilds/{gid}/channels", body)
        print(f"Category created: {cat_name} ({len(channels)} channels)")

    voice_cat = req("POST", f"/guilds/{gid}/channels", {"name": "VOICE", "type": 4})
    for vname in ("General Hangout", "Event Night"):
        req("POST", f"/guilds/{gid}/channels",
            {"name": vname, "type": 2, "parent_id": voice_cat["id"]})
    print("Category created: VOICE (2 channels)")

    print("\nDone. Review the server, then delete the default #general/#text channels")
    print("Discord made on creation, and revoke this bot token.")


if __name__ == "__main__":
    main()
