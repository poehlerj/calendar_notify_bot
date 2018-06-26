#!/usr/bin/env python3

import os
import re

from setuptools import setup

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    with open("calendar_bot/__init__.py", "r") as file:
        version = re.search('^__version__\s*=\s*"(.*)"', file.read(), re.M).group(1)

    with open("README.md", "rb") as file:
        long_descr = file.read().decode("utf-8")

    if not os.path.exists("calendar_bot/public_config.py"):
        with open("default_public_config.py", "rb") as input:
            with open("calendar_bot/public_config.py", "wb+") as file:
                file.write(input.read())

    if not os.path.exists("calendar_bot/private_config.py"):
        with open("calendar_bot/private_config.py", "w+") as file:
            content = '''telegram_token = ''\n'''
            file.write(content)

    if not os.path.exists("logs"):
        os.makedirs("logs")

    setup(
        name="calendar_bot",
        packages=['calendar_bot'],
        entry_points={
            "console_scripts": [
                "calendar_bot = calendar_bot:main"
            ]
        },
        include_package_data=True,
        install_requires=[
            'python-telegram-bot',
            'icalendar',
            'requests',
            'pytz',
            'PyYAML', 'jinja2'
        ],
        version=version,
        description="",
        long_description=long_descr,
        author="Jonas Pöhler",
        url=""
    )
