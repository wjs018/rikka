"""Module to find and make discussion threads for show episodes."""

import time
import requests

from logging import debug, info, error

import lemmy
from config import min_ns, api_call_times
from helper_functions import URL
from data.models import UpcomingEpisode


airing_schedule_query = """
query ($time: Int, $id: [Int]) {
  Page(page: 1, perPage: 3) {
    pageInfo {
      total
    }
    airingSchedules(airingAt_greater: $time, sort: TIME, mediaId_in: $id) {
      airingAt
      episode
    }
  }
}
"""


def main(config, db, *args, **kwargs):
    """Main function for episode module"""
    lemmy.init_lemmy(config)

    # Check for new upcoming episodes, populate UpcomingEpisodes table
    info("Fetching all upcoming episodes from AniList")
    _add_update_upcoming_episodes(db=db, ratelimit=config.ratelimit)

    # Check for episodes in UpcomingEpisodes table that have air dates prior to program
    # runtime
    info("Checking for episodes that have aired.")
    current_time = int(time.time())
    aired = _get_aired_episodes(db=db, current_time=current_time)
    info("Found {} episodes that have aired.".format(len(aired)))

    # Make a post for aired episodes, populate Episodes table
    for episode in aired:
        episode_title, episode_body = _create_post_contents(
            config, db, episode, submit=config.submit
        )

        post_url = _create_post(
            config, episode_title, episode_body, submit=config.submit
        )

        if post_url:
            post_url.replace("http:", "https:")
            info("Post made at url: {}".format(post_url))
            # Add the posted episode to the Episodes table
            db.add_episode(episode.media_id, episode.number, post_url)

            # Remove the just-posted episode from the UpcomingEpisodes table
            db.remove_upcoming_episode(episode.media_id, episode.number)

            # Edit the link table in previous episode posts
            show = db.get_show(episode.media_id)
            show_episodes = db.get_episodes(show)

            if len(show_episodes) > 0:
                edit_history_length = int(4 * 13 / 2)  # cols x rows / 2
                show_episodes.sort(key=lambda x: x.number)
                for editing_episode in show_episodes[-edit_history_length:]:
                    _edit_post(
                        config,
                        db,
                        editing_episode,
                        editing_episode.link,
                        submit=config.submit,
                    )

        else:
            error("Episode not submitted")


def _add_update_upcoming_episodes(db, ratelimit=60):
    """
    Queries AniList for the airing schedule and updates the database. Only grabs up to
    the next three airing episodes for each show.
    """

    debug("Getting list of enabled shows from database")
    shows = db.get_shows(enabled="enabled")

    retries = {}

    for show in shows:
        retries[show.id] = 0

    for show in shows:
        upcoming_list = _fetch_upcoming_episodes(show_id=show.id, ratelimit=ratelimit)

        if not upcoming_list:
            info("No upcoming episodes found for show {}".format(show.id))
            continue
        elif upcoming_list == "bad response":
            if retries[show.id] >= 3:
                error("Failed getting show info 3 times, skipping")
                continue

            error(
                "Problem fetching episodes, have retried {} times".format(
                    retries[show.id]
                )
            )
            retries[show.id] += 1
            shows.append(show)
            continue

        info(
            "Found {} upcoming episodes for show {}".format(len(upcoming_list), show.id)
        )

        for episode in upcoming_list:
            debug("Adding upcoming episode to the database.")
            db.add_upcoming_episode(
                media_id=show.id,
                episode_num=episode.number,
                airing_time=episode.airing_time,
            )


def _fetch_upcoming_episodes(show_id, ratelimit=60):
    """Makes the api call for a given show id."""

    current_unix_time = int(time.time())

    variables = {"time": current_unix_time, "id": [show_id]}

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
        debug("Sleeping {} seconds to respect rate limit.".format(sleep_secs))
        time.sleep(sleep_secs)

    # Make the HTTP API request
    try:
        info("Making request to AniList for airing times of show id {}".format(show_id))
        debug("Current length of deque is {}".format(len(api_call_times)))
        api_call_times.appendleft(time.time_ns())
        response = requests.post(
            URL,
            json={"query": airing_schedule_query, "variables": variables},
            timeout=5.0,
        )
    except:
        error("Bad response from request for airing times")
        return "bad response"

    # Request went ok
    if response.ok:
        debug("Fetched airing schedule for show with id {}".format(show_id))
    else:
        error("Bad response from request")
        return "bad response"

    json_resp = response.json()["data"]
    episodes_found = json_resp["Page"]["airingSchedules"]
    upcoming_list = []

    for episode in episodes_found:
        airing_time = episode["airingAt"]
        episode_num = episode["episode"]

        upcoming = UpcomingEpisode(
            media_id=show_id, number=episode_num, airing_time=airing_time
        )
        upcoming_list.append(upcoming)

    return upcoming_list


