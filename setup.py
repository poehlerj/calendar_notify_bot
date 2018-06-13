#!/usr/bin/env python3

import re, os
from setuptools import setup

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    with open("__init__.py", "r") as file:
        version = re.search('^__version__\s*=\s*"(.*)"', file.read(), re.M).group(1)

    with open("README.md", "rb") as file:
        long_descr = file.read().decode("utf-8")

    if not os.path.exists("public_config.py"):
        with open("public_config.py", "wb+") as file:
            content = '''cal_url = ''\n
                        check_interval = 60\n
                        cal_file_name_new = 'calendar.ics.new'\n
                        cal_file_name = 'calendar.ics'\n
                        chat_ids_file_name = 'chat_ids.txt'\n
                        server_timezone = 'Europe/Berlin'\n'''
            file.write(content.encode("utf-8"))

    if not os.path.exists("private_config.py"):
        with open("private_config.py", "wb+") as file:
            content = '''telegram_token = ''\n'''
            file.write(content.encode("utf-8"))

    if not os.path.exists("logs"):
        os.makedirs("logs")

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
            'icalendar',
            'requests',
            'pytz',
            'PyYAML'
        ],
        version=version,
        description="",
        long_description=long_descr,
        author="Jonas Pöhler",
        url=""
    )
