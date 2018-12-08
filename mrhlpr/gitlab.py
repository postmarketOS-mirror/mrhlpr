# Copyright 2018 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
""" GitLab related functions on top of git. """

import hashlib
import urllib.parse
import urllib.request
import os
import shutil
import json
import logging

from . import git


def download_json(pathname, no_cache=False):
    """ Download and parse JSON from an API, with a cache.
        :pathname: gitlab URL pathname (without the usual prefix)
        :no_cache: download again, even if already cached
        :returns: parsed JSON """
    url = parse_git_origin()["api"] + pathname

    # Prepare cache
    cache_dir = os.getenv("HOME") + "/.cache/mrhlpr/http"
    cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    cache_file = cache_dir + "/" + cache_key
    os.makedirs(cache_dir, exist_ok=True)

    # Check the cache
    if os.path.exists(cache_file) and not no_cache:
        logging.debug("Download " + url + " (cached)")
    else:
        print("Download " + url)
        # Save to temp file
        temp_file = cache_file + ".tmp"
        with urllib.request.urlopen(url) as response:
            with open(temp_file, "wb") as handle:
                shutil.copyfileobj(response, handle)

        # Pretty print JSON (easier debugging)
        with open(temp_file, "r") as handle:
            parsed = json.load(handle)
        with open(temp_file, "w") as handle:
            handle.write(json.dumps(parsed, indent=4))

        # Replace cache file
        if os.path.exists(cache_file):
            os.remove(cache_file)
        os.rename(temp_file, cache_file)

    # Parse JSON from the cache file
    logging.debug(" -> " + cache_file)
    with open(cache_file, "r") as handle:
        return json.load(handle)


def parse_git_origin():
    """ Parse the origin remote's URL, so it can easily be used in API calls.
        :returns: a dict like the following:
                  {"api": "https://gitlab.com/api/v4",
                   "api_project_id": "postmarketOS%2Fmrhlpr",
                   "full": "git@gitlab.com:postmarketOS/mrhlpr.git",
                   "project": "postmarketOS",
                   "project_id": "postmarketOS/mrhlpr",
                   "host": "gitlab.com"} """
    # Try to get the URL
    url = git.get_remote_url()
    if not url:
        print("Not inside a git repository, or no 'origin' remote configured.")
        exit(1)

    # Find the host (gitlab.com only so far)
    prefixes = ["git@gitlab.com:", "https://gitlab.com/"]
    host = None
    rest = None
    for prefix in prefixes:
        if url.startswith(prefix):
            host = "gitlab.com"
            rest = url[len(prefix):]
    if not host:
        print("Failed to extract gitlab server from: " + url)
        exit(1)

    # project_id: remove ".git" suffix
    project_id = rest
    if project_id.endswith(".git"):
        project_id = project_id[:-1*len(".git")]

    # API URL parts
    api = "https://" + host + "/api/v4"
    api_project_id = urllib.parse.quote_plus(project_id)

    # Return everything
    return {"api": api,
            "api_project_id": api_project_id,
            "full": url,
            "project": project_id.split("/", 1)[0],
            "project_id": project_id,
            "host": host}
