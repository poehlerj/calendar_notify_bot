#!/usr/bin/env python3

import os
import re

from babel.messages import frontend as babel
from setuptools import setup

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    with open("calendar_bot/__init__.py", "r") as file:
        version = re.search('^__version__\s*=\s*"(.*)"', file.read(), re.M).group(1)

    with open("README.md", "rb") as file:
        long_descr = file.read().decode("utf-8")

    if not os.path.exists("public_config.py"):
        with open("default_public_config.py", "rb") as input:
            with open("calendar_bot/public_config.py", "wb+") as file:
                file.write(input.read())

    if not os.path.exists("private_config.py"):
        with open("private_config.py", "wb+") as file:
            content = '''telegram_token = ''\n'''
            file.write(content.encode("utf-8"))

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
        cmdclass={'compile_catalog': babel.compile_catalog,
                  'extract_messages': babel.extract_messages,
                  'init_catalog': babel.init_catalog,
                  'update_catalog': babel.update_catalog},
        include_package_data=True,
        setup_requires=['babel'],
        install_requires=[
            'python-telegram-bot',
            'icalendar',
            'requests',
            'pytz',
            'PyYAML',
        ],
        version=version,
        description="",
        long_description=long_descr,
        author="Jonas Pöhler",
        url=""
    )
