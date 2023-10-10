"""
Module for interacting with the sqlite database used by rikka.
"""

import sqlite3
import re

from functools import wraps
from logging import error, exception, debug
from typing import Optional, List
from unidecode import unidecode

from .models import ShowType, Show, UnprocessedShow, Episode, UpcomingEpisode


def open_database(the_database):
    """Opens the sqlite file and enforces foreign keys."""

    try:
        db = sqlite3.connect(the_database)
        db.execute("PRAGMA foreign_keys=ON")
    except:
        error("Failed to open database, {}".format(the_database))
        return None
    return DatabaseDatabase(db)


def db_error(f):
    """Handle database errors and log them."""

    @wraps(f)
    def protected(*args, **kwargs):
        try:
            f(*args, **kwargs)
            return True
        except:  # pylint: disable=bare-except
            exception("Database exception thrown")
            return False

    return protected


def db_error_default(default_value):
    """Handle database errors and log them."""

    value = default_value

    def decorate(f):
        @wraps(f)
        def protected(*args, **kwargs):
            nonlocal value
            try:
                return f(*args, **kwargs)
            except:  # pylint: disable=bare-except
                exception("Database exception thrown")
                return value

        return protected

    return decorate


def _collate_alphanum(str1, str2):
    """Collation definition used by the sqlite database."""

    str1 = _alphanum_convert(str1)
    str2 = _alphanum_convert(str2)

    if str1 == str2:
        return 0
    elif str1 < str2:
        return -1
    else:
        return 1


_alphanum_regex = re.compile("[^a-zA-Z0-9]+")
_romanization_o = re.compile("\bwo\b")


def _alphanum_convert(s):
    """Handle some romanization quirks."""

    # Characters to words
    s = s.replace("&", "and")
    # Japanese romanization differences
    s = _romanization_o.sub("o", s)
    s = s.replace("uu", "u")
    s = s.replace("wo", "o")

    s = _alphanum_regex.sub("", s)
    s = s.lower()
    return unidecode(s)


