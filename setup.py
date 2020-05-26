from setuptools import setup, find_packages

requirements = [
    "click",
    "confuse",
    "blessed",
    "pupil_recording_interface",
]

setup(
    name="ved-capture",
    version="0.2.0",
    packages=find_packages(),
    long_description=open("README.md").read(),
    entry_points="""
        [console_scripts]
        vedc=ved_capture.cli:vedc
    """,
    install_requires=requirements,
    include_package_data=True,
)
