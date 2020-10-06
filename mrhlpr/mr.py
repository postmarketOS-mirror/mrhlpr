# Copyright 2020 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
""" High level merge request related functions on top of git, gitlab, mrdb. """

import json
import logging
import os
import re
import subprocess
import sys

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
                   "source_branch": "mymr",
                   "target_branch": "v20.05",
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

    source_branch = api["source_branch"]
    target_branch = api["target_branch"]
    for branch in [source_branch, target_branch]:
        if (not re.compile(r"[a-zA-Z0-9/-_.]*").match(branch) or
                branch.startswith("-")):
            print(f"Invalid branch: {branch}")
            exit(1)

    return {"title": api["title"],
            "source_branch": source_branch,
            "target_branch": target_branch,
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
    remote, repo = status["source"].split("/", 1)
    origin = gitlab.parse_git_origin()
    branch = status["source_branch"]

    # Require clean worktree
    if not git.clean_worktree():
        print("ERROR: worktree is not clean! Commit or stash your changes")
        print("and try again. See 'git status' for details.")
        exit(1)

    # Don't add the origin remote twice
    remote_local = remote
    if remote == origin["project"]:
        remote_local = "origin"

    # Check existing remote
    project_repo_git = "{}/{}.git".format(remote, repo)
    username = (origin["username"] + "@" if origin["username"] else "")
    url = "https://" + username + origin["host"] + "/" + project_repo_git
    url_push = "git@" + username + origin["host"] + ":" + project_repo_git
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
        try:
            git.run(["fetch", remote_local])
        except subprocess.CalledProcessError:
            print("Failed to fetch from remote. Try running 'git fetch " +
                  remote_local + "' manually and check the output, most"
                  " likely you ran into this problem:"
                  " https://gitlab.com/postmarketOS/mrhlpr/issues/1")
            sys.exit(1)

    branch_local = "mrhlpr/" + str(mr_id)

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
            print("$ mrhlpr checkout " + str(mr_id) + " -n")
            exit(1)
        git.run(["checkout", branch_local])

        # Compare revisions (reset hard if needed)
        rev_current = git.run(["rev-parse", "HEAD"])
        rev_remote = git.run(["rev-parse", remote_local + "/" + branch])
        if rev_current == rev_remote:
            print("(Most recent commit is already checked out.)")
        else:
            print("################")
            print("NOTE: branch " + branch_local + " already exists, reusing.")
            print("You can go back to the previous commit with:")
            print("$ git reset --hard " + rev_current)
            print("################")
            git.run(["reset", "--hard", rev_remote])
    else:
        git.run(["checkout", "-b", branch_local, remote_local + "/" + branch],
                check=False)
        if git.branch_current() != branch_local:
            print()
            print("ERROR: checkout failed.")
            print("* Does that branch still exist?")
            print("* Maybe the MR has been closed/merged already?")
            print("* Do you have unstaged commits that would be overwritten?")
            exit(1)

    # Set upstream branch (git will still complain with "The upstream branch
    # of your current branch does not match the name of your current branch",
    # unless "git config push.default upstream" is set. There doesn't seem to
    # be a way around that.)
    git.run(["branch", "-u", remote_local + "/" + branch])

    # Save in mrdb
    mrdb.set(origin["host"], origin["project_id"], branch_local, mr_id)


def commits_have_mr_id(commits, mr_id):
    """ Check if all given commits have the MR-ID in the subject.

        :param commits: return value from git.commits_on_top_of()
        :returns: True if the MR-ID is in each subject, False otherwise """
    for commit in commits:
        subject = git.run(["show", "-s", "--format=%s", commit])
        if not subject.endswith(" (MR " + str(mr_id) + ")"):
            return False
    return True


def commits_follow_format(commits):
    """ Check if the commit subjects follow the correct naming format.

        :param commits: return value from git.commits_on_top_of()
        :returns: (result, subject_err)
                  result: True if the commits are formatted correctly, False if
                          something is obviously wrong and None if it is
                          something between
                  subject_err: string with commit hash and explanation of what
                               is wrong with the subject """
    subjects = {}
    for commit in commits:
        subjects[commit] = git.run(["show", "-s", "--format=%s", commit])

    # Run generic checks that don't need definitions first
    for commit, subject in subjects.items():

        # Don't have an period at the end of the subject
        if subject.endswith("."):
            return (False, [commit[0:6] + " ends with period"])

    # Load a definition file from the root of the repo if it exists
    definition_file = os.path.join(git.topdir(), '.mrhlpr.json')
    if not os.path.isfile(definition_file):
        return (True, [])

    with open(definition_file) as handle:
        definitions = json.load(handle)

    regexes_pass = []
    for regex in definitions['subject_format']['pass']:
        regexes_pass.append(re.compile(regex))

    regexes_unknown = []
    for regex in definitions['subject_format']['unknown']:
        regexes_unknown.append(re.compile(regex))

    result = True
    subj_err = []

    for commit, subject in subjects.items():
        logging.debug('Checking subject: {}'.format(subject))
        for regex in regexes_pass:
            if regex.match(subject):
                logging.debug('  Matched pass regex {}'.format(regex.pattern))
                break
        else:
            for regex in regexes_unknown:
                if regex.match(subject):
                    logging.debug(
                        '  Matched unknown regex {}'.format(regex.pattern))
                    result = None
                    subj_err.append(commit[0:6] + " matches " + regex.pattern)
                    break
            else:
                logging.debug('  No regex matched')
                return (False, [commit[0:6] + " doesn't match any regex"])

    return (result, subj_err)


def commits_are_signed(commits):
    """ Check if all given commits are signed.

        :param commits: return value from git.commits_on_top_of()
        :returns: True if all are signed, False otherwise """
    for commit in commits:
        if not git.run(["verify-commit", commit], check=False):
            return False
    return True


def fixmsg(mr_id):
    """ Add the MR-ID in each commit of the MR.

        :param mr_id: merge request ID """
    if not mr_id:
        print("ERROR: no merge request is currently checked out.")
        print("Run 'mrhlpr checkout N' first.")
        exit(1)
    target_branch = get_status(mr_id)["target_branch"]

    script = os.path.realpath(os.path.realpath(__file__) +
                              "/../data/msg_filter.py")
    os.chdir(git.run(["rev-parse", "--show-toplevel"]))

    print("Appending ' (MR " + str(mr_id) + ")' to commits and signing them...")  # noqa: E501
    try:
        env = os.environ.copy()
        env["MRHLPR_MSG_FILTER_MR_ID"] = str(mr_id)
        git.run(["filter-branch", "-f", "--msg-filter", script,
                 "--commit-filter", "git commit-tree -S \"$@\"",
                 f"origin/{target_branch}..HEAD"], env=env)
    except subprocess.CalledProcessError:
        print("ERROR: git filter-branch failed. Do you have git commit signing"
              " set up properly? (Run with -v to see the failing command.)")
        exit(1)
