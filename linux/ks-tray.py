#!/usr/bin/env python3
# Steam Screenshot Bridge
# Copyright (C) 2026
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version. See the LICENSE file for details.

"""Steam Screenshot Bridge — tray app (SteamOS / KDE Plasma).

Linux counterpart of the Windows Win11SteamF10 tray helper: same idea, same
config-file shape. Owns the hotkey grabber (xbindkeys) so there is one thing to
start, stop and reconfigure.

Implements StatusNotifierItem + com.canonical.dbusmenu directly, which is what
Plasma speaks natively. Going through Gtk.StatusIcon/xembedsniproxy shows the
icon but loses the menu, so the D-Bus interfaces are done by hand here.

Only depends on what ships in the SteamOS base image: python-gobject,
xbindkeys, xdotool, xprop, ffmpeg.
"""
import os
import signal
import subprocess
import sys
import time

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, ".config", "ks-shot")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.ini")
XBK_CONFIG = os.path.join(CONFIG_DIR, "xbindkeysrc")
SHOT = os.environ.get("KS_SHOT") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "ks-shot")
LOG = os.path.join(HOME, ".local", "share", "ks-shot.log")
LOCK = "/tmp/ks-tray.lock"

DEFAULT_CONFIG = """\
; Steam Screenshot Bridge configuration
; Change the value after hotkey=, then pick "重新加载热键" in the tray menu.
;
; Examples:
;   hotkey=F10
;   hotkey=Control+Alt+s
;   hotkey=Scroll_Lock
;   hotkey=Shift+Print
;
; Modifier names:
;   Control, Alt, Shift, Mod4 (Super/Windows key)
;   Join them with + , e.g. Control+Alt+s
;
; Key names are X keysyms. Common ones:
;   F1 ... F12
;   a ... z          (lower case; use Shift+a for upper case)
;   0 ... 9
;   Escape, Tab, space, BackSpace, Return,
;   Insert, Delete, Home, End, Prior (PageUp), Next (PageDown),
;   Left, Right, Up, Down, Print, Pause, Scroll_Lock, Menu
;   KP_0 ... KP_9, KP_Add, KP_Subtract, KP_Multiply, KP_Divide
;
; Full list: run `xev` in a terminal and press the key you want.
;
; NOTE for SteamOS desktop mode (Wayland):
;   A bare key such as F10 is reliably caught when it comes from Steam Input
;   (i.e. a controller back button mapped to that key). A bare key pressed on a
;   physical keyboard may not reach this grabber, because kwin delivers most
;   plain keys straight to the focused window. A Control+Alt combination works
;   for both cases, so use one of those if you also want a keyboard shortcut.

hotkey=F10
"""

SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <method name="Activate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="ContextMenu">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="Scroll">
      <arg name="delta" type="i" direction="in"/>
      <arg name="orientation" type="s" direction="in"/>
    </method>
    <signal name="NewIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus"><arg name="status" type="s"/></signal>
  </interface>
</node>
"""

MENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg name="parentId" type="i" direction="in"/>
      <arg name="recursionDepth" type="i" direction="in"/>
      <arg name="propertyNames" type="as" direction="in"/>
      <arg name="revision" type="u" direction="out"/>
      <arg name="layout" type="(ia{sv}av)" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg name="ids" type="ai" direction="in"/>
      <arg name="propertyNames" type="as" direction="in"/>
      <arg name="properties" type="a(ia{sv})" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg name="id" type="i" direction="in"/>
      <arg name="name" type="s" direction="in"/>
      <arg name="value" type="v" direction="out"/>
    </method>
    <method name="Event">
      <arg name="id" type="i" direction="in"/>
      <arg name="eventId" type="s" direction="in"/>
      <arg name="data" type="v" direction="in"/>
      <arg name="timestamp" type="u" direction="in"/>
    </method>
    <method name="AboutToShow">
      <arg name="id" type="i" direction="in"/>
      <arg name="needUpdate" type="b" direction="out"/>
    </method>
    <signal name="LayoutUpdated">
      <arg name="revision" type="u"/>
      <arg name="parent" type="i"/>
    </signal>
  </interface>
</node>
"""


def log(msg):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f:
            f.write("%s [tray] %s\n" % (time.strftime("%F %T"), msg))
    except Exception:
        pass


