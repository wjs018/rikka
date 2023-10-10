import logging
from logging import info, exception, debug

import requests
import yaml
import time

import data.database as db
import module_update
from module_episode import _fetch_upcoming_episodes
from helper_functions import URL

logging.basicConfig(level=logging.INFO)


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


if __name__ == "__main__":
    # Testing stuff

    # Testing database setup
    # db_file = "database.sqlite"
    # myuri_db = db.open_database(db_file)
    # myuri_db.setup_tables()

    # # Testing add module
    # media_id = 154587
    # raw_show = module_update.get_show_info(media_id=media_id)

    # db_id = myuri_db.add_show(raw_show=raw_show, commit=True)

    # yaml_file = "season_configs/fall_2023.yaml"

    # info("Opening yaml file {}".format(yaml_file))

    # try:
    #     with open(yaml_file, "r", encoding="UTF-8") as f:
    #         parsed = yaml.safe_load(f)
    # except yaml.YAMLError:
    #     exception("Failed to parse edit file")

    # info(
    #     "Found {} enabled shows and {} disabled shows".format(
    #         len(parsed["enabled"]), len(parsed["disabled"])
    #     )
    # )

    # for show_id in parsed["enabled"]:
    #     debug("Found enabled show id {}".format(show_id))

    show_id = 154587

    upcoming = _fetch_upcoming_episodes(show_id=show_id, ratelimit=60)

    print(upcoming[0])
