"""Module to parse config file."""

import configparser
from collections import deque
from logging import warning

from data.models import str_to_showtype

# Variable used to aid in ratelimiting api calls
api_call_times = deque()
min_ns = 60 * 1000000000


class WhitespaceFriendlyConfigParser(configparser.ConfigParser):
    """Config file parser to deal with extra whitespace."""

    def get(self, section, option, *args, **kwargs):
        val = super().get(section, option, *args, **kwargs)
        return val.strip('"')


class Config:
    """Object containing values from parsed config file."""

    def __init__(self):
        # defined at runtime
        self.module = None

        # data section
        self.database = None

        # options section
        self.debug = False
        self.ratelimit = 60
        self.new_show_types = list()
        self.countries = list()
        self.submit = None
        self.days = None
        self.show_discovery = False
        self.min_upvotes = None
        self.min_comments = None

        # lemmy section
        self.l_community = None
        self.l_instance = None
        self.l_username = None
        self.l_password = None

        # post section
        self.post_title = None
        self.post_title_with_en = None
        self.post_body = None
        self.post_formats = dict()

        # megathread section
        self.megathread_episodes = None
        self.megathread_title = None
        self.megathread_title_with_en = None
        self.megathread_body = None
        self.megathread_comment = None


def from_file(file_path):
    """Parse a given config file and create a Config object."""

    if file_path.find(".") < 0:
        file_path += ".ini"

    parsed = WhitespaceFriendlyConfigParser()
    success = parsed.read(file_path, encoding="utf-8")
    if len(success) == 0:
        print("Failed to load config file")
        return None

    config = Config()

    if "data" in parsed:
        sec = parsed["data"]
        config.database = sec.get("database", None)

    if "lemmy" in parsed:
        sec = parsed["lemmy"]
        config.l_community = sec.get("community", None)
        config.l_instance = sec.get("instance", None)
        config.l_username = sec.get("username", None)
        config.l_password = sec.get("password", None)

    if "options" in parsed:
        sec = parsed["options"]
        config.ratelimit = sec.getint("ratelimit", 60)
        global api_call_times  # pylint: disable=global-statement
        api_call_times = deque(maxlen=config.ratelimit)
        config.debug = sec.getboolean("debug", False)
        config.submit = sec.getboolean("submit", True)
        config.days = sec.getint("days", 7)
        config.show_discovery = sec.getboolean("show_discovery", False)
        config.min_upvotes = sec.getint("min_upvotes", 1)
        config.min_comments = sec.getint("min_comments", 0)

        config.new_show_types.extend(
            map(
                lambda s: str_to_showtype(s.strip()),
                sec.get("new_show_types", "").split(" "),
            )
        )

        config.countries.extend(
            map(
                lambda s: s.strip(),
                sec.get("countries", "").split(" "),
            )
        )

    if "post" in parsed:
        sec = parsed["post"]
        config.post_title = sec.get("title", None)
        config.post_title_with_en = sec.get("title_with_en", None)
        config.post_body = sec.get("post_body", None)
        for key in sec:
            if key.startswith("format_") and len(key) > 7:
                config.post_formats[key[7:]] = sec[key]

    if "megathread" in parsed:
        sec = parsed["megathread"]
        config.megathread_episodes = sec.getint("megathread_episodes", 12)
        config.megathread_title = sec.get("megathread_title", None)
        config.megathread_title_with_en = sec.get("megathread_title_with_en", None)
        config.megathread_body = sec.get("megathread_body", None)
        config.megathread_comment = sec.get("megathread_comment", None)

    return config


def validate(config):
    """
    Validate the config object to make sure parameters are valid.

        Parameters:
            config      Config object representing a parsed config file

        Returns (only one):
            False       config is correct, no errors
            string      describes part of config that is incorrect
    """

    def is_bad_str(s):
        return s is None or len(s) == 0

    if is_bad_str(config.database):
        return "database missing"
    if config.ratelimit < 0:
        warning("Rate limit can't be negative, defaulting to 60")
        config.ratelimit = 60
    if is_bad_str(config.l_community):
        return "community missing"
    if is_bad_str(config.l_instance):
        return "lemmy instance missing"
    if is_bad_str(config.l_username):
        return "lemmy username missing"
    if is_bad_str(config.l_password):
        return "lemmy password missing"
    if is_bad_str(config.post_title):
        return "post title missing"
    if is_bad_str(config.post_body):
        return "post body missing"
    if is_bad_str(config.megathread_title):
        return "megathread title missing"
    if is_bad_str(config.megathread_body):
        return "megathread body missing"
    if is_bad_str(config.megathread_comment):
        return "megathread comment missing"
    return False
