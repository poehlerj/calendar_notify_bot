#!/usr/bin/env python3

import re, os
from setuptools import setup

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    with open("__init__.py", "r") as file:
        version = re.search('^__version__\s*=\s*"(.*)"', file.read(), re.M).group(1)

    with open("README.md", "rb") as f:
        long_descr = f.read().decode("utf-8")

    setup(
        name="calendar_bot",
        packages=[],
        entry_points={
            "console_scripts": [
                "calendar_bot = calendar_bot:main"
            ]
        },
        include_package_data=True,
        install_requires=[
            'python-telegram-bot',
            'python-redmine',
            'icalendar',
            'requests', 'pytz'
        ],
        version=version,
        description="",
        long_description=long_descr,
        author="Jonas Pöhler",
        url=""
    )
