"""Defines classes for working with shows and episodes."""

import enum


class ShowType(enum.Enum):
    """Key for show types."""

    UNKNOWN = 0
    TV = 1
    MOVIE = 2
    OVA = 3


def str_to_showtype(string):
    """Convert a show type string to int key."""

    if string is not None:
        string = string.lower()
        if string == "tv":
            return ShowType.TV
        if string == "movie":
            return ShowType.MOVIE
        if string == "ova":
            return ShowType.OVA
    return ShowType.UNKNOWN


def showtype_to_str(showtype):
    """Convert a showtype int to the string representation."""

    if showtype == 1:
        return "TV"
    elif showtype == 2:
        return "MOVIE"
    elif showtype == 3:
        return "OVA"

    return "UNKNOWN"


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
    ):
        self.media_id = media_id
        self.id_mal = id_mal
        self.name = name
        self.name_en = name_en
        self.more_names = more_names
        self.show_type = str_to_showtype(show_type).value
        self.has_source = has_source
        self.is_nsfw = is_nsfw
