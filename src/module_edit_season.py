"""Module to get list of series releasing in a given year and season."""

import requests
import time

from logging import debug, info, error
from helper_functions import URL, add_update_shows_by_id, meet_discovery_criteria
from config import min_ns, api_call_times

SEASON_LIST = ["WINTER", "SPRING", "SUMMER", "FALL"]

paged_season_query = """
query ($page: Int, $season: MediaSeason, $seasonYear: Int) {
  Page (page: $page, perPage: 50) {
    pageInfo {
      hasNextPage
    }
    media (season: $season, seasonYear: $seasonYear) {
      id
      format
      isAdult
      countryOfOrigin
    }
  }
}
"""


def main(config, db, *args, **kwargs):
    """Main function for the edit_season module."""

    # First, check input arguments and raise and exception if there is a problem
    throw_exception = False

    if len(args) != 2:
        error("Incorrect number of arguments for edit_season module.")
        throw_exception = True

    if not isinstance(args[0], str):
        error("First argument must be a string for edit_season module")
        throw_exception = True

    if not args[1].isdigit():
        error("Second argument must be a positive int for edit_season module")
        throw_exception = True

    if args[0].upper() not in SEASON_LIST:
        error("Season must be any of WINTER, SPRING, SUMMER, or FALL")
        throw_exception = True

    if throw_exception:
        raise Exception("Inputs to edit_season module not input correctly")

    # Arguments seem to be amenable to proceeding
    season = args[0].upper()
    year = args[1]

    found_shows = []
    ratelimit = config.ratelimit
    page = 1
    retries = {}

    # Make the api calls, allowing up to three retries
    while True:
        response = _get_season_shows(
            db, config, page, season, year, ratelimit=ratelimit
        )

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

        found_shows.extend(response[1])

        if not response[0]:
            break

        page += 1

    info("{} shows found meeting criteria for the season".format(len(found_shows)))

    shows_added = add_update_shows_by_id(db, show_ids=found_shows, ratelimit=ratelimit)

    info("{} shows added to the database".format(shows_added))


def _get_season_shows(db, config, page, season, year, ratelimit=60):
    """
    Fetch the shows airing in a given season for a given year from the AniList api. The
    page is used to facilitate paginating many results.

        Parameters:
            db              DatabaseDatabase object
            config          Config object
            page            The page of results to fetch from the api. Up to 50 results
                            per page.
            season          The name of the season to look for shows
            year            The year to look for shows

        Returns -> List:
            result[0]       The first returned item is a boolean representing whether
                            whether there is another page of results or not. This is
                            pulled from the api.
            result[1]       The second element of the returned list is a list of all the
                            ids of the shows returned by the api that meet the
                            discovery criteria
    """

    variables = {"page": page, "season": season, "seasonYear": year}

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
            json={"query": paged_season_query, "variables": variables},
            timeout=5.0,
        )
    except:
        error("Bad response from request for airing times")
        return "bad response"

    response = response.json()
    has_next_page = response["data"]["Page"]["pageInfo"]["hasNextPage"]
    found_shows_resp = response["data"]["Page"]["media"]

    discovered_shows = []

    for found_show in found_shows_resp:
        if meet_discovery_criteria(db, config, found_show):
            discovered_shows.append(found_show["id"])

    return [has_next_page, discovered_shows]
