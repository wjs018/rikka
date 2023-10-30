"""Module to find and make discussion threads for show episodes."""

import time
import requests

from logging import debug, info, error

import lemmy
from config import min_ns, api_call_times
from helper_functions import URL
from data.models import (
    UpcomingEpisode,
    UnprocessedShow,
    str_to_showtype,
    Megathread,
    Episode,
)


paged_airing_query = """
query ($page: Int, $start: Int, $end: Int) {
  Page(page: $page, perPage: 25) {
    pageInfo {
      hasNextPage
    }
    airingSchedules(airingAt_greater: $start, airingAt_lesser: $end, sort: TIME) {
      airingAt
      episode
      media {
        id
        idMal
        title {
          romaji
          english
        }
        format
        countryOfOrigin
        source
        synonyms
        isAdult
        status
        duration
      }
    }
  }
}
"""

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
    info(
        "Fetching all upcoming episodes from AniList for the next {} days.".format(
            config.days
        )
    )
    result = _add_update_upcoming_episodes(db=db, config=config)

    info(
        "Found {} upcoming episodes and discovered {} new shows".format(
            result[0], result[1]
        )
    )

    # Check for episodes in UpcomingEpisodes table that have air dates prior to program
    # runtime
    info("Checking for episodes that have aired.")
    current_time = int(time.time())
    aired = _get_aired_episodes(db=db, current_time=current_time)
    info("Found {} episodes that have aired.".format(len(aired)))

    # For each aired episode, check if there is a previous thread
    for episode in aired:
        info("Processing aired episode {}".format(episode))
        handled = _handle_episode_post(db, config, episode)

        if handled:
            debug("Successfully processed episode, editing posts")
            show = db.get_show(episode.media_id)
            show_episodes = db.get_episodes(show)
            show_megathread = db.get_latest_megathread(episode.media_id)

            edit_history_length = int(4 * 13 / 2)

            if len(show_episodes) > 0:
                show_episodes.sort(key=lambda x: x.number)

                for editing_episode in show_episodes[-edit_history_length:]:
                    if lemmy.is_comment_url(editing_episode.link):
                        continue

                    _edit_post(
                        config, db, editing_episode, editing_episode.link, config.submit
                    )

            if show_megathread:
                _edit_megathread(
                    config, db, episode, show_megathread.post_url, config.submit
                )
        else:
            error("Problem handling aired episode {}".format(episode))


def _add_update_upcoming_episodes(db, config):
    """
    Queries AniList for the airing schedule and updates the database with upcoming
    episodes. Returns list of shows that episodes belong to.

        Returns:

    """

    # Initialize things to prep for api calls
    ratelimit = config.ratelimit
    days = config.days

    found_episodes = []
    found_shows = []
    new_shows = 0
    new_episodes = 0
    page = 1
    start = int(time.time())
    end = start + days * 86400

    retries = {}

    # Make the api calls, allowing up to three retries
    while True:
        response = _get_airing_schedule(page, start, end, ratelimit=ratelimit)

        if response == "bad response":
            debug(
                "Bad response when getting upcoming episodes. Tried {} times".format(
                    retries.get(page, 0)
                )
            )

            retries[page] = retries.get(page, 0) + 1

            if retries[page] >= 3:
                debug(
                    "Retried {} times. Skipping and proceeding.".format(retries[page])
                )
                page += 1

            continue

        found_episodes.extend(response[1])
        found_shows.extend(response[2])

        if not response[0]:
            break

        page += 1

    # Get list of already enabled shows from database
    enabled_show_ids = []
    enabled_shows = db.get_shows()
    for show in enabled_shows:
        enabled_show_ids.append(show.id)

    # Initialize things to filter out unwanted shows
    countries = config.countries
    types = config.new_show_types
    discovery = config.show_discovery

    # Filter out shows not matching show type or country of origin, add matching shows
    if discovery:
        for show in found_shows:
            if show["id"] in enabled_show_ids:
                continue
            elif (
                show["countryOfOrigin"] in countries
                and str_to_showtype(show["format"]) in types
            ):
                debug("Found new show {}. Adding to database.".format(show["id"]))

                parsed_show = UnprocessedShow(
                    media_id=show["id"],
                    id_mal=show["idMal"],
                    name=show["title"]["romaji"],
                    name_en=show["title"]["english"],
                    more_names=show["synonyms"],
                    show_type=show["format"],
                    has_source=int(show["source"] != "ORIGINAL"),
                    is_nsfw=int(show["isAdult"]),
                    is_airing=True,
                )

                db.add_show(parsed_show)
                new_shows += 1

                for alias in show["synonyms"]:
                    db.add_alias(show["id"], alias)

                enabled_show_ids.append(show["id"])

    # Now with a full list of enabled show ids, add upcoming episodes for those shows
    for episode in found_episodes:
        if episode.media_id not in enabled_show_ids:
            continue

        db.add_upcoming_episode(episode)
        new_episodes += 1

    return [new_episodes, new_shows]


