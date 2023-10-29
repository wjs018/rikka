"""Module with common functions accessed by multiple modules."""

import time
import requests

from logging import debug, info, error
from data.models import UnprocessedShow
from config import min_ns, api_call_times

URL = "https://graphql.anilist.co"

show_query = """
query ($id: Int) {
  Media (id: $id) {
    id
    idMal
    title {
      romaji
      english
    }
    format
    source
    synonyms
    isAdult
    status
  }
}
"""


def add_update_show_by_id(db, show_id, ratelimit=60, enabled=True):
    """
    Either adds a show with given id if it isn't already in the database or updates an
    existing show in the database with fresh info from AniList.

        Parameters:
            db              DatabaseDatabase object
            show_id         AniList id for the show
            ratelimit       requests/min to limit api calls to
            enabled         Enabled/Disabled status of show to set

        Returns:
            show            Show object that has been added/updated in the database.
                            Will return None if it could not execute properly.
    """

    debug("Adding/Updating show with id {}".format(show_id))

    raw_show = get_show_info(show_id, ratelimit=ratelimit)

    if not raw_show:
        error("Could not fetch show info from AniList.")
        return None

    db_show = check_if_exists(db, show_id=show_id)

    if db_show:
        debug("Found show in database, updating")
        db.update_show(show_id=show_id, raw_show=raw_show, commit=True)
    else:
        debug("Did not find show in database, adding it")
        db.add_show(raw_show=raw_show, commit=True)

    show = db.get_show(show_id)

    # Make sure show is disabled if set to be so
    if not enabled:
        debug("Disabling show")
        db.set_show_enabled(show, enabled=False, commit=True)

    for alias in raw_show.more_names:
        debug("Adding alias for show id {} as {}".format(raw_show.media_id, alias))
        add_alias(db=db, show_id=show_id, alias=alias, commit=True)

    return show


def get_show_info(media_id, ratelimit=60):
    """
    Gets show info from AniList with given id.

        Parameters:
            media_id        int corresponding to the AniList id
            ratelimit       Number of requests/minute to limit api calls to

        Returns:
            raw_show        UnprocessedShow object for the show. Will return
                            None in case of a problem with the request.
    """

    variables = {"id": media_id}

    # Check api call times to make sure we stay under the ratelimit
    while len(api_call_times) >= ratelimit:
        oldest_call = api_call_times.pop()
        current_time = time.time_ns()

        delta_ns = current_time - oldest_call

        debug(
            "Interval since oldest call is {} seconds".format((delta_ns / 1000000000.0))
        )

        if delta_ns > min_ns:
            break

        sleep_secs = (min_ns - delta_ns) / 1000000000.0
        info("Sleeping {} seconds to respect rate limit.".format(sleep_secs))
        time.sleep(sleep_secs)

    # Make the HTTP API request
    try:
        info("Making request to AniList for show id {}".format(media_id))
        debug("Current length of deque is {}".format(len(api_call_times)))
        api_call_times.appendleft(time.time_ns())
        response = requests.post(
            URL, json={"query": show_query, "variables": variables}, timeout=5.0
        )
    except:
        error("Bad response from request")
        return None

    # Request went ok
    if response.ok:
        debug("Fetched show with id {} info from AniList".format(media_id))
    else:
        error("Bad response from request")
        return None

    json_resp = response.json()["data"]["Media"]

    # Extract the show info from the dict
    show_media_id = media_id
    show_id_mal = json_resp["idMal"]
    show_name = json_resp["title"]["romaji"]
    show_name_en = json_resp["title"]["english"]
    show_more_names = json_resp["synonyms"]
    show_show_type = json_resp["format"]
    show_has_source = int(json_resp["source"] != "ORIGINAL")
    show_is_nsfw = int(json_resp["isAdult"])
    show_status = json_resp["status"]

    if show_status in ["FINISHED", "CANCELLED"]:
        show_status = False
    else:
        show_status = True

    # Create the UnprocessedShow
    raw_show = UnprocessedShow(
        media_id=show_media_id,
        id_mal=show_id_mal,
        name=show_name,
        name_en=show_name_en,
        more_names=show_more_names,
        show_type=show_show_type,
        has_source=show_has_source,
        is_nsfw=show_is_nsfw,
        is_airing=show_status,
    )

    return raw_show


def check_if_exists(db, show_id):
    """Check if the show is already in the database."""

    debug("Checking database for show id {}".format(show_id))
    show = db.get_show(id=show_id)

    if show:
        debug("Found show titled {}".format(show.name))
        return show

    return None


def add_alias(db, show_id, alias, commit=True):
    """Add an alias for the given show."""

    db.add_alias(show_id=show_id, alias=alias, commit=commit)
