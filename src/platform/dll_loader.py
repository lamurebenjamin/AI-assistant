# -*- coding: utf-8 -*-
"""Gestionnaire de chargement des bibliothèques dynamiques natives et NVIDIA sous Windows."""

import os
import sys

_DLL_HANDLES = []


def setup_nvidia_dll_directories() -> list:
    """Rend accessibles les DLL NVIDIA installées dans l'environnement virtuel.
    
    Retourne la liste des handles afin de maintenir les répertoires actifs
    pendant toute la durée de vie du processus.
    """
    global _DLL_HANDLES
    if _DLL_HANDLES:
        return _DLL_HANDLES

    if sys.platform != "win32":
        return []

    nvidia_packages_dir = os.path.join(
        sys.prefix,
        "Lib",
        "site-packages",
        "nvidia",
    )

    nvidia_dll_dirs = (
        os.path.join(nvidia_packages_dir, "cuda_runtime", "bin"),
        os.path.join(nvidia_packages_dir, "cublas", "bin"),
        os.path.join(nvidia_packages_dir, "cufft", "bin"),
        os.path.join(nvidia_packages_dir, "cudnn", "bin"),
        os.path.join(nvidia_packages_dir, "cuda_nvrtc", "bin"),
    )

    available_dirs = [d for d in nvidia_dll_dirs if os.path.isdir(d)]

    for directory in available_dirs:
        try:
            handle = os.add_dll_directory(directory)
            _DLL_HANDLES.append(handle)
        except (AttributeError, OSError):
            pass

    if available_dirs:
        os.environ["PATH"] = os.pathsep.join(
            available_dirs + [os.environ.get("PATH", "")]
        )

    return _DLL_HANDLES


# Configuration automatique à l'import
setup_nvidia_dll_directories()