def _get_airing_schedule(page, start, end, ratelimit=60):
    """
    Queries the AniList api for episodes airing between the start and end times given.
    Also need to specify the page of results to return (up to 25 results per page)

        Parameters:
            page            The page of results to fetch from the api. Up to 25 results
                            per page.
            start           The timestamp that the airing time must be greater than to be
                            included in the results
            end             The timestamp that the airing time must be less than to be
                            included in the results

        Returns -> List:
            result[0]       The first returned item is a boolean representing whether
                            whether there is another page of results or not. This is
                            pulled from the api.
            result[1]       The second element of the returned list is a list of all the
                            found episodes as UpcomingEpisode objects.
            result[2]       The last element of the returned list is a list of all the
                            unparsed media entries for the upcoming episodes
    """

    variables = {"page": page, "start": start, "end": end}

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
        debug("Making request to AniList for airing times of upcoming shows")
        debug("Current length of deque is {}".format(len(api_call_times)))
        api_call_times.appendleft(time.time_ns())
        response = requests.post(
            URL,
            json={"query": paged_airing_query, "variables": variables},
            timeout=5.0,
        )
    except:
        error("Bad response from request for airing times")
        return "bad response"

    response = response.json()
    has_next_page = response["data"]["Page"]["pageInfo"]["hasNextPage"]

    found_episodes_resp = response["data"]["Page"]["airingSchedules"]

    found_shows = []
    found_episodes = []

    for episode in found_episodes_resp:
        media_id = episode["media"]["id"]
        episode_num = episode["episode"]
        air_time = episode["airingAt"]

        if episode["media"]["duration"]:
            air_time += 60 * episode["media"]["duration"]

        found_episodes.append(UpcomingEpisode(media_id, episode_num, air_time))

        found_shows.append(episode["media"])

    return_list = [has_next_page]
    return_list.append(found_episodes)
    return_list.append(found_shows)

    return return_list


def _handle_episode_post(db, config, episode):
    """
    Basic flow of how this function works:

    1. Check if show has past episode threads
        A. If not, create a standalone post for the new episode
        B. If so, check engagement on most recent episode's post
            a. If thresholds met, then create a standalone post for the episode
            b. If thresholds not met, then divert episode post to a megathread
                i. If an existing megathread is available, then post top-level
                    comment to that megathread
                ii. If an existing megathread is not available, then create a
                    new megathread and then a top-level comment in that thread
    """

    # First, fetch previous episode, if it exists
    show = db.get_show(id=episode.media_id)
    most_recent = db.get_latest_episode(show)

    # Next, if this is a new show, make the post and return true
    if not most_recent:
        info("No previous episode found, making a new standalone post.")
        created_post = _create_standalone_post(db, config, episode)
        if created_post:
            return True
        return False

    # This is not a new show, so check past episode's engagement
    debug("Previous episode found, checking engagement metrics.")
    min_engagement = [config.min_upvotes, config.min_comments]
    engagement = lemmy.get_engagement(episode.link)
    met_threshold = all(list(x >= y for x, y in zip(engagement, min_engagement)))

    # If we met the threshold, disable megathread status, make the post, and return True
    if met_threshold:
        info("Engagement metrics met. Creating a new standalone post.")
        db.set_megathread_status(episode.media_id, False)
        created_post = _create_standalone_post(db, config, episode)
        if created_post:
            return True
        return False

    # Did not meet thresholds, so set megathread status and handle the megathread
    info("Placing episode discussion in a megathread.")
    db.set_megathread_status(episode.media_id, True)

    megathread_handled = _handle_megathread(db, config, episode)

    if megathread_handled:
        return True

    return False


