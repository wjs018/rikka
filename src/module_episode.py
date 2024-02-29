"""Module to find and make discussion threads for show episodes."""

import time
import requests

from logging import debug, info, error
from datetime import datetime, timezone

import lemmy
from config import min_ns, api_call_times
from helper_functions import (
    URL,
    add_update_shows_by_id,
    meet_discovery_criteria,
    safe_format,
)
from data.models import (
    UpcomingEpisode,
    str_to_showtype,
    Megathread,
    ShowType,
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


def main(config, db, *args, **kwargs):
    """Main function for episode module"""

    manual_creation = False

    # First check if this is a manual thread addition
    if len(args) not in [0, 2]:
        error(
            "Wrong number of args for episode module. Found {} args".format(len(args))
        )
        raise Exception("Wrong number of arguments")
    elif len(args) == 2:
        # Manual episode thread creation
        debug("Manually creating a discussion thread")

        if args[0].isdigit():
            debug("Fetching show with id {} from database".format(args[0]))
            show = db.get_show(args[0])
        else:
            error("First argument should be show's AniList id number")
            raise Exception("Improper first argument")

        if not show:
            error("Show doesn't exist in database, add it first")
            raise Exception("Nonexistent show in database")

        if not str(args[1]).isdigit():
            error("Second argument must be episode number")
            raise Exception("Improper second argument")

        # Getting to this point means we can create the thread
        current_time = datetime.now(timezone.utc)
        manual_episode = UpcomingEpisode(args[0], args[1], current_time)

        manual_creation = True

    lemmy.init_lemmy(config)

    if not manual_creation:
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

        # Check for episodes in UpcomingEpisodes table that have air dates prior to
        # program runtime
        info("Checking for episodes that have aired.")
        current_time = int(time.time())
        aired = _get_aired_episodes(db=db, current_time=current_time)
        info("Found {} episodes that have aired.".format(len(aired)))
    else:
        aired = [manual_episode]

    # Clear out old ignored episodes from the database
    db.remove_old_ignored_episodes(num_days=config.episode_retention)

    # For each aired episode, check if there is a previous thread
    for episode in aired:
        info("Processing aired episode {}".format(episode))
        handled = _handle_episode_post(
            db, config, episode, ignore_engagement=manual_creation
        )

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

                    if not bool(editing_episode.can_edit):
                        continue

                    if config.submit_image == "banner":
                        banner_image = db.get_banner_image(editing_episode.media_id)
                        if banner_image:
                            image_url = banner_image.image_link
                        else:
                            image_url = None
                    elif config.submit_image == "cover":
                        cover_image = db.get_cover_image(editing_episode.media_id)
                        if cover_image:
                            image_url = cover_image.image_link
                        else:
                            image_url = None
                    else:
                        image_url = None

                    _edit_post(
                        config,
                        db,
                        editing_episode,
                        editing_episode.link,
                        config.submit,
                        image_url=image_url,
                    )

            if show_megathread:
                if config.submit_image == "banner":
                    banner_image = db.get_banner_image(show_megathread.media_id)
                    if banner_image:
                        image_url = banner_image.image_link
                    else:
                        image_url = None
                elif config.submit_image == "cover":
                    cover_image = db.get_cover_image(show_megathread.media_id)
                    if cover_image:
                        image_url = cover_image.image_link
                    else:
                        image_url = None
                else:
                    image_url = None

                _edit_megathread(
                    config,
                    db,
                    episode,
                    show_megathread.post_url,
                    config.submit,
                    image_url=image_url,
                )
        else:
            error("Problem handling aired episode {}".format(episode))


def _add_update_upcoming_episodes(db, config):
    """
    Queries AniList for the airing schedule and updates the database with upcoming
    episodes.

        Returns -> List:
            result[0]           Total number of upcoming episodes found and added or
                                updated in the database through the api call.
            result[1]           Number of new shows found and added to the database.
    """

    # Initialize things to prep for api calls
    ratelimit = config.ratelimit
    days = config.days

    found_episodes = []
    found_shows = []
    new_show_list = []
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
    disabled_show_ids = []
    enabled_shows = db.get_shows()
    disabled_shows = db.get_shows(enabled="disabled")
    for show in enabled_shows:
        enabled_show_ids.append(show.id)
    for show in disabled_shows:
        disabled_show_ids.append(show.id)

    # Initialize things to filter out unwanted shows
    discovery = config.show_discovery

    # Filter out shows not matching show type or country of origin, add matching shows
    if discovery:
        for show in found_shows:
            if meet_discovery_criteria(db, config, show):
                debug("Found new show {}. Adding to database.".format(show["id"]))
                new_show_list.append(show["id"])

        added = add_update_shows_by_id(
            db, new_show_list, enabled=config.discovery_enabled
        )
        new_shows += added
        if config.discovery_enabled:
            enabled_show_ids = enabled_show_ids + new_show_list
        else:
            disabled_show_ids = disabled_show_ids + new_show_list

    # Now with a full list of shows in the database, add the upcoming episodes
    potential_shows = enabled_show_ids + disabled_show_ids
    for episode in found_episodes:
        if episode.media_id in potential_shows:
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

    try:
        has_next_page = response["data"]["Page"]["pageInfo"]["hasNextPage"]
    except KeyError:
        error("Bad response from AniList api from request for airing times")
        return "bad response"

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


def _handle_episode_post(db, config, episode, ignore_engagement=False):
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

    created_post = False
    megathread_handled = False
    disabled_show_ids = []
    disabled_shows = db.get_shows(enabled="disabled")
    for show in disabled_shows:
        disabled_show_ids.append(show.id)

    # First, fetch previous episode, if it exists
    show = db.get_show(id=episode.media_id)
    most_recent = db.get_latest_episode(show)

    # Check if the show is disabled. If so, create the ignored episode
    if episode.media_id in disabled_show_ids:
        info(
            "Show id {} marked as disabled. Ignoring aired episode.".format(
                episode.media_id
            )
        )
        db.add_ignored_episode(episode)
        db.remove_upcoming_episode(episode.media_id, episode.number)
        return False

    # Next, if this is a new show, make the post and return true
    if not most_recent:
        info("No previous episode found, making a new standalone post.")
        created_post = _create_standalone_post(db, config, episode)
        if created_post:
            return True
        return False

    # Next, if this is a thread being manually created, ignore metrics
    if ignore_engagement:
        info("Manual thread creation, ignoring engagement metrics")
        created_post = _create_standalone_post(db, config, episode)
        if created_post:
            return True
        return False

    # This isn't a new show, check if the previous episode was posted too recently for
    # engagement to be considered
    most_recent_time = lemmy.get_publish_time(most_recent.link)
    current_time = datetime.now(timezone.utc)
    elapsed = current_time - most_recent_time
    engagement_lag = config.engagement_lag * 3600

    if elapsed.total_seconds() <= engagement_lag:
        # Not enough time has passed since the last post, only put in a megathread if
        # previous post was also in a megathread
        info("Not enough elapsed time since last post. Ignoring engagement metrics.")
        if lemmy.is_comment_url(most_recent.link):
            megathread_handled = _handle_megathread(db, config, episode)
        elif lemmy.is_post_url(most_recent.link):
            created_post = _create_standalone_post(db, config, episode)

        if megathread_handled:
            return True
        elif created_post:
            return True
        else:
            return False

    # This is not a new show, so check past episode's engagement
    debug("Previous episode found, checking engagement metrics.")
    min_engagement = [config.min_upvotes, config.min_comments]
    engagement = lemmy.get_engagement(most_recent.link)
    met_threshold = all(list(x >= y for x, y in zip(engagement, min_engagement)))

    # If we met the threshold, disable megathread status, make the post, and return True
    if met_threshold:
        info("Engagement metrics met. Creating a new standalone post.")
        db.set_megathread_status(episode.media_id, False)
        created_post = _create_standalone_post(db, config, episode)
        if created_post:
            return True
        return False

    # Did not meet thresholds, check if show should be disabled
    if config.disable_inactive:
        db.set_show_enabled(show, enabled=False)
        return True

    # Did not meet thresholds, so set megathread status and handle the megathread
    info("Placing episode discussion in a megathread.")
    db.set_megathread_status(episode.media_id, True)

    megathread_handled = _handle_megathread(db, config, episode)

    if megathread_handled:
        return True

    return False


def _create_standalone_post(db, config, episode):
    """Create a standalone episode discussion post."""

    show = db.get_show(episode.media_id)
    nsfw = bool(show.is_nsfw)

    title, body = _create_post_contents(config, db, episode)

    if config.submit_image == "banner":
        banner_image = db.get_banner_image(episode.media_id)
        if banner_image:
            url = banner_image.image_link
        else:
            url = None
    elif config.submit_image == "cover":
        cover_image = db.get_cover_image(episode.media_id)
        if cover_image:
            url = cover_image.image_link
        else:
            url = None
    else:
        url = None

    post_url = _create_post(config, title, body, nsfw, submit=config.submit, url=url)

    if post_url:
        post_url.replace("http:", "https:")
        info("Post made at url: {}".format(post_url))
        info("Post title:\n{}".format(title))

        post_time = lemmy.get_publish_time(post_url)
        post_time = int(time.mktime(post_time.timetuple()))

        # Add episode to the Episodes table
        db.add_episode(
            episode.media_id,
            episode.number,
            post_url,
            can_edit=True,
            creation_time=post_time,
        )

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
        number = megathread.thread_num + 1
        megathread = _create_megathread(db, config, episode, number)
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

            post_time = lemmy.get_publish_time(link)
            post_time = int(post_time.timetuple())

            debug("Writing new episode to database")
            db.add_episode(
                episode.media_id,
                episode.number,
                link,
                can_edit=True,
                creation_time=post_time,
            )
            db.increment_num_episodes(megathread)
            db.remove_upcoming_episode(episode.media_id, episode.number)

            return True

        error("Failed to create comment in megathread")

    return False


def _create_megathread(db, config, episode, number=1):
    """Creates a new megathread for the given episode's show."""

    show = db.get_show(episode.media_id)
    nsfw = bool(show.is_nsfw)

    title = _create_megathread_title(config, db, episode)
    title = _format_post_text(config, db, episode, title, thread_num=number)

    if len(title) >= 198:
        title = _create_megathread_title(config, db, episode, include_english=False)
        title = _format_post_text(config, db, episode, title, thread_num=number)
        title = title[:198]

    info("Post title:\n{}".format(title))

    body = _format_post_text(config, db, episode, config.megathread_body)

    if config.submit_image == "banner":
        banner_image = db.get_banner_image(episode.media_id)
        if banner_image:
            url = banner_image.image_link
        else:
            url = None
    elif config.submit_image == "cover":
        cover_image = db.get_cover_image(episode.media_id)
        if cover_image:
            url = cover_image.image_link
        else:
            url = None
    else:
        url = None

    if config.submit:
        new_post = lemmy.submit_text_post(
            config.l_community, title, body, nsfw, url=url
        )
        if new_post:
            megathread_url = lemmy.get_shortlink_from_id(new_post["id"])
            info("Megathread made at {}".format(megathread_url))

            debug("Writing megathread to database")
            megathread = Megathread(episode.media_id, number, megathread_url, 0)
            db.add_megathread(megathread)

            return megathread

        error("Failed to submit megathread post")

    return False


def _create_megathread_title(config, db, episode, include_english=True):
    """Create the title for a megathread"""

    show = db.get_show(episode.media_id)

    if show.name_en and include_english:
        title = config.megathread_title_with_en
    else:
        title = config.megathread_title

    return title


def _edit_megathread(config, db, episode, url, submit=True, image_url=None):
    """Edit the contents of a megathread."""

    body = _format_post_text(config, db, episode, config.megathread_body)

    if submit:
        lemmy.edit_text_post(
            url, body, link_url=image_url, overwrite_url=config.overwrite_url
        )
    return None


def _get_aired_episodes(db, current_time):
    """Get list of episodes that aired."""

    debug("Querying database for upcoming episodes that have aired.")
    aired = db.get_aired_episodes(current_time)

    debug("Found {} episodes that have aired in the database.".format(len(aired)))

    return aired


def _create_post(config, title, body, nsfw, submit=True, url=None):
    """Creates the discussion post on Lemmy."""

    if submit:
        new_post = lemmy.submit_text_post(
            config.l_community, title, body, nsfw, url=url
        )
        print("here")
        if new_post is not None:
            debug("Post successful")
            return lemmy.get_shortlink_from_id(new_post["id"])

        error("Failed to submit post")

    return None


def _edit_post(config, db, aired_episode, url, submit=True, image_url=None):
    """Edits the table of links in a discussion post."""

    _, body = _create_post_contents(config, db, aired_episode, submit=submit)

    if submit:
        lemmy.edit_text_post(
            url, body, link_url=image_url, overwrite_url=config.overwrite_url
        )
    return None


def _create_post_contents(config, db, aired_episode, submit=True, include_english=True):
    """Make the discussion post contents for the aired episode."""

    show = db.get_show(aired_episode.media_id)

    if show.type == ShowType.MOVIE.value:
        post_title = _create_movie_post_title(
            config, db, aired_episode, include_english=include_english
        )
        post_title = _format_post_text(config, db, aired_episode, post_title)

        if len(post_title) >= 198:
            post_title = _create_movie_post_title(
                config, db, aired_episode, include_english=False
            )
            post_title = _format_post_text(config, db, aired_episode, post_title)

        post_body = _format_post_text(config, db, aired_episode, config.movie_post_body)
    else:
        post_title = _create_post_title(
            config, db, aired_episode, include_english=include_english
        )
        post_title = _format_post_text(config, db, aired_episode, post_title)

        if len(post_title) >= 198:
            post_title = _create_post_title(
                config, db, aired_episode, include_english=False
            )
            post_title = _format_post_text(config, db, aired_episode, post_title)

        post_body = _format_post_text(config, db, aired_episode, config.post_body)

    return post_title[:198], post_body


def _create_post_title(config, db, aired_episode, include_english=True):
    """Construct the post title"""

    show = db.get_show(aired_episode.media_id)

    if show.name_en and include_english:
        title = config.post_title_with_en
    else:
        title = config.post_title

    return title


def _create_movie_post_title(config, db, aired_episode, include_english=True):
    """Construct the post title for a movie post"""

    show = db.get_show(aired_episode.media_id)

    if show.name_en and include_english:
        title = config.movie_title_with_en
    else:
        title = config.movie_title

    return title


def _format_post_text(config, db, aired_episode, text, **kwargs):
    """Format the text to substitute placeholders."""

    formats = config.post_formats

    show = db.get_show(aired_episode.media_id)

    if "thread_num" in kwargs:
        megathread_number = kwargs.get("thread_num")
    else:
        megathread_number = "1"

    if "{spoiler}" in text:
        text = safe_format(text, spoiler=_gen_text_spoiler(formats, show))
    if "{discussions}" in text:
        text = safe_format(text, discussions=_gen_text_discussions(db, formats, show))
    if "{aliases}" in text:
        text = safe_format(text, aliases=_gen_text_aliases(db, formats, show))
    if "{links}" in text:
        text = safe_format(text, links=_gen_text_links(db, formats, show))
    if "{banner}" in text:
        text = safe_format(text, banner=_gen_text_banner(db, formats, show))
    if "{cover}" in text:
        text = safe_format(text, cover=_gen_text_cover(db, formats, show))

    text = safe_format(
        text,
        show_name=show.name,
        show_name_en=show.name_en,
        episode=aired_episode.number,
        megathread_number=megathread_number,
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


def _gen_text_links(db, formats, show):
    links = db.get_external_links(show.id)
    if len(links) == 0:
        return ""

    link_str = ""

    for link in links:
        link_str += link.to_markdown()

    return safe_format(formats["links"], external_links=link_str)


def _gen_text_banner(db, formats, show):
    banner_image = db.get_banner_image(show.id)
    if not banner_image:
        return ""

    return banner_image.to_markdown()


def _gen_text_cover(db, formats, show):
    cover_image = db.get_cover_image(show.id)
    if not cover_image:
        return ""

    return cover_image.to_markdown()
