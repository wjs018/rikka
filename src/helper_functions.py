"""Module with common functions accessed by multiple modules."""

import time
import requests

from logging import debug, info, error
from requests.exceptions import JSONDecodeError
from data.models import UnprocessedShow, ExternalLink, Image, str_to_showtype
from config import min_ns, api_call_times

URL = "https://graphql.anilist.co"

paged_show_query = """
query ($page: Int, $id_in: [Int]) {
  Page (page: $page, perPage: 50) {
    pageInfo {
      hasNextPage
    }
    media (id_in: $id_in) {
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
      externalLinks {
        type
        site
        language
        url
      }
      bannerImage
      coverImage {
        extraLarge
      }
    }
  }
}
"""


def add_update_shows_by_id(
    db, show_ids, ratelimit=60, enabled=True, ignore_enabled=False, get_raw_shows=False
):
    """
    Either adds shows in the given id list if it isn't already in the database, or
    updates an existing show if it is already in the database with fresh info from
    AniList.

    Returns the number of shows updated.
    """

    page = 1
    raw_shows = []
    retries = {}

    while True:
        response = _get_shows_info(page, show_ids, ratelimit)

        if response == None:
            break

        if response == "bad response":
            debug(
                "Bad response when getting upcoming episodes. Tried {} times".format(
                    retries.get(page, 0)
                )
            )

            retries[page] = retries.get(page, 0) + 1

            if retries[page] >= 5:
                debug(
                    "Retried {} times. Skipping and proceeding.".format(retries[page])
                )
                page += 1

            continue

        raw_shows.extend(response[1])

        if not response[0]:
            break

        page += 1

    if get_raw_shows:
        return raw_shows

    for raw_show in raw_shows:
        db_show = check_if_exists(db, raw_show.media_id)
        if db_show:
            debug("Found show in database, updating")
            db.update_show(
                raw_show.media_id, raw_show, commit=True, ignore_enabled=ignore_enabled
            )
        else:
            debug("Did not find show in database, adding it")
            db.add_show(raw_show, commit=True)

        if not enabled:
            debug("Disabling show")
            show = db.get_show(raw_show.media_id)
            db.set_show_enabled(show, enabled=False, commit=True)

        for alias in raw_show.more_names:
            debug("Adding alias for show id {} as {}".format(raw_show.media_id, alias))
            add_alias(db, raw_show.media_id, alias, commit=True)

        for link in raw_show.external_links:
            debug("Adding link for show id {}: {}".format(raw_show.media_id, link))
            db.add_external_link(link, commit=True)

        for image in raw_show.images:
            debug(
                "Adding image for show id {} at url {}".format(
                    raw_show.media_id, image.image_link
                )
            )
            db.add_image(image, commit=True)

    return len(raw_shows)


def _get_shows_info(page, show_ids, ratelimit=60):
    """
    Pulls media information from the AniList api.

        Returns -> List:
            result[0]           Boolean indicating whether there is another page of
                                results. Pulled directly from the api.
            result[1]           List of UnprocessedShow objects from the api call.
    """

    variables = {"page": page, "id_in": show_ids}

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
            json={"query": paged_show_query, "variables": variables},
            timeout=5.0,
        )
        response_test = response.json()
        if "data" not in response_test:
            error("Bad response from request for airing times")
            return "bad response"
    except:
        error("Bad response from request for airing times")
        return "bad response"

    try:
        response = response.json()
    except JSONDecodeError:
        error("Persistent bad api responses, skipping updating upcoming episodes")
        return None

    try:
        has_next_page = response["data"]["Page"]["pageInfo"]["hasNextPage"]
    except TypeError:
        error("Persistent bad api responses, skipping updating upcoming episodes")
        return None

    found_shows_resp = response["data"]["Page"]["media"]

    found_shows = []

    for show in found_shows_resp:
        media_id = show["id"]
        id_mal = show["idMal"]
        name = show["title"]["romaji"]
        name_en = show["title"]["english"]
        more_names = show["synonyms"]
        show_type = show["format"]
        has_source = int(show["source"] != "ORIGINAL")
        is_nsfw = int(show["isAdult"])
        status = show["status"]
        external_links_raw = show["externalLinks"]
        banner_image = show["bannerImage"]
        cover_image = show["coverImage"]["extraLarge"]

        external_links = []

        # Create AniList link
        anilist_url = "https://anilist.co/anime/" + str(media_id)
        anilist_link = ExternalLink(
            media_id=media_id,
            link_type="INFO",
            site="AniList",
            language="",
            url=anilist_url,
        )
        external_links.append(anilist_link)

        # Create MAL link
        if id_mal:
            mal_url = "https://myanimelist.net/anime/" + str(id_mal)
            mal_link = ExternalLink(
                media_id=media_id,
                link_type="INFO",
                site="MyAnimeList",
                language="",
                url=mal_url,
            )
            external_links.append(mal_link)

        for link in external_links_raw:
            link_type = link["type"]
            site = link["site"]
            language = link["language"]
            url = link["url"]
            external_link = ExternalLink(
                media_id=media_id,
                link_type=link_type,
                site=site,
                language=language,
                url=url,
            )
            external_links.append(external_link)

        images = []

        if banner_image:
            banner = Image(
                media_id=media_id, image_type="banner", image_link=banner_image
            )
            images.append(banner)

        if cover_image:
            cover = Image(media_id=media_id, image_type="cover", image_link=cover_image)
            images.append(cover)

        if status in ["FINISHED", "CANCELLED"]:
            status = False
        else:
            status = True

        raw_show = UnprocessedShow(
            media_id=media_id,
            id_mal=id_mal,
            name=name,
            name_en=name_en,
            more_names=more_names,
            show_type=show_type,
            has_source=has_source,
            is_nsfw=is_nsfw,
            is_airing=status,
            external_links=external_links,
            images=images,
        )

        found_shows.append(raw_show)

    return [has_next_page, found_shows]


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


def meet_discovery_criteria(db, config, media_dict):
    """
    Check if a media item returned by api call meets the discovery criteria. Will also
    return False if show already exists in database.
    """

    if not config.show_discovery:
        return False

    existing_show_ids = []
    db_shows = db.get_shows(enabled="all")
    for show in db_shows:
        existing_show_ids.append(show.id)

    countries = config.countries
    types = config.new_show_types
    media_type = str_to_showtype(media_dict["format"])

    if media_dict["id"] in existing_show_ids:
        return False

    if media_dict["isAdult"] and not config.nsfw_discovery:
        return False

    if media_dict["countryOfOrigin"] not in countries:
        return False

    if media_type not in types:
        return False

    return True


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