class DatabaseDatabase:
    """Class to manage database interactions for rikka."""

    def __init__(self, db):
        self._db = db
        self.q = db.cursor()

        # Set up collations
        self._db.create_collation("alphanum", _collate_alphanum)

    def save(self):
        """Commit changes to the db."""

        self._db.commit()

    def rollback(self):
        """Roll back pending changes to the db."""

        self._db.rollback()

    def setup_tables(self):
        """Creates the tables and schema used by rikka."""

        self.q.execute(
            """CREATE TABLE IF NOT EXISTS ShowTypes (
            id		INTEGER NOT NULL PRIMARY KEY UNIQUE,
            key		TEXT NOT NULL
        )"""
        )
        self.q.executemany(
            "INSERT OR IGNORE INTO ShowTypes (id, key) VALUES (?, ?)",
            [(t.value, t.name.lower()) for t in ShowType],
        )

        self.q.execute(
            """CREATE TABLE IF NOT EXISTS Shows (
            id		    INTEGER NOT NULL PRIMARY KEY UNIQUE,
            id_mal      INTEGER,
            name		TEXT NOT NULL,
            name_en		TEXT,
            type		INTEGER NOT NULL,
            has_source	INTEGER NOT NULL DEFAULT 0,
            is_nsfw		INTEGER NOT NULL DEFAULT 0,
            enabled		INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(type) REFERENCES ShowTypes(id)
        )"""
        )

        self.q.execute(
            """CREATE TABLE IF NOT EXISTS Aliases (
            id		    INTEGER NOT NULL,
            alias		TEXT NOT NULL,
            FOREIGN KEY(id) REFERENCES Shows(id) ON DELETE CASCADE,
            UNIQUE(id, alias) ON CONFLICT IGNORE
        )"""
        )

        self.q.execute(
            """CREATE TABLE IF NOT EXISTS Episodes (
            id  		INTEGER NOT NULL,
            episode		INTEGER NOT NULL,
            post_url	TEXT,
            UNIQUE(id, episode) ON CONFLICT REPLACE,
            FOREIGN KEY(id) REFERENCES Shows(id) ON DELETE CASCADE
        )"""
        )

        self.q.execute(
            """CREATE TABLE IF NOT EXISTS UpcomingEpisodes (
            id              INTEGER NOT NULL,
            episode         INTEGER NOT NULL,
            airing_time     INTEGER NOT NULL,
            UNIQUE(id, episode) ON CONFLICT REPLACE,
            FOREIGN KEY(id) REFERENCES Shows(id) ON DELETE CASCADE
        )"""
        )

        self._db.commit()

    # Shows

    @db_error_default(list())
    def get_aliases(self, show: Show) -> [str]:
        """Return list of aliases for a given Show object."""

        self.q.execute("SELECT alias FROM Aliases where id = ?", (show.id,))
        return [s for s, in self.q.fetchall()]

    @db_error_default(list())
    def get_shows(self, enabled="enabled") -> [Show]:
        """
        Query the database for list of Show objects.

            Parameters:
                enabled         "all", "enabled", or "disabled" only gets the shows with the
                                selected status from the database

            Returns:
                shows           List of Show objects
        """

        debug("Getting shows from database")

        shows = list()

        if enabled == "all":
            self.q.execute(
                "SELECT id, id_mal, name, name_en, type, has_source, is_nsfw, enabled FROM Shows"
            )
        else:
            if enabled == "enabled":
                enabled = 1
            elif enabled == "disabled":
                enabled = 0
            else:
                error("enabled parameter not set correctly")

            self.q.execute(
                "SELECT id, id_mal, name, name_en, type, has_source, is_nsfw, enabled FROM Shows \
                WHERE enabled = ?",
                (enabled,),
            )

        for show in self.q.fetchall():
            show = Show(*show)
            show.aliases = self.get_aliases(show)
            shows.append(show)

        return shows

    @db_error_default(None)
    def get_show(self, id=None) -> Optional[Show]:  # pylint: disable=W0622
        """Query the database and return the Show object from given id."""

        debug("Getting show from database")

        # Get show
        if id is None:
            error("Show ID not provided to get_show")
            return None
        self.q.execute(
            "SELECT id, id_mal, name, name_en, type, has_source, is_nsfw, enabled FROM Shows \
            WHERE id = ?",
            (id,),
        )
        show = self.q.fetchone()
        if show is None:
            return None
        show = Show(*show)
        show.aliases = self.get_aliases(show)
        return show

    @db_error_default(None)
    def get_show_by_name(self, name) -> Optional[Show]:
        """Query the database and return the Show object from given name."""

        debug("Getting show from database")

        self.q.execute(
            "SELECT id, name, name_en, type, has_source, is_nsfw, enabled, delayed FROM Shows \
            WHERE name = ?",
            (name,),
        )
        show = self.q.fetchone()
        if show is None:
            return None
        show = Show(*show)
        show.aliases = self.get_aliases(show)
        return show

    @db_error_default(None)
    def add_show(self, raw_show: UnprocessedShow, commit=True) -> int:
        """Add a show to the database."""

        debug("Inserting show: {}".format(raw_show))

        id = raw_show.media_id  # pylint: disable=W0622
        id_mal = raw_show.id_mal
        name = raw_show.name
        name_en = raw_show.name_en
        show_type = raw_show.show_type
        has_source = raw_show.has_source
        is_nsfw = raw_show.is_nsfw
        enabled = raw_show.is_airing
        self.q.execute(
            "INSERT INTO Shows (id, id_mal, name, name_en, type, has_source, is_nsfw, enabled) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (id, id_mal, name, name_en, show_type, has_source, is_nsfw, enabled),
        )

        if commit:
            self._db.commit()
        return id

    @db_error
    def add_alias(self, show_id: int, alias: str, commit=True):
        """Add an alias for a given show id."""

        debug("Adding an alias for show id {}".format(show_id))

        self.q.execute(
            "INSERT INTO Aliases (id, alias) VALUES (?, ?)", (show_id, alias)
        )
        if commit:
            self._db.commit()

    @db_error_default(None)
    def update_show(self, show_id: int, raw_show: UnprocessedShow, commit=True):
        """Update a show in the database."""

        debug("Updating show: {}".format(raw_show))

        id_mal = raw_show.id_mal
        name = raw_show.name
        name_en = raw_show.name_en
        show_type = raw_show.show_type
        has_source = raw_show.has_source
        is_nsfw = raw_show.is_nsfw
        enabled = raw_show.is_airing

        if id_mal:
            self.q.execute(
                "UPDATE Shows SET id_mal = ? WHERE id = ?", (id_mal, show_id)
            )
        if name:
            self.q.execute("UPDATE Shows SET name = ? WHERE id = ?", (name, show_id))
        if name_en:
            self.q.execute(
                "UPDATE Shows SET name_en = ? WHERE id = ?", (name_en, show_id)
            )
        self.q.execute(
            "UPDATE Shows SET type = ?, has_source = ?, is_nsfw = ?, enabled = ? WHERE id = ?",
            (show_type, has_source, is_nsfw, enabled, show_id),
        )

        if commit:
            self._db.commit()

    @db_error
    def set_show_enabled(self, show: Show, enabled=True, commit=True):
        """Set a show as enabled or disabled."""

        debug(
            "Marking show {} as {}".format(
                show.name, "enabled" if enabled else "disabled"
            )
        )

        self.q.execute("UPDATE Shows SET enabled = ? WHERE id = ?", (enabled, show.id))

        if commit:
            self._db.commit()

    @db_error
    def remove_show(self, show_id: int, commit=True):
        """Remove a show from the database entirely."""

        debug("Removing show with id {} from the database".format(show_id))

        self.q.execute("DELETE FROM Shows WHERE id = ?", (show_id,))

        if commit:
            self._db.commit()

    # Episodes

    @db_error
    def add_episode(self, media_id, episode_num, post_url=None):
        """
        Add an episode to the database.

            Parameters:
                show            id of the show for the episode
                episode_num     The episode number
                post_url        The url for the discussion post
        """

        show = self.get_show(media_id)

        debug(
            "Inserting episode {} for show {}, link: {}".format(
                episode_num, show.id, post_url
            )
        )

        self.q.execute(
            "INSERT INTO Episodes (id, episode, post_url) VALUES (?, ?, ?)",
            (show.id, episode_num, post_url),
        )
        self._db.commit()

    @db_error_default(None)
    def get_latest_episode(self, show: Show) -> Optional[Episode]:
        """Get the most recent episode for the given Show object."""

        debug("Fetching the most recent episode for {}".format(show.name))

        self.q.execute(
            "SELECT episode, post_url FROM Episodes WHERE show = ? ORDER BY episode DESC LIMIT 1",
            (show.id,),
        )
        data = self.q.fetchone()
        if data is not None:
            return Episode(show.id, data[0], data[1])
        return None

    @db_error_default(list())
    def get_episodes(self, show, ensure_sorted=True) -> List[Episode]:
        """Get a list of episodes for a given Show object."""

        debug("Fetching episodes for {}".format(show.name))

        episodes = list()
        self.q.execute(
            "SELECT episode, post_url FROM Episodes WHERE id = ?", (show.id,)
        )
        for data in self.q.fetchall():
            episodes.append(Episode(show.id, data[0], data[1]))

        if ensure_sorted:
            episodes = sorted(episodes, key=lambda e: e.number)
        return episodes

    @db_error
    def add_upcoming_episode(self, media_id, episode_num, airing_time):
        """Add an upcoming episode to the database."""

        self.q.execute(
            "INSERT INTO UpcomingEpisodes (id, episode, airing_time) VALUES (?, ?, ?)",
            (media_id, episode_num, airing_time),
        )

        self._db.commit()

    @db_error_default(list())
    def get_aired_episodes(self, current_time):
        """
        Get a list of UpcomingEpisodes that have a timestamp previous to provided
        current_time.
        """

        upcoming = []

        self.q.execute(
            "SELECT id, episode, airing_time FROM UpcomingEpisodes "
            "WHERE airing_time < ? ORDER BY airing_time ASC",
            (current_time,),
        )

        for data in self.q.fetchall():
            upcoming.append(
                UpcomingEpisode(media_id=data[0], number=data[1], airing_time=data[2])
            )

        return upcoming

    @db_error
    def remove_upcoming_episode(self, media_id, episode_num):
        """Remove an upcoming episode from the UpcomingEpisodes table."""

        self.q.execute(
            "DELETE FROM UpcomingEpisodes WHERE id = ? AND episode = ?",
            (media_id, episode_num),
        )

        self._db.commit()
