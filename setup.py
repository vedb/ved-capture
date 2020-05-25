from setuptools import setup, find_packages
from distutils.util import convert_path

requirements = [
    "click",
    "confuse",
    "blessed",
    "pupil_recording_interface",
]

main_ns = {}
ver_path = convert_path("ved_capture/_version.py")
with open(ver_path) as ver_file:
    exec(ver_file.read(), main_ns)

setup(
    name="ved-capture",
    version=main_ns["__version__"],
    packages=find_packages(),
    long_description=open("README.md").read(),
    entry_points="""
        [console_scripts]
        vedc=ved_capture.cli:vedc
    """,
    install_requires=requirements,
    include_package_data=True,
)
