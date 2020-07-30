""" ``ved_capture`` """
import pkg_resources

__version__ = pkg_resources.require("ved_capture")[0].version

APP_INFO = {"name": "ved-capture", "version": __version__}
