# Copyright 2018 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
""" High level merge request related functions on top of git, gitlab, mrdb. """

import os
import re

from . import git
from . import gitlab
from . import mrdb


def checked_out():
    """ :returns: checked out MR ID or None """
    origin = gitlab.parse_git_origin()
    branch = git.branch_current()
    return mrdb.get(origin["host"], origin["project_id"], branch)


def get_status(mr_id, no_cache=False):
    """ Get merge request related information from the GitLab API.
        To hack on this, run mrhlpr with -v to get the cached JSON files
        location. Then you can take a look at the data returned from the API.
        :param mr_id: merge request ID
        :param no_cache: do not cache the API result for the merge request data
        :returns: a dict like:
                  {"title": "This is my first merge request",
                   "branch": "mymr",
                   "source": "ollieparanoid/mrhlpr",
                   "source_namespace": "ollieparanoid",
                   "allow_push": True,
                   "state": "merged"} """
    # Query merge request
    # https://docs.gitlab.com/ee/api/merge_requests.html
    origin = gitlab.parse_git_origin()
    url_mr = "/projects/{}/merge_requests/{}".format(origin["api_project_id"],
                                                     mr_id)
    api = gitlab.download_json(url_mr, no_cache)

    # Query source project/repository
    # https://docs.gitlab.com/ee/api/projects.html
    # Always cache this, since we don't expect the "path_with_namespace" to
    # ever change (and even if, we can keep using the old one locally).
    url_project = "/projects/" + str(api["source_project_id"])
    api_source = gitlab.download_json(url_project)

    # Allow maintainer to push
    allow_push = False
    if "allow_maintainer_to_push" in api and api["allow_maintainer_to_push"]:
        allow_push = True

    # MR initiated from same GitLab project
    if api_source["namespace"]["name"] == origin["project"]:
        allow_push = True

    # Sanity checks (don't let the API trick us into passing options to git!)
    source = api_source["path_with_namespace"]
    if (not re.compile(r"[a-zA-Z0-9_.-]*\/[a-zA-Z0-9_.-]*").match(source) or
            source.startswith("-")):
        print("Invalid source: " + source)
        exit(1)

    source_namespace = api_source["namespace"]["name"]
    if (not re.compile(r"[a-zA-Z0-9_.-]*").match(source_namespace) or
            source_namespace.startswith("-")):
        print("Invalid source_namespace: " + source_namespace)
        exit(1)

    branch = api["source_branch"]
    if (not re.compile(r"[a-zA-Z0-9/-_.]*").match(branch) or
            branch.startswith("-")):
        print("Invalid branch: " + branch)
        exit(1)

    return {"title": api["title"],
            "branch": branch,
            "source": source,
            "source_namespace": source_namespace,
            "allow_push": allow_push,
            "state": api["state"]}


def checkout(mr_id, no_cache=False, fetch=False, overwrite_remote=False):
    """ Add the MR's source repository as git remote, fetch it and checkout the
        branch used in the merge request.
        :param mr_id: merge request ID
        :param no_cache: do not cache the API result for the merge request data
        :param fetch: always fetch the source repository
        :param overwrite_remote: overwrite URLs of existing remote """
    status = get_status(mr_id, no_cache)
    remote, repo = status["source"].split("/", 2)
    origin = gitlab.parse_git_origin()
    branch = status["branch"]

    # Don't add the origin remote twice
    remote_local = remote
    if remote == origin["project"]:
        remote_local = "origin"

    # Check existing remote
    project_repo_git = "{}/{}.git".format(remote, repo)
    url = "https://" + origin["host"] + "/" + project_repo_git
    url_push = "git@" + origin["host"] + ":" + project_repo_git
    existing = git.get_remote_url(remote_local)
    if existing and existing != url:
        if overwrite_remote:
            print("Overwriting remote URL (old: '" + existing + "')")
            git.run(["remote", "set-url", remote_local, url])
            git.run(["remote", "set-url", "--push", remote_local, url_push])
        else:
            print("ERROR: Remote '" + remote_local + "' already exists and has"
                  " a different URL.")
            print()
            print("existing: " + existing)
            print("expected: " + url)
            print()
            print("If you are fine with the expected url, use 'mrhlpr checkout"
                  " " + str(mr_id) + " -o' to overwrite it.")
            print()
            print("mrhlpr will also set this pushurl: " + url_push)
            exit(1)

    # Fetch origin
    if fetch and remote != origin["project"]:
        print("Fetch " + git.get_remote_url())
        git.run(["fetch", "origin"])

    # Add missing remote
    if not existing:
        git.run(["remote", "add", remote_local, url])
        git.run(["remote", "set-url", "--push", remote_local, url_push])
        fetch = True
    if fetch:
        print("Fetch " + url)
        git.run(["fetch", remote_local])

    # Always prepend the remote before "master"
    branch_local = branch
    if branch == "master":
        branch_local = remote + "-" + branch

    # Checkout the branch
    print("Checkout " + branch_local + " from " + remote + "/" + branch)
    if branch_local in git.branches():
        # Check existing branch
        remote_existing = git.branch_remote(branch_local)
        if remote_existing != remote_local:
            print("Branch '" + branch_local + "' exists, but points to a"
                  " different remote.")
            print()
            print("existing remote: " + str(remote_existing))
            print("expected remote: " + remote_local)
            print()
            print("Consider deleting this branch and trying again:")
            print("$ git checkout master")
            print("$ git branch -D " + branch_local)
            print("$ mrhlpr checkout " + str(mr_id))
            exit(1)
        git.run(["checkout", branch_local])
    else:
        git.run(["checkout", "-b", branch_local, remote_local + "/" + branch],
                check=False)
        if git.branch_current() != branch_local:
            print()
            print("ERROR: checkout failed.")
            print("* Does that branch still exist?")
            print("* Maybe the MR has been closed/merged already?")
            print("* Consider fetching the remote ('mrhlpr checkout " +
                  str(mr_id) + " -f')")
            exit(1)

    # Save in mrdb
    mrdb.set(origin["host"], origin["project_id"], branch_local, mr_id)


def commits_have_mr_id(commits, mr_id):
    """ Check if all given commits have the MR-ID in the subject.
        :param commits: return value from git.commits_on_top_of_master()
        :returns: True if the MR-ID is in each subject, False otherwise """
    for commit in commits:
        subject = git.run(["show", "-s", "--format=%s", commit])
        if not subject.endswith(" (!" + str(mr_id) + ")"):
            return False
    return True


def fixmsg(mr_id):
    """ Add the MR-ID in each commit of the MR.
        :param mr_id: merge request ID """
    if not mr_id:
        print("ERROR: no merge request is currently checked out.")
        print("Run 'mrhlpr checkout N' first.")
        exit(1)

    os.putenv("MRHLPR_MSG_FILTER_MR_ID", str(mr_id))
    script = os.path.realpath(os.path.realpath(__file__) +
                              "/../data/msg_filter.py")
    os.chdir(git.run(["rev-parse", "--show-toplevel"]))

    print("Appending ' (!" + str(mr_id) + ")' to all commits...")
    git.run(["filter-branch", "-f", "--msg-filter", script,
             "origin/master..HEAD"])
