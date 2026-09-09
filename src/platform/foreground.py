# -*- coding: utf-8 -*-
"""Détection et inspection des processus Windows au premier plan."""

import ctypes
import os
import sys

ADOBE_PROCESS_NAMES = {
    "acrord32.exe",   # Adobe Acrobat Reader (32 bits / historique)
    "acrobat.exe",    # Adobe Acrobat Pro / DC
    "rdrcef.exe",     # Sous-processus du moteur de rendu d'Acrobat Reader DC
}


def get_foreground_process_name() -> str:
    """Retourne le nom (minuscule) de l'exécutable de la fenêtre au premier plan."""
    if sys.platform != "win32":
        return ""
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
        )
        if not handle:
            return ""
        try:
            buffer_size = ctypes.c_ulong(260)
            buffer = ctypes.create_unicode_buffer(260)
            success = ctypes.windll.kernel32.QueryFullProcessImageNameW(
                handle, 0, buffer, ctypes.byref(buffer_size)
            )
            if success:
                return os.path.basename(buffer.value).lower()
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except (AttributeError, OSError, ValueError):
        pass
    return ""


def is_adobe_reader_foreground() -> bool:
    """Indique si la fenêtre active appartient à Adobe Reader/Acrobat."""
    return get_foreground_process_name() in ADOBE_PROCESS_NAMES