def _create_standalone_post(db, config, episode):
    """Create a standalone episode discussion post."""

    title, body = _create_post_contents(config, db, episode)

    post_url = _create_post(config, title, body, submit=config.submit)

    if post_url:
        post_url.replace("http:", "https:")
        info("Post made at url: {}".format(post_url))
        info("Post title:\n{}".format(title))

        # Add episode to the Episodes table
        db.add_episode(episode.media_id, episode.number, post_url)

        # Remove the just-posted episode from the UpcomingEpisodes table
        db.remove_upcoming_episode(episode.media_id, episode.number)

        # Post created, return True
        return True

    error("Problem making standalone discussion post.")
    return False


def _handle_megathread(db, config, episode):
    """Logic to handle megathreads and posts in them."""

    megathread = db.get_latest_megathread(episode.media_id)

    if not megathread:
        info("Creating a new megathread")
        megathread = _create_megathread(db, config, episode)
        if not megathread:
            return False

    # There is a previous megathread, check number of episodes it has
    if megathread.num_episodes >= config.megathread_episodes:
        info("Maximum number of episodes in past megathread, creating a new one")
        megathread = _create_megathread(db, config, episode)
        if not megathread:
            return False

    # With a megathread available, make comment in the thread
    megathread_comment = _format_post_text(
        config, db, episode, config.megathread_comment
    )

    if config.submit:
        info("Creating top level comment in the megathread")
        response = lemmy.submit_text_comment(megathread.post_url, megathread_comment)
        if response:
            link = lemmy.get_commentlink_from_id(response["id"])
            info("Comment made at {}".format(link))

            debug("Writing new episode to database")
            db.add_episode(episode.media_id, episode.number, link)
            db.increment_num_episodes(megathread)
            db.remove_upcoming_episode(episode.media_id, episode.number)

            return True

        error("Failed to create comment in megathread")

    return False


def _create_megathread(db, config, episode, number=1):
    """Creates a new megathread for the given episode's show."""

    title = _create_megathread_title(config, db, episode)
    title = _format_post_text(config, db, episode, title)

    info("Post title:\n{}".format(title))

    body = _format_post_text(config, db, episode, config.megathread_body)

    if config.submit:
        new_post = lemmy.submit_text_post(config.l_community, title, body)
        if new_post:
            url = lemmy.get_shortlink_from_id(new_post["id"])
            info("Megathread made at {}".format(url))

            debug("Writing megathread to database")
            megathread = Megathread(episode.media_id, number, url, 0)
            db.add_megathread(megathread)

            return megathread

        error("Failed to submit megathread post")

    return False


def _create_megathread_title(config, db, episode):
    """Create the title for a megathread"""

    show = db.get_show(episode.media_id)

    if show.name_en:
        title = config.megathread_title_with_en
    else:
        title = config.megathread_title

    return title


def _edit_megathread(config, db, episode, url, submit=True):
    """Edit the contents of a megathread."""

    body = _format_post_text(config, db, episode, config.megathread_body)

    if submit:
        lemmy.edit_text_post(url, body)
    return None


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
    """Make the discussion post contents for the aired episode."""

    post_title = _create_post_title(config, db, aired_episode)
    post_title = _format_post_text(config, db, aired_episode, post_title)

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
