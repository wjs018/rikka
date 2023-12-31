"""Defines classes for working with shows and episodes."""

import enum


class ShowType(enum.Enum):
    """Key for show types."""

    UNKNOWN = 0
    TV = 1
    TV_SHORT = 2
    MOVIE = 3
    SPECIAL = 4
    OVA = 5
    ONA = 6
    MUSIC = 7


def str_to_showtype(string):
    """Convert a show type string to int key."""

    if string is not None:
        string = string.lower()
        if string == "tv":
            return ShowType.TV
        if string == "tv_short":
            return ShowType.TV_SHORT
        if string == "movie":
            return ShowType.MOVIE
        if string == "special":
            return ShowType.SPECIAL
        if string == "ova":
            return ShowType.OVA
        if string == "ona":
            return ShowType.ONA
        if string == "music":
            return ShowType.MUSIC
    return ShowType.UNKNOWN


class DbEqMixin:
    """Define some helper functions for dealing with Show objects."""

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return self.id != other.id

    def __hash__(self):
        return hash(self.id)


class Show(DbEqMixin):
    """Class to handle Show objects."""

    def __init__(
        self,
        id,  # pylint: disable=W0622
        id_mal,
        name,
        name_en,
        show_type,
        has_source,
        is_nsfw,
        megathread,
        enabled,
    ):
        # Note: arguments are order-sensitive
        self.id = id
        self.id_mal = id_mal
        self.name = name
        self.name_en = name_en
        self.type = show_type
        self.has_source = has_source == 1
        self.is_nsfw = is_nsfw == 1
        self.megathread = megathread == 1
        self.enabled = enabled


class Episode:
    """Class to handle Episode objects."""

    def __init__(self, media_id, number, link=None):
        # Note: arguments are order-sensitive
        self.media_id = media_id
        self.number = number
        self.link = link

    def __str__(self):
        return "Show id: {}, Episode: {}, Link: {}".format(
            self.media_id, self.number, self.link
        )


class UpcomingEpisode:
    """Class to handle upcoming episodes."""

    def __init__(self, media_id, number, airing_time):
        # Note: arguments are order-sensitive
        self.media_id = media_id
        self.number = number
        self.airing_time = airing_time

    def __str__(self):
        return "Show id: {}, Episode: {}, Airing At {}".format(
            self.media_id, self.number, self.airing_time
        )


class UnprocessedShow:
    """Class used to define new shows."""

    def __init__(
        self,
        media_id,
        id_mal,
        name,
        name_en,
        more_names,
        show_type,
        has_source,
        is_nsfw,
        is_airing,
    ):
        self.media_id = media_id
        self.id_mal = id_mal
        self.name = name
        self.name_en = name_en
        self.more_names = more_names
        self.show_type = str_to_showtype(show_type).value
        self.has_source = has_source
        self.is_nsfw = is_nsfw
        self.is_airing = is_airing

    def __eq__(self, other):
        return self.media_id == other.media_id

    def __ne__(self, other):
        return self.media_id != other.media_id

    def __hash__(self):
        return hash(self.media_id)


class Megathread:
    """Class used to define a megathread."""

    def __init__(self, media_id, thread_num, post_url, num_episodes):
        self.media_id = media_id
        self.thread_num = thread_num
        self.post_url = post_url
        self.num_episodes = num_episodes

    def __str__(self):
        return "Megathread number {} for show id {}, containing {} episodes at link {}".format(
            self.thread_num, self.media_id, self.num_episodes, self.post_url
        )
