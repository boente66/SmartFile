# app/system/system_identification.py

import platform
from pathlib import Path


class SystemIdentification:
    """
    Responsável por identificar o ambiente do sistema
    onde o SmartFlie está executando.
    """

    # -------------------------
    # Sistema operacional
    # -------------------------

    @staticmethod
    def get_os():
        return platform.system()

    @staticmethod
    def is_linux():
        return platform.system() == "Linux"

    @staticmethod
    def is_windows():
        return platform.system() == "Windows"

    @staticmethod
    def is_mac():
        return platform.system() == "Darwin"

    # -------------------------
    # Python
    # -------------------------

    @staticmethod
    def get_python_version():
        return platform.python_version()

    # -------------------------
    # Arquitetura
    # -------------------------

    @staticmethod
    def get_architecture():
        return platform.machine()

    # -------------------------
    # Diretórios padrão
    # -------------------------

    @staticmethod
    def get_home_directory():
        return Path.home()

    @staticmethod
    def get_documents_directory():
        return Path.home() / "Documents"

    @staticmethod
    def get_downloads_directory():
        return Path.home() / "Downloads"

    @staticmethod
    def get_temp_directory():
        if SystemIdentification.is_windows():
            return Path.home() / "AppData" / "Local" / "Temp"
        return Path("/tmp")

    # -------------------------
    # Scanner backend
    # -------------------------

    @staticmethod
    def get_scanner_backend():
        """
        Define backend ideal para scanner
        baseado no sistema operacional.
        """

        if SystemIdentification.is_linux():
            return "sane"

        if SystemIdentification.is_windows():
            return "wia"

        if SystemIdentification.is_mac():
            return "ica"

        return None

    # -------------------------
    # Informações completas
    # -------------------------

    @staticmethod
    def get_system_info():
        return {
            "os": SystemIdentification.get_os(),
            "python": SystemIdentification.get_python_version(),
            "architecture": SystemIdentification.get_architecture(),
            "scanner_backend": SystemIdentification.get_scanner_backend(),
            "documents": SystemIdentification.get_documents_directory(),
            "downloads": SystemIdentification.get_downloads_directory(),
            "temp": SystemIdentification.get_temp_directory(),
        }


    @staticmethod
    def get_scanner_backend():
       system = platform.system()

       if system == "Linux":
        return "sane"

       if system == "Windows":
        return "twain"

       if system == "Darwin":
        return "ica"

        return None