def _get_aired_episodes(db, current_time):
    """Get list of episodes that aired."""

    debug("Querying database for upcoming episodes that have aired.")
    aired = db.get_aired_episodes(current_time)

    debug("Found {} episodes that have aired in the database.".format(len(aired)))

    return aired


def _create_post(config, title, body, submit=True):
    """Creates the discussion post on Lemmy."""

    if submit:
        new_post = lemmy.submit_text_post(config.l_community, title, body)
        if new_post is not None:
            debug("Post successful")
            return lemmy.get_shortlink_from_id(new_post["id"])

        error("Failed to submit post")

    return None


def _edit_post(config, db, aired_episode, url, submit=True):
    """Edits the table of links in a discussion post."""

    _, body = _create_post_contents(config, db, aired_episode, submit=submit)

    if submit:
        lemmy.edit_text_post(url, body)
    return None


def _create_post_contents(config, db, aired_episode, submit=True):
    """Make a discussion post to Lemmy for the aired episode."""

    post_title = _create_post_title(config, db, aired_episode)
    post_title = _format_post_text(config, db, aired_episode, post_title)

    info("Post title:\n{}".format(post_title))

    post_body = _format_post_text(config, db, aired_episode, config.post_body)

    return post_title, post_body


def _create_post_title(config, db, aired_episode):
    """Construct the post title"""

    show = db.get_show(aired_episode.media_id)

    if show.name_en:
        title = config.post_title_with_en
    else:
        title = config.post_title

    return title


def _format_post_text(config, db, aired_episode, text):
    """Format the text to substitute placeholders."""

    formats = config.post_formats

    show = db.get_show(aired_episode.media_id)

    if "{spoiler}" in text:
        text = safe_format(text, spoiler=_gen_text_spoiler(formats, show))
    if "{discussions}" in text:
        text = safe_format(text, discussions=_gen_text_discussions(db, formats, show))
    if "{aliases}" in text:
        text = safe_format(text, aliases=_gen_text_aliases(db, formats, show))

    text = safe_format(
        text,
        show_name=show.name,
        show_name_en=show.name_en,
        episode=aired_episode.number,
    )
    return text.strip()


def _gen_text_spoiler(formats, show):
    debug(
        "Generating spoiler text for show {}, spoiler is {}".format(
            show, show.has_source
        )
    )
    if show.has_source:
        return formats["spoiler"]
    return ""


def _gen_text_discussions(db, formats, show):
    episodes = db.get_episodes(show)
    debug("Num previous episodes: {}".format(len(episodes)))
    N_LINES = 13
    n_episodes = 4 * N_LINES  # maximum 4 columns
    if len(episodes) > n_episodes:
        debug(f"Clipping to most recent {n_episodes} episodes")
        episodes = episodes[-n_episodes:]
    if len(episodes) > 0:
        table = []
        for episode in episodes:
            table.append(
                safe_format(
                    formats["discussion"],
                    episode=episode.number,
                    link=episode.link if episode.link else "http://localhost",
                )
            )

        num_columns = 1 + (len(table) - 1) // N_LINES
        format_head, format_align = (
            formats["discussion_header"],
            formats["discussion_align"],
        )
        table_head = (
            "|".join(num_columns * [format_head])
            + "\n"
            + "|".join(num_columns * [format_align])
        )
        table = ["|".join(table[i::N_LINES]) for i in range(N_LINES)]
        return table_head + "\n" + "\n".join(table)
    else:
        return formats["discussion_none"]


def _gen_text_aliases(db, formats, show):
    aliases = db.get_aliases(show)
    if len(aliases) == 0:
        return ""
    return safe_format(formats["aliases"], aliases=", ".join(aliases))


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def safe_format(s, **kwargs):
    """
    A safer version of the default str.format(...) function.
    Ignores unused keyword arguments and unused '{...}' placeholders instead of throwing a KeyError.
    :param s: The string being formatted
    :param kwargs: The format replacements
    :return: A formatted string
    """
    return s.format_map(_SafeDict(**kwargs))
