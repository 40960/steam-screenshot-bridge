#!/usr/bin/env python3
"""Register an image into the Steam screenshot library for a given AppID.

Uses Steam's own libsteam_api.so via ISteamScreenshots::AddScreenshotToLibrary.
That is a different code path from the Steam Overlay screenshot capture, so it
still works for apps whose Steam metadata sets DisableOverlay -- the case this
whole project exists for.

Dimensions are passed in by the caller, so no image library is needed.

usage: steamshot.py <appid> <image> <width> <height> [thumbnail]
"""
import ctypes
import os
import sys
import time

# Steam ships this itself; no Steamworks SDK download required.
LIB_CANDIDATES = [
    "~/.local/share/Steam/steamrt64/libsteam_api.so",
    "~/.steam/steam/steamrt64/libsteam_api.so",
    "~/.steam/root/steamrt64/libsteam_api.so",
    "~/.var/app/com.valvesoftware.Steam/data/Steam/steamrt64/libsteam_api.so",
]


def find_lib():
    for candidate in LIB_CANDIDATES:
        path = os.path.expanduser(candidate)
        if os.path.exists(path):
            return path
    return None


def add(appid, path, width, height, thumb=None):
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return 2, "file not found: %s" % path

    lib_path = find_lib()
    if not lib_path:
        return 6, "libsteam_api.so not found (looked in: %s)" % ", ".join(LIB_CANDIDATES)

    # Steamworks reads these at init time.
    os.environ["SteamAppId"] = str(appid)
    os.environ["SteamGameId"] = str(appid)

    lib = ctypes.CDLL(lib_path)

    lib.SteamAPI_InitFlat.argtypes = [ctypes.c_char_p]
    lib.SteamAPI_InitFlat.restype = ctypes.c_int
    err = ctypes.create_string_buffer(1024)
    rc = lib.SteamAPI_InitFlat(err)
    if rc != 0:
        return 3, "SteamAPI_InitFlat failed rc=%d: %s" % (rc, err.value.decode(errors="replace"))

    lib.SteamAPI_SteamScreenshots_v003.restype = ctypes.c_void_p
    screenshots = lib.SteamAPI_SteamScreenshots_v003()
    if not screenshots:
        lib.SteamAPI_Shutdown()
        return 4, "could not get ISteamScreenshots"

    lib.SteamAPI_ISteamScreenshots_AddScreenshotToLibrary.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
    lib.SteamAPI_ISteamScreenshots_AddScreenshotToLibrary.restype = ctypes.c_uint32

    handle = lib.SteamAPI_ISteamScreenshots_AddScreenshotToLibrary(
        screenshots, path.encode(), thumb.encode() if thumb else None, int(width), int(height))

    # Let Steam process the resulting callback before we detach.
    for _ in range(16):
        lib.SteamAPI_RunCallbacks()
        time.sleep(0.05)

    lib.SteamAPI_Shutdown()

    if handle == 0xFFFFFFFF:  # INVALID_SCREENSHOT_HANDLE
        return 5, "AddScreenshotToLibrary returned INVALID handle"
    return 0, "OK handle=%d size=%sx%s" % (handle, width, height)


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("usage: steamshot.py <appid> <image> <width> <height> [thumbnail]")
        sys.exit(1)
    code, msg = add(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4],
                    sys.argv[5] if len(sys.argv) > 5 else None)
    print(msg)
    sys.exit(code)
