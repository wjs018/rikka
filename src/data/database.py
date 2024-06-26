"""
Module for interacting with the sqlite database used by rikka.
"""

import sqlite3
import re
import time

from functools import wraps
from logging import error, exception, debug
from typing import Optional, List
from unidecode import unidecode

from .models import (
    ShowType,
    Show,
    UnprocessedShow,
    Episode,
    UpcomingEpisode,
    Megathread,
    ExternalLink,
    Image,
    SummaryPost,
)


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
            megathread  INTEGER NOT NULL DEFAULT 0,
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
            """CREATE TABLE IF NOT EXISTS Seasons (
            id              INTEGER NOT NULL,
            season          TEXT NOT NULL,
            year            INTEGER NOT NULL,
            track           INTEGER NOT NULL DEFAULT 1,
            has_episodes    INTEGER NOT NULL DEFAULT 0,
            updated         INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(id) REFERENCES Shows(id) ON DELETE CASCADE,
            UNIQUE(id) ON CONFLICT REPLACE
        )"""
        )

        self.q.execute(
            """CREATE TABLE IF NOT EXISTS Episodes (
            id  		    INTEGER NOT NULL,
            episode		    INTEGER NOT NULL,
            post_url	    TEXT,
            can_edit        INTEGER NOT NULL,
            creation_time   INTEGER NOT NULL,
            UNIQUE(id, episode) ON CONFLICT REPLACE,
            FOREIGN KEY(id) REFERENCES Shows(id) ON DELETE CASCADE
        )"""
        )

        self.q.execute(
            """CREATE TABLE IF NOT EXISTS UserEpisodes (
            id              INTEGER NOT NULL,
            episode         INTEGER NOT NULL,
            post_url        text,
            can_edit        INTEGER NOT NULL,
            creation_time   INTEGER NOT NULL,
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

        self.q.execute(
            """CREATE TABLE IF NOT EXISTS IgnoredEpisodes (
            id              INTEGER NOT NULL,
            episode         INTEGER NOT NULL,
            airing_time     INTEGER NOT NULL,
            UNIQUE(id, episode) ON CONFLICT REPLACE,
            FOREIGN KEY(id) REFERENCES Shows(id) ON DELETE CASCADE
        )"""
        )

        self.q.execute(
            """CREATE TABLE IF NOT EXISTS LatestEpisodes (
            id              INTEGER NOT NULL,
            episode         INTEGER NOT NULL,
            post_url        TEXT,
            can_edit        INTEGER NOT NULL,
            creation_time   INTEGER NOT NULL,
            UNIQUE(id) ON CONFLICT REPLACE,
            FOREIGN KEY(id) REFERENCES Shows(id) ON DELETE CASCADE
        )"""
        )

        self.q.execute(
            """CREATE TABLE IF NOT EXISTS SummaryPosts (
            number          INTEGER NOT NULL,
            post_url        TEXT,
            pinned          INTEGER NOT NULL,
            creation_time   INTEGER NOT NULL,
            last_update     INTEGER NOT NULL,
            UNIQUE(number) ON CONFLICT REPLACE
        )"""
        )

        self.q.execute(
            """CREATE TABLE IF NOT EXISTS Megathreads (
            id              INTEGER NOT NULL,
            thread_num      INTEGER NOT NULL,
            post_url        TEXT,
            num_episodes    INTEGER NOT NULL,
            UNIQUE(id, thread_num) ON CONFLICT REPLACE,
            FOREIGN KEY(id) REFERENCES Shows(id) ON DELETE CASCADE
        )"""
        )

        self.q.execute(
            """CREATE TABLE IF NOT EXISTS Links (
            id              INTEGER NOT NULL,
            link_type       TEXT,
            site            TEXT,
            language        TEXT,
            url             TEXT,
            UNIQUE(id, site, language) ON CONFLICT REPLACE,
            FOREIGN KEY(id) REFERENCES Shows(id) ON DELETE CASCADE
        )"""
        )

        self.q.execute(
            """CREATE TABLE IF NOT EXISTS Images (
            id              INTEGER NOT NULL,
            image_type      TEXT,
            image_link      TEXT,
            UNIQUE(id, image_type) ON CONFLICT REPLACE,
            FOREIGN KEY(id) REFERENCES Shows(id) ON DELETE CASCADE
        )"""
        )

        self._db.commit()

    # Shows

    @db_error_default(list())
    def get_aliases(self, show: Show) -> List[str]:
        """Return list of aliases for a given Show object."""

        self.q.execute("SELECT alias FROM Aliases where id = ?", (show.id,))
        return [s for s, in self.q.fetchall()]

    @db_error_default(list())
    def get_shows(self, enabled="enabled") -> List[Show]:
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
                "SELECT id, id_mal, name, name_en, type, has_source, is_nsfw, \
                megathread, enabled FROM Shows"
            )
        else:
            if enabled == "enabled":
                enabled = 1
            elif enabled == "disabled":
                enabled = 0
            else:
                error("enabled parameter not set correctly")

            self.q.execute(
                "SELECT id, id_mal, name, name_en, type, has_source, is_nsfw, \
                megathread, enabled FROM Shows WHERE enabled = ?",
                (enabled,),
            )

        for show in self.q.fetchall():
            show = Show(*show)
            show.aliases = self.get_aliases(show)
            show.external_links = self.get_external_links(show.id)
            shows.append(show)

        return shows

    @db_error_default(None)
    def get_show(self, id=None) -> Optional[Show]:  # pylint: disable=W0622
        """Query the database and return the Show object from given id."""

        debug("Getting show from database")

        if id is None:
            error("Show ID not provided to get_show")
            return None
        self.q.execute(
            "SELECT id, id_mal, name, name_en, type, has_source, is_nsfw, megathread, \
            enabled FROM Shows WHERE id = ?",
            (id,),
        )
        show = self.q.fetchone()
        if show is None:
            return None
        show = Show(*show)
        show.aliases = self.get_aliases(show)
        show.external_links = self.get_external_links(show.id)
        show.season = self.get_season(show.id)
        show.year = self.get_year(show.id)
        return show

    @db_error_default(None)
    def get_show_by_name(self, name) -> Optional[Show]:
        """Query the database and return the Show object from given name."""

        debug("Getting show from database")

        self.q.execute(
            "SELECT id, name, name_en, type, has_source, is_nsfw, megathread, enabled, \
            FROM Shows WHERE name = ?",
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

        # None is written to db as NULL and can sometimes end up in posts, just use ""
        if not id_mal:
            id_mal = ""

        if not name_en:
            name_en = ""

        if name_en:
            if name_en.lower() == name.lower():
                name_en = ""

        # Sanitize & to and to avoid over-zealous lemmy sanitization in post titles
        name = name.replace("&", " and ")
        name = re.sub(r"\s+", " ", name)
        if name_en:
            name_en = name_en.replace("&", " and ")
            name_en = re.sub(r"\s+", " ", name_en)

        show_type = raw_show.show_type
        has_source = raw_show.has_source
        is_nsfw = raw_show.is_nsfw
        enabled = raw_show.is_airing
        self.q.execute(
            "INSERT INTO Shows (id, id_mal, name, name_en, type, has_source, is_nsfw, \
            enabled) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (id, id_mal, name, name_en, show_type, has_source, is_nsfw, enabled),
        )

        if commit:
            self._db.commit()

        season = raw_show.season
        year = raw_show.year
        self.add_season_year(media_id=id, season=season, year=year)

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
    def update_show(
        self, show_id: int, raw_show: UnprocessedShow, commit=True, ignore_enabled=False
    ):
        """Update a show in the database."""

        debug("Updating show: {}".format(raw_show))

        id_mal = raw_show.id_mal
        name = raw_show.name
        name_en = raw_show.name_en

        # None is written to db as NULL and can sometimes end up in posts, just use ""
        if not id_mal:
            id_mal = ""

        if not name_en:
            name_en = ""

        if name_en:
            if name_en.lower() == name.lower():
                name_en = ""

        # Sanitize & to and to avoid over-zealous lemmy sanitization in post titles
        name = name.replace("&", " and ")
        name = re.sub(r"\s+", " ", name)
        if name_en:
            name_en = name_en.replace("&", " and ")
            name_en = re.sub(r"\s+", " ", name_en)

        show_type = raw_show.show_type
        has_source = raw_show.has_source
        is_nsfw = raw_show.is_nsfw

        if not ignore_enabled:
            enabled = raw_show.is_airing
        else:
            db_show = self.get_show(id=show_id)
            enabled = db_show.enabled

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

        self.add_season_year(
            media_id=show_id,
            season=raw_show.season,
            year=raw_show.year,
            ignore_tracking=True,
        )
        self.update_single_has_episodes(media_id=show_id)

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

    @db_error_default(bool)
    def get_megathread_status(self, show_id):
        """
        Returns a boolean. True if a show is currently set to post in a
        megathread, False if episodes get individual discussion posts.
        """

        self.q.execute("SELECT megathread FROM Shows WHERE id = ?", (show_id,))

        megathread = self.q.fetchone()

        return bool(megathread)

    @db_error_default(list)
    def get_megathread_statuses(self, enabled="enabled"):
        """
        Returns a list of show ids that are set to use megathreads.

        enabled parameter can have values of 'enabled', 'disabled', or 'all'
        and has an identical filtering effect as get_shows().
        """

        debug("Getting list of shows using megathreads from the database.")

        show_ids = list()

        if enabled == "all":
            self.q.execute("SELECT id FROM Shows WHERE megathread = ?", (1,))
        else:
            if enabled == "enabled":
                enabled = 1
            elif enabled == "disabled":
                enabled = 0
            else:
                error("enabled parameter not set correctly")

            self.q.execute(
                "SELECT id FROM Shows WHERE megathread = ? AND enabled = ?",
                (1, enabled),
            )

        for show in self.q.fetchall():
            show_ids.append(show)

        return show_ids

    @db_error
    def set_megathread_status(self, show_id, enabled, commit=True):
        """Set a show to post to a megathread or not."""

        self.q.execute(
            "UPDATE Shows SET megathread = ? WHERE id = ?", (int(enabled), show_id)
        )

        if commit:
            self._db.commit()

    # Seasons

    @db_error
    def add_season_year(
        self,
        media_id,
        season,
        year,
        track=True,
        has_episodes=False,
        updated=False,
        ignore_tracking=False,
    ):
        """Add the season and year to the Seasons table"""

        track_status = self.get_track_status(media_id=media_id)
        if track_status is None:
            track_status = int(track)

        if not ignore_tracking:
            self.q.execute(
                "INSERT INTO Seasons (id, season, year, track, has_episodes, updated) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (media_id, season, year, int(track), int(has_episodes), int(updated)),
            )
        else:
            self.q.execute(
                "INSERT INTO Seasons (id, season, year, track, has_episodes, updated) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (media_id, season, year, track_status, int(has_episodes), int(updated)),
            )

        self._db.commit()

    @db_error_default(int)
    def get_track_status(self, media_id):
        """Get the status of a shows track value in the Seasons table if it exists."""

        self.q.execute("SELECT track FROM Seasons WHERE id = ?", (media_id,))

        data = self.q.fetchone()
        if data is not None:
            return data[0]
        else:
            return None

    @db_error_default(int)
    def get_year(self, media_id):
        """Get the year for a given id."""

        self.q.execute("SELECT year FROM Seasons WHERE id = ?", (media_id,))

        data = self.q.fetchone()

        if data is not None:
            return int(data[0])
        else:
            return None

    @db_error_default(str)
    def get_season(self, media_id):
        """Get the season for a given media id."""

        self.q.execute("SELECT season FROM Seasons WHERE id = ?", (media_id,))

        data = self.q.fetchone()

        if data is not None:
            return data[0]
        else:
            return None

    @db_error
    def set_updated(self, media_id, updated=True):
        """Mark a show in the Seasons table as having had the episode list updated."""

        self.q.execute(
            "UPDATE Seasons SET updated = ? WHERE id = ?", (int(updated), media_id)
        )
        self._db.commit()

    @db_error
    def set_has_episodes(self, media_id, has_episodes=True):
        """Mark a show as having episodes"""

        self.q.execute(
            "UPDATE Seasons SET has_episodes = ? WHERE id = ?",
            (int(has_episodes), media_id),
        )
        self._db.commit()

    @db_error
    def set_tracking(self, media_id, track=True):
        """Mark whether a show should be tracked for wiki-updating purposes."""

        self.q.execute(
            "UPDATE Seasons SET track = ? WHERE id = ?", (int(track), media_id)
        )
        self._db.commit()

    @db_error_default(list())
    def get_updated_shows(self):
        """Fetch list of show ids that are marked as updated in the Seasons table."""

        id_list = []

        self.q.execute("SELECT id FROM Seasons WHERE updated = ?", (1,))

        data = self.q.fetchall()
        for show in data:
            id_list.append(show[0])

        return id_list

    @db_error_default(dict())
    def get_season_struct(self):
        """Returns the contents of the Seasons table in a nested dict format."""

        result = {}

        self.q.execute("SELECT id, season, year FROM Seasons WHERE track = ?", (1,))

        data = self.q.fetchall()
        for show in data:
            if show[2] not in result:
                result[show[2]] = {show[1]: [show[0]]}
            else:
                if show[1] not in result[show[2]]:
                    result[show[2]][show[1]] = [show[0]]
                else:
                    result[show[2]][show[1]].append(show[0])

        return result

    @db_error_default(list())
    def get_seasons_with_episodes(self, track=True, has_episodes=True):
        """
        Returns list of all seasons that are tracked and have episodes from Seasons
        table.
        """

        result = []

        self.q.execute(
            "SELECT DISTINCT season, year FROM Seasons WHERE track = ? AND "
            "has_episodes = ?",
            (int(track), int(has_episodes)),
        )

        data = self.q.fetchall()
        for row in data:
            result.append([row[0], row[1]])

        return result

    @db_error_default(list())
    def get_shows_from_season(self, season, year, track=True, has_episodes=True):
        """
        Returns list of show ids from a specified season that are tracked and have
        episodes.
        """

        result = []

        self.q.execute(
            "SELECT id FROM Seasons WHERE season = ? AND year = ? AND track = ? "
            "AND has_episodes = ?",
            (season, year, int(track), int(has_episodes)),
        )

        data = self.q.fetchall()
        for row in data:
            result.append(row[0])

        return result

    @db_error
    def set_track_season(self, season, year, track):
        """
        Mark all shows in a given season and year whether to be tracked in Seasons
        table.
        """

        self.q.execute(
            "UPDATE Seasons SET track = ? WHERE season = ? AND year = ?",
            (int(track), season, year),
        )
        self._db.commit()

    @db_error
    def set_season_updated(self, season, year, updated=False):
        """
        Mark all shows in a given season and year as updated (or not) in Seasons
        table.
        """

        self.q.execute(
            "UPDATE Seasons SET updated = ? WHERE season = ? AND year = ?",
            (int(updated), season, year),
        )
        self._db.commit()

    @db_error
    def update_all_has_episodes(self):
        """
        Forces checking each show in the Seasons table to see if there are episodes in
        the Episodes table corresponding to it.
        """

        id_list = []

        self.q.execute("SELECT id FROM Seasons")

        data = self.q.fetchall()
        for row in data:
            id_list.append(row[0])

        for show in id_list:
            self.q.execute("SELECT episode FROM Episodes WHERE id = ?", (show,))
            data = self.q.fetchone()
            if data is not None:
                self.set_has_episodes(media_id=show, has_episodes=True)
            else:
                self.set_has_episodes(media_id=show, has_episodes=False)

    @db_error
    def update_single_has_episodes(self, media_id):
        """
        Updates a single show in the Seasons table to mark if there are episodes in the
        Episodes table corresponding to it.
        """

        self.q.execute("SELECT episode FROM Episodes WHERE id = ?", (media_id,))

        data = self.q.fetchone()
        if data is not None:
            self.set_has_episodes(media_id=media_id, has_episodes=True)
        else:
            self.set_has_episodes(media_id=media_id, has_episodes=False)

    # Episodes

    @db_error
    def add_episode(
        self, media_id, episode_num, post_url=None, can_edit=True, creation_time=None
    ):
        """
        Add an episode to the database.

            Parameters:
                show                id of the show for the episode
                episode_num         The episode number
                post_url            The url for the discussion post
                can_edit            The post is editable by rikka
                creation_time       The unix timestamp that the post was created
        """

        show = self.get_show(media_id)

        debug(
            "Inserting episode {} for show {}, link: {}".format(
                episode_num, show.id, post_url
            )
        )

        if not creation_time:
            creation_time = int(time.time())

        self.q.execute(
            "INSERT INTO Episodes (id, episode, post_url, can_edit, creation_time) "
            "VALUES (?, ?, ?, ?, ?)",
            (show.id, episode_num, post_url, int(can_edit), creation_time),
        )
        self._db.commit()

        self.set_has_episodes(media_id=media_id, has_episodes=True)
        self.set_updated(media_id=media_id, updated=True)

    @db_error_default(None)
    def get_latest_episode(self, show: Show) -> Optional[Episode]:
        """Get the most recent episode for the given Show object."""

        debug("Fetching the most recent episode for {}".format(show.name))

        self.q.execute(
            "SELECT episode, post_url, can_edit, creation_time FROM Episodes WHERE "
            "id = ? ORDER BY episode DESC LIMIT 1",
            (show.id,),
        )
        data = self.q.fetchone()
        if data is not None:
            return Episode(show.id, *data)
        return None

    @db_error_default(Episode)
    def get_episode(self, show: Show, episode: int) -> Optional[Episode]:
        """Get a specific episode for the given show and episode number"""

        debug("Fetching episode {} for show {}".format(episode, show.name))

        self.q.execute(
            "SELECT episode, post_url, can_edit, creation_time FROM Episodes WHERE "
            "id = ? AND episode = ? LIMIT 1",
            (show.id, episode),
        )

        data = self.q.fetchone()
        if data is not None:
            return Episode(show.id, *data)
        return None

    @db_error_default(list())
    def get_episodes(self, show, ensure_sorted=True) -> List[Episode]:
        """Get a list of episodes for a given Show object."""

        debug("Fetching episodes for {}".format(show.name))

        episodes = list()
        self.q.execute(
            "SELECT episode, post_url, can_edit, creation_time FROM Episodes WHERE "
            "id = ?",
            (show.id,),
        )
        for data in self.q.fetchall():
            episodes.append(Episode(show.id, *data))

        if ensure_sorted:
            episodes = sorted(episodes, key=lambda e: e.number)
        return episodes

    @db_error_default(list())
    def get_recent_episodes(self, num_days=8):
        """Return all Episodes within the past num_days"""

        current_time = int(time.time())
        cutoff_time = current_time - (num_days * 24 * 60 * 60)
        episodes = list()

        self.q.execute(
            "SELECT id, episode, post_url, can_edit, creation_time FROM Episodes WHERE "
            "creation_time > ?",
            (cutoff_time,),
        )

        for data in self.q.fetchall():
            episodes.append(Episode(*data))

        return episodes

    @db_error
    def add_user_episode(
        self, media_id, episode_num, post_url=None, can_edit=True, creation_time=None
    ):
        """Adds a user created episode to the UserEpisodes table"""

        show = self.get_show(media_id)

        debug(
            "Inserting user episode {} for show {}, link: {}".format(
                episode_num, show.id, post_url
            )
        )

        if not creation_time:
            creation_time = int(time.time())

        self.q.execute(
            "INSERT INTO UserEpisodes (id, episode, post_url, can_edit, creation_time) "
            "VALUES (?, ?, ?, ?, ?)",
            (show.id, episode_num, post_url, int(can_edit), creation_time),
        )
        self._db.commit()

    @db_error_default(Episode)
    def get_user_episode(self, show: Show, episode: int) -> Optional[Episode]:
        """Get a specific episode for the given show and episode number"""

        debug("Fetching episode {} for show {}".format(episode, show.name))

        self.q.execute(
            "SELECT episode, post_url, can_edit, creation_time FROM UserEpisodes WHERE "
            "id = ? AND episode = ? LIMIT 1",
            (show.id, episode),
        )

        data = self.q.fetchone()
        if data is not None:
            return Episode(show.id, *data)
        return None

    @db_error_default(list())
    def get_user_episodes(self, show, ensure_sorted=True) -> List[Episode]:
        """Get a list of episodes for a given Show object."""

        debug("Fetching user episodes for {}".format(show.name))

        episodes = list()
        self.q.execute(
            "SELECT episode, post_url, can_edit, creation_time FROM UserEpisodes WHERE "
            "id = ?",
            (show.id,),
        )
        for data in self.q.fetchall():
            episodes.append(Episode(show.id, *data))

        if ensure_sorted:
            episodes = sorted(episodes, key=lambda e: e.number)
        return episodes

    @db_error
    def add_upcoming_episode(self, upcoming_episode):
        """
        Add an upcoming episode to the database using given UpcomingEpisode object.
        """

        media_id = upcoming_episode.media_id
        episode_num = upcoming_episode.number
        airing_time = upcoming_episode.airing_time

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

    @db_error_default(UpcomingEpisode)
    def get_next_episode(self, media_id):
        """
        Return the next UpcomingEpisode object in time for the given show id.
        """

        self.q.execute(
            "SELECT id, episode, airing_time FROM UpcomingEpisodes "
            "WHERE id = ? ORDER BY airing_time ASC",
            (media_id,),
        )

        data = self.q.fetchone()
        if data is not None:
            return UpcomingEpisode(*data)
        else:
            return None

    @db_error_default(list())
    def get_upcoming_shows(self) -> Optional[List[Show]]:

        show_ids = []
        shows = []

        self.q.execute("SELECT DISTINCT id FROM UpcomingEpisodes")

        for row in self.q.fetchall():
            show_ids.append(row[0])

        for media_id in show_ids:
            shows.append(self.get_show(media_id))

        return shows

    @db_error
    def remove_upcoming_episode(self, media_id, episode_num):
        """Remove an upcoming episode from the UpcomingEpisodes table."""

        self.q.execute(
            "DELETE FROM UpcomingEpisodes WHERE id = ? AND episode = ?",
            (media_id, episode_num),
        )

        self._db.commit()

    @db_error
    def remove_upcoming_episodes(self, media_id):
        """Remove all upcoming episodes for a given show from the database."""

        self.q.execute("DELETE FROM UpcomingEpisodes WHERE id = ?", (media_id,))

        self._db.commit()

    @db_error
    def add_ignored_episode(self, upcoming_episode: UpcomingEpisode):
        """Add an ignored episode to the table."""

        media_id = upcoming_episode.media_id
        episode_num = upcoming_episode.number
        airing_time = upcoming_episode.airing_time

        self.q.execute(
            "INSERT INTO IgnoredEpisodes (id, episode, airing_time) VALUES (?, ?, ?)",
            (media_id, episode_num, airing_time),
        )

        self._db.commit()

    @db_error_default(UpcomingEpisode)
    def get_ignored_episode(
        self, media_id: int, episode: int
    ) -> Optional[UpcomingEpisode]:
        """Get an ignored episode from the database"""

        self.q.execute(
            "SELECT id, episode, airing_time FROM IgnoredEpisodes "
            "WHERE id = ? AND episode = ? LIMIT 1",
            (media_id, episode),
        )

        data = self.q.fetchone()
        if data is not None:
            return UpcomingEpisode(media_id, episode, data[2])
        return None

    @db_error_default(UpcomingEpisode)
    def get_most_recent_ignored(self, media_id: int) -> Optional[UpcomingEpisode]:
        """Get the most recently aired but ignored episode for a given show."""

        self.q.execute(
            "SELECT id, episode, airing_time FROM IgnoredEpisodes "
            "WHERE id = ? ORDER BY airing_time DESC",
            (media_id,),
        )

        data = self.q.fetchone()
        if data is not None:
            return UpcomingEpisode(*data)
        else:
            return None

    @db_error_default(list())
    def get_ignored_shows(self) -> Optional[List[Show]]:

        show_ids = []
        shows = []

        self.q.execute("SELECT DISTINCT id FROM IgnoredEpisodes")

        for row in self.q.fetchall():
            show_ids.append(row[0])

        for media_id in show_ids:
            shows.append(self.get_show(media_id))

        return shows

    @db_error
    def remove_ignored_episode(self, media_id: int, episode: int):
        """Remove an ignored episode from the database"""

        self.q.execute(
            "DELETE FROM IgnoredEpisodes WHERE id = ? AND episode = ?",
            (media_id, episode),
        )

        self._db.commit()

    @db_error
    def remove_old_ignored_episodes(self, num_days=30):
        """Remove all ignored episodes after they have been ignored for a given time"""

        current_time = int(time.time())
        cutoff = current_time - (num_days * 24 * 60 * 60)

        self.q.execute("DELETE FROM IgnoredEpisodes WHERE airing_time < ?", (cutoff,))

        self._db.commit()

    @db_error
    def build_latest_episodes(self, num_days=8):
        """
        Adds the most recent Episode to the LatestEpisodes table if it was created
        within the past num_days
        """

        # First, get all episodes created more recently than num_days ago
        recent_episodes = self.get_recent_episodes(num_days=num_days)

        # Next, iterate through, getting the latest episode for each show
        for recent_episode in recent_episodes:
            show = self.get_show(recent_episode.media_id)
            most_recent = self.get_latest_episode(show=show)
            self.add_latest_episode(most_recent)

    @db_error
    def prune_latest_episodes(self, num_days=8):
        """
        Prunes LatestEpisodes table of items created more than num_days in the past.
        """

        current_time = int(time.time())
        cutoff = current_time - (num_days * 24 * 60 * 60)

        self.q.execute("DELETE FROM LatestEpisodes WHERE creation_time < ?", (cutoff,))

        self._db.commit()

    @db_error
    def add_latest_episode(self, episode: Episode):
        """Adds an episode to the LatestEpisodes table"""

        self.q.execute(
            "INSERT INTO LatestEpisodes (id, episode, post_url, can_edit, creation_time)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                episode.media_id,
                episode.number,
                episode.link,
                int(episode.can_edit),
                episode.creation_time,
            ),
        )
        self._db.commit()

    @db_error_default(list)
    def get_latest_episodes(self):
        """Returns a list of all the Episode objects in LatestEpisodes table"""

        latest_episodes = []

        self.q.execute("SELECT * FROM LatestEpisodes ORDER BY creation_time DESC")

        for row in self.q.fetchall():
            latest_episodes.append(Episode(*row))

        return latest_episodes

    @db_error
    def add_summary_post(self, summary_post: SummaryPost):
        """Adds a summary post to the SummaryPosts table."""

        self.q.execute(
            "INSERT INTO SummaryPosts (number, post_url, pinned, creation_time, "
            "last_update) VALUES (?, ?, ?, ?, ?)",
            (
                summary_post.number,
                summary_post.post_url,
                summary_post.pinned,
                summary_post.creation_time,
                summary_post.last_update,
            ),
        )
        self._db.commit()

    @db_error_default(SummaryPost)
    def get_summary_post(self, number):
        """Fetches a specific SummaryPost"""

        self.q.execute(
            "SELECT post_url, pinned, creation_time, last_update FROM SummaryPosts "
            "WHERE number = ?",
            (number,),
        )

        data = self.q.fetchone()
        if data is not None:
            return SummaryPost(number=number, *data)
        else:
            return None

    @db_error_default(SummaryPost)
    def get_latest_summary_post(self):
        """Fetches the most recent summary post"""

        self.q.execute(
            "SELECT number, post_url, pinned, creation_time, last_update FROM "
            "SummaryPosts ORDER BY number DESC LIMIT 1"
        )

        data = self.q.fetchone()
        if data is not None:
            return SummaryPost(*data)
        else:
            return None

    @db_error_default(list)
    def get_pinned_summary_posts(self):
        """Fetches any summary posts that are marked as pinned"""

        summary_posts = []

        self.q.execute(
            "SELECT number, post_url, pinned, creation_time, last_update FROM "
            "SummaryPosts WHERE pinned = 1"
        )

        for post in self.q.fetchall():
            summary_posts.append(SummaryPost(*post))

        return summary_posts

    # Megathreads

    @db_error_default(list)
    def get_megathreads(self, media_id):
        """Returns all the megathreads for a given media id."""

        megathreads = []

        self.q.execute(
            "SELECT id, thread_num, post_url, num_episodes FROM Megathreads \
            WHERE id = ? ORDER BY thread_num DESC",
            (media_id,),
        )

        for thread in self.q.fetchall():
            thread = Megathread(*thread)
            megathreads.append(thread)

        return megathreads

    @db_error_default(None)
    def get_latest_megathread(self, media_id):
        """Get the most recent megathread for a given show id."""

        self.q.execute(
            "SELECT id, thread_num, post_url, num_episodes FROM Megathreads \
            WHERE id = ? ORDER BY thread_num DESC LIMIT 1",
            (media_id,),
        )

        thread = self.q.fetchone()
        if thread is not None:
            return Megathread(*thread)
        return None

    @db_error
    def add_megathread(self, megathread: Megathread, commit=True):
        """Add or update a megathread in the database."""

        debug("Inserting megathread: {}".format(megathread))

        id = megathread.media_id
        thread_num = megathread.thread_num
        post_url = megathread.post_url
        num_episodes = megathread.num_episodes

        self.q.execute(
            "INSERT INTO Megathreads (id, thread_num, post_url, num_episodes) VALUES \
            (?, ?, ?, ?)",
            (id, thread_num, post_url, num_episodes),
        )

        if commit:
            self._db.commit()

    @db_error
    def increment_num_episodes(self, megathread: Megathread, commit=True):
        """Increases num_episodes by 1 for given megathread."""

        id = megathread.media_id
        thread_num = megathread.thread_num
        new_num_episodes = megathread.num_episodes + 1

        self.q.execute(
            "UPDATE Megathreads SET num_episodes = ? WHERE id = ? AND thread_num = ?",
            (new_num_episodes, id, thread_num),
        )

    # External Links

    @db_error
    def add_external_link(self, external_link: ExternalLink, commit=True):
        """Add an external link for a given show id."""

        debug("Adding an external link for show id {}".format(external_link.media_id))

        # None is written to db as NULL and can sometimes end up in posts, just use ""
        if not external_link.language:
            external_link.language = ""

        self.q.execute(
            "INSERT INTO Links (id, link_type, site, language, url) VALUES (?, ?, ?, ?, ?)",
            (
                external_link.media_id,
                external_link.link_type,
                external_link.site,
                external_link.language,
                external_link.url,
            ),
        )

        if commit:
            self._db.commit()

    @db_error_default(List)
    def get_external_links(self, media_id):
        """Return all the external links for a given id."""

        debug("Fetching all the external links for show id {}".format(media_id))

        external_links = []

        self.q.execute(
            "SELECT id, link_type, site, language, url FROM Links WHERE id = ? \
            ORDER BY link_type ASC",
            (media_id,),
        )

        for link in self.q.fetchall():
            external_link = ExternalLink(*link)
            external_links.append(external_link)

        return external_links

    # Images

    @db_error
    def add_image(self, image: Image, commit=True):
        """Add an image for a show to the database"""

        debug("Adding an image for show id {}".format(image.media_id))

        self.q.execute(
            "INSERT INTO Images (id, image_type, image_link) VALUES (?, ?, ?)",
            (image.media_id, image.image_type, image.image_link),
        )

        if commit:
            self._db.commit()

    @db_error_default(Image)
    def get_banner_image(self, media_id):
        """Retrieve the banner image for a show."""

        debug("Fetching the banner image for show id {}".format(media_id))

        self.q.execute(
            "SELECT image_link FROM Images WHERE id = ? AND image_type = ? LIMIT 1",
            (media_id, "banner"),
        )

        banner_link = self.q.fetchone()
        if banner_link is None:
            return None
        banner_image = Image(
            media_id=media_id, image_type="banner", image_link=banner_link[0]
        )
        return banner_image

    @db_error_default(Image)
    def get_cover_image(self, media_id):
        """Retrieve the cover image for a show."""

        debug("Fetching the cover image for show id {}".format(media_id))

        self.q.execute(
            "SELECT image_link FROM Images WHERE id = ? AND image_type = ? LIMIT 1",
            (media_id, "cover"),
        )

        cover_link = self.q.fetchone()
        if cover_link is None:
            return None
        cover_image = Image(
            media_id=media_id, image_type="cover", image_link=cover_link[0]
        )
        return cover_image
