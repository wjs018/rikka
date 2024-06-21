"""Module to create a formatted page that lists the status of shows"""

import datetime

from jinja2 import Template

from logging import debug, info


def main(config, db, *args, **kwargs):
    """Main function for the module"""

    # Dict object to hold everything for jinja
    context = {}

    # First, compile list of currently enabled shows
    result = _get_enabled_shows(db)
    context["enabled"] = result[0]
    processed_ids = result[1]

    # Second, compile list of shows with at least one entry in IgnoredEpisodes table
    # Make sure they are not already in enabled shows list
    result = _get_requestable_shows(db, processed_ids)
    context["requestable"] = result[0]
    processed_ids = result[1]

    # Third, compile list of shows with at least one entry in UpcomingEpisodes table
    # Make sure they are not already in the previous two lists
    result = _get_upcoming_shows(db, processed_ids)
    context["upcoming"] = result[0]
    processed_ids = result[1]

    # Finally, put it all in one dict and then process the jinja template
    with open(config.template_file, "r") as file:
        template = Template(file.read(), trim_blocks=True)
    rendered = template.render(context=context)

    with open(config.output_filename, "w", encoding="utf8") as file:
        file.write(rendered)


def _get_enabled_shows(db):
    """
    Return list of all enabled shows in the database and separate list of all show ids.

    Returned object is of form [list of shows, list of ids]

    Format for each item in list of shows:
        result[0]       Show name
        result[1]       Show name in English
        result[2]       AniList link
        result[3]       Link to most recent discussion (if exists)
    """

    list_of_shows = []
    list_of_ids = []

    info("Fetching enabled shows from the database")
    db_shows = db.get_shows()
    info("Found {} enabled shows".format(len(db_shows)))

    for show in db_shows:
        debug("Handling show with id {}".format(show.id))
        list_of_ids.append(show.id)

        # Gather and construct the info we need for the show
        list_for_show = []
        list_for_show.append(show.name)

        # If no separate English name exists, just reuse the romaji
        if not show.name_en:
            list_for_show.append(show.name)
        else:
            list_for_show.append(show.name_en)

        list_for_show.append("https://anilist.co/anime/" + str(show.id))

        # Fetch the most recent episode if it exists
        debug("Fetching most recent episode for show with id {}".format(show.id))
        latest = db.get_latest_episode(show)

        if latest:
            list_for_show.append("[Link]({})".format(latest.link))
        else:
            list_for_show.append("")

        list_of_shows.append(list_for_show)

    list_of_shows.sort(key=lambda x: x[1])

    return [list_of_shows, list_of_ids]


def _get_requestable_shows(db, processed_ids):
    """
    Return list of all requestable shows not already enabled and list of newly added ids

    Returned object is of form [list of shows, list of ids]

    Format for each item in list of shows:
        result[0]       Show name
        result[1]       Show name in English
        result[2]       AniList link
        result[3]       Most recently aired episode number
    """

    list_of_shows = []

    info("Getting list of ignored shows from the database")
    ignored_shows = db.get_ignored_shows()
    info("Found {} ignored shows".format(len(ignored_shows)))

    for show in ignored_shows:
        if show.id in processed_ids:
            continue

        debug("Handling show with id {}".format(show.id))
        processed_ids.append(show.id)

        # Gather and construct the info we need for the show
        list_for_show = []
        list_for_show.append(show.name)

        # If no separate English name exists, just reuse the romaji
        if not show.name_en:
            list_for_show.append(show.name)
        else:
            list_for_show.append(show.name_en)

        list_for_show.append("https://anilist.co/anime/" + str(show.id))

        debug(
            "Fetching most recently ignored episode for show with id {}".format(show.id)
        )
        recent = db.get_most_recent_ignored(show.id)
        list_for_show.append("Episode " + str(recent.number))

        list_of_shows.append(list_for_show)

    list_of_shows.sort(key=lambda x: x[1])

    return [list_of_shows, processed_ids]


def _get_upcoming_shows(db, processed_ids):
    """
    Return list of all upcoming shows not already enabled and list of newly added ids

    Returned object is of form [list of shows, list of ids]

    Format for each item in list of shows:
        result[0]       Show name
        result[1]       Show name in English
        result[2]       AniList link
        result[3]       Airing time for first episode in GMT
    """

    list_of_shows = []

    info("Getting list of upcoming shows from the database")
    upcoming_shows = db.get_upcoming_shows()
    info("Found {} upcoming shows".format(len(upcoming_shows)))

    for show in upcoming_shows:
        if show.id in processed_ids:
            continue

        debug("Handling show with id {}".format(show.id))
        processed_ids.append(show.id)

        # Gather and construct the info we need for the show
        list_for_show = []
        list_for_show.append(show.name)

        # If no separate English name exists, just reuse the romaji
        if not show.name_en:
            list_for_show.append(show.name)
        else:
            list_for_show.append(show.name_en)

        list_for_show.append("https://anilist.co/anime/" + str(show.id))

        # Get the airing time of the next episode in GMT
        debug("Getting next episode for show with id {}".format(show.id))
        next_ep = db.get_next_episode(show.id)
        time_str = datetime.datetime.fromtimestamp(
            next_ep.airing_time, tz=datetime.timezone.utc
        ).strftime("%B %d at %H:%M")
        list_for_show.append(time_str)

        list_of_shows.append(list_for_show)

    list_of_shows.sort(key=lambda x: x[1])

    return [list_of_shows, processed_ids]
