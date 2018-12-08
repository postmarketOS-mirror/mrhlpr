# Copyright 2018 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
""" Simple lookup table on disk for local (host, project, branch) to MR ID. """

import json
import os
import logging


def load():
    """ :returns: dict of the loaded lookup table, looks like:
                  {"gitlab.com":
                    {"postmarketOS/pmaports":
                      {"sailfish": 66,
                       "grate-driver": 67}}} """
    path = os.getenv("HOME") + "/.cache/mrhlpr/mrdb.json"
    if not os.path.exists(path):
        return {}
    with open(path, "r") as handle:
        return json.load(handle)


def get(host, project_id, branch):
    """ :returns: the MR-ID or None """
    db = load()
    if (host in db
            and project_id in db[host]
            and branch in db[host][project_id]):
        return db[host][project_id][branch]
    return None


def set(host, project_id, branch, mr_id):
    """ Save the MR-ID for the given host, project_id, branch to the database.
        The database file gets rewritten from scratch each time, we don't
        really write often into it anyway, and this keeps the code simple. """
    # Create path
    path = os.getenv("HOME") + "/.cache/mrhlpr/mrdb.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Add structure
    db = load()
    if host not in db:
        db[host] = {}
    if project_id not in db[host]:
        db[host][project_id] = {}

    # Skip if unchanged
    if (branch in db[host][project_id] and
            db[host][project_id][branch] == mr_id):
        return

    # Update the file
    logging.debug(str([host, project_id, branch]) + " set to " + str(mr_id))
    db[host][project_id][branch] = mr_id
    with open(path, "w") as handle:
        handle.write(json.dumps(db, indent=4))