def read_hotkeys():
    """Every hotkey= line is honoured, so several keys can trigger a shot."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w") as f:
            f.write(DEFAULT_CONFIG)
    keys = []
    try:
        for line in open(CONFIG_PATH):
            line = line.strip()
            if not line or line[0] in ";#":
                continue
            if line.lower().startswith("hotkey="):
                value = line.split("=", 1)[1].strip()
                if value and value not in keys:
                    keys.append(value)
    except Exception as e:
        log("WARN unreadable config, using F10: %s" % e)
    return keys or ["F10"]


def session_env():
    env = dict(os.environ)
    env.setdefault("DISPLAY", ":0")
    env.pop("GDK_BACKEND", None)
    if "XAUTHORITY" not in env:
        try:
            out = subprocess.check_output(["pgrep", "-a", "kwin_wayland"], text=True)
            for token in out.split():
                if token.startswith("/run/user/") and "xauth" in token:
                    env["XAUTHORITY"] = token
                    break
        except Exception:
            pass
    return env


class Bridge:
    """Reflects and controls xbindkeys.service (the standalone hotkey grabber).

    The tray deliberately does NOT run its own xbindkeys: two grabbers fight
    over the same key and only one wins.
    """

    UNIT = "xbindkeys.service"
    XBK_RC = os.path.join(HOME, ".xbindkeysrc")

    def __init__(self):
        self.hotkeys = read_hotkeys()

    @property
    def hotkey(self):
        return ", ".join(self.hotkeys)

    def write_config(self):
        with open(self.XBK_RC, "w") as f:
            for key in self.hotkeys:
                f.write('"%s"\n  %s\n\n' % (SHOT, key))

    def systemctl(self, *args):
        try:
            return subprocess.run(["systemctl", "--user", *args],
                                  capture_output=True, text=True, timeout=10)
        except Exception as e:
            log("systemctl %s failed: %s" % (" ".join(args), e))
            return None

    def running(self):
        r = self.systemctl("is-active", self.UNIT)
        return bool(r) and r.stdout.strip() == "active"

    def start(self):
        self.write_config()
        r = self.systemctl("restart", self.UNIT)
        ok = bool(r) and r.returncode == 0
        log("xbindkeys.service restart -> %s (%s)" % ("ok" if ok else "fail", self.hotkey))
        return ok

    def stop(self):
        """The grabber is a service of its own; leave it running on tray exit."""
        return

    def reload(self):
        self.hotkeys = read_hotkeys()
        return self.start()


class Tray:
    # menu item ids
    HEADER, SEP1, SHOOT, CONFIG, RELOAD, LOGVIEW, SEP2, QUIT = range(1, 9)

    def __init__(self):
        self.bridge = Bridge()
        self.revision = 1

        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.sni_info = Gio.DBusNodeInfo.new_for_xml(SNI_XML).interfaces[0]
        self.menu_info = Gio.DBusNodeInfo.new_for_xml(MENU_XML).interfaces[0]

        self.bus.register_object("/StatusNotifierItem", self.sni_info,
                                 self.sni_method, self.sni_get_property, None)
        self.bus.register_object("/MenuBar", self.menu_info,
                                 self.menu_method, self.menu_get_property, None)

        # our unique bus name is what the watcher wants
        Gio.bus_own_name(Gio.BusType.SESSION, "org.kde.StatusNotifierItem.ks-shot",
                         Gio.BusNameOwnerFlags.NONE, None, self.on_name_acquired, None)

        GLib.timeout_add_seconds(10, self.watchdog)

    # --- registration ---------------------------------------------------
    def on_name_acquired(self, connection, name):
        try:
            connection.call_sync(
                "org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher",
                "org.kde.StatusNotifierWatcher", "RegisterStatusNotifierItem",
                GLib.Variant("(s)", (connection.get_unique_name(),)),
                None, Gio.DBusCallFlags.NONE, 3000, None)
            log("registered with StatusNotifierWatcher as %s" % connection.get_unique_name())
        except Exception as e:
            log("FAIL registering with watcher: %s" % e)

    # --- StatusNotifierItem ---------------------------------------------
    def state_text(self):
        return "运行中" if self.bridge.running() else "已停止"

    def sni_get_property(self, conn, sender, path, iface, prop):
        if prop == "Category":
            return GLib.Variant("s", "ApplicationStatus")
        if prop == "Id":
            return GLib.Variant("s", "ks-shot")
        if prop == "Title":
            return GLib.Variant("s", "Steam 截图桥")
        if prop == "Status":
            return GLib.Variant("s", "Active")
        if prop == "IconName":
            return GLib.Variant("s", "camera-photo")
        if prop == "ItemIsMenu":
            return GLib.Variant("b", True)
        if prop == "Menu":
            return GLib.Variant("o", "/MenuBar")
        if prop == "ToolTip":
            return GLib.Variant("(sa(iiay)ss)",
                                ("camera-photo", [], "Steam 截图桥",
                                 "%s（热键 %s）" % (self.state_text(), self.bridge.hotkey)))
        return None

    def sni_method(self, conn, sender, path, iface, method, params, invocation):
        # ItemIsMenu=True means Plasma opens the menu itself; nothing to do here.
        invocation.return_value(None)

    # --- dbusmenu --------------------------------------------------------
    def items(self):
        return [
            (self.HEADER, {"label": "Steam 截图桥 — %s (%s)" % (self.state_text(), self.bridge.hotkey),
                           "enabled": False}),
            (self.SEP1, {"type": "separator"}),
            (self.SHOOT, {"label": "立即截图"}),
            (self.CONFIG, {"label": "打开配置"}),
            (self.RELOAD, {"label": "重新加载热键"}),
            (self.LOGVIEW, {"label": "查看日志"}),
            (self.SEP2, {"type": "separator"}),
            (self.QUIT, {"label": "退出"}),
        ]

    @staticmethod
    def make_item(item_id, props, children):
        """Build a dbusmenu (ia{sv}av) item.

        Built with VariantBuilder rather than a format string: PyGObject
        re-parses format strings recursively and chokes on already-built
        child variants.
        """
        builder = GLib.VariantBuilder(GLib.VariantType("av"))
        for child in children:
            builder.add_value(GLib.Variant.new_variant(child))
        return GLib.Variant.new_tuple(
            GLib.Variant("i", item_id),
            GLib.Variant("a{sv}", props),
            builder.end())

    @staticmethod
    def props_variant(props):
        out = {}
        for k, v in props.items():
            out[k] = GLib.Variant("b", v) if isinstance(v, bool) else GLib.Variant("s", v)
        return out

    def menu_get_property(self, conn, sender, path, iface, prop):
        if prop == "Version":
            return GLib.Variant("u", 3)
        if prop == "Status":
            return GLib.Variant("s", "normal")
        if prop == "TextDirection":
            return GLib.Variant("s", "ltr")
        if prop == "IconThemePath":
            return GLib.Variant("as", [])
        return None

    def menu_method(self, conn, sender, path, iface, method, params, invocation):
        if method == "GetLayout":
            children = GLib.VariantBuilder(GLib.VariantType("av"))
            for item_id, props in self.items():
                child = self.make_item(item_id, self.props_variant(props), [])
                children.add_value(GLib.Variant.new_variant(child))
            root = GLib.Variant.new_tuple(
                GLib.Variant("i", 0),
                GLib.Variant("a{sv}", {"children-display": GLib.Variant("s", "submenu")}),
                children.end())
            invocation.return_value(
                GLib.Variant.new_tuple(GLib.Variant("u", self.revision), root))

        elif method == "GetGroupProperties":
            result = [(item_id, self.props_variant(props)) for item_id, props in self.items()]
            invocation.return_value(GLib.Variant("(a(ia{sv}))", (result,)))

        elif method == "GetProperty":
            item_id, name = params.unpack()
            value = dict(self.items()).get(item_id, {}).get(name, "")
            variant = GLib.Variant("b", value) if isinstance(value, bool) else GLib.Variant("s", value)
            invocation.return_value(GLib.Variant("(v)", (variant,)))

        elif method == "Event":
            item_id, event_id = params.unpack()[0], params.unpack()[1]
            if event_id == "clicked":
                self.on_click(item_id)
            invocation.return_value(None)

        elif method == "AboutToShow":
            invocation.return_value(GLib.Variant("(b)", (False,)))

        else:
            invocation.return_value(None)

    # --- actions ---------------------------------------------------------
    def spawn(self, argv):
        subprocess.Popen(argv, env=session_env(),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def notify(self, title, body):
        self.spawn(["notify-send", "-a", "Steam Screenshot", "-i", "camera-photo",
                    "-t", "2000", title, body])

    def on_click(self, item_id):
        if item_id == self.SHOOT:
            self.spawn([SHOT])
        elif item_id == self.CONFIG:
            self.spawn(["xdg-open", CONFIG_PATH])
        elif item_id == self.RELOAD:
            ok = self.bridge.reload()
            self.menu_changed()
            self.notify("Steam 截图桥",
                        ("热键已重新加载：%s" % self.bridge.hotkey) if ok else "热键加载失败，见日志")
        elif item_id == self.LOGVIEW:
            self.spawn(["xdg-open", LOG])
        elif item_id == self.QUIT:
            log("exit requested from tray")
            self.bridge.stop()
            LOOP.quit()

    def menu_changed(self):
        self.revision += 1
        try:
            self.bus.emit_signal(None, "/MenuBar", "com.canonical.dbusmenu",
                                 "LayoutUpdated", GLib.Variant("(ui)", (self.revision, 0)))
            self.bus.emit_signal(None, "/StatusNotifierItem", "org.kde.StatusNotifierItem",
                                 "NewToolTip", None)
        except Exception:
            pass

    def watchdog(self):
        """Only refresh the label; systemd already restarts the unit itself."""
        self.menu_changed()
        return True


LOOP = GLib.MainLoop()


def main():
    lock = open(LOCK, "w")
    try:
        import fcntl
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        print("already running")
        return 0

    tray = Tray()
    for sig in (signal.SIGINT, signal.SIGTERM):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig,
                             lambda: (tray.bridge.stop(), LOOP.quit(), False)[2])
    log("tray started (hotkey=%s)" % tray.bridge.hotkey)
    LOOP.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
