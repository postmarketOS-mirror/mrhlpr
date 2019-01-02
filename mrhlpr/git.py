# Copyright 2019 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
""" Low level git functions. """

import subprocess
import logging


def run(parameters, check=True):
    """ Run a git command.
        :parameters: list of arguments to pass to git
        :check: when set to True, raise an exception on exit code not being 0
        :returns: on success: output of the command (last new line removed)
                  on failure: None """
    try:
        logging.debug("+ git " + " ".join(parameters))
        stdout = subprocess.check_output(["git"] + parameters,
                                         stderr=subprocess.STDOUT)
        ret = stdout.decode("utf-8").rstrip()
        logging.debug(ret)
        return ret
    except subprocess.CalledProcessError:
        if check:
            raise
        return None


def get_remote_url(remote="origin"):
    """ :returns: the remote URL as string, e.g.
                  "https://gitlab.com/postmarketOS/pmaports.git" """
    return run(["remote", "get-url", remote], check=False)


def branches(obj="refs/heads"):
    """ :returns: a list of all local branch names """
    ret = run(["for-each-ref", obj, "--format", "%(refname:short)"])
    return ret.splitlines()


def branch_current():
    """ :returns: current branch name (if any) or "HEAD" """
    return run(["rev-parse", "--abbrev-ref", "HEAD"])


def branch_remote(branch_name="HEAD"):
    ''' :returns: remote name, or None'''
    upstream = run(["rev-parse", "--abbrev-ref", branch_name + "@{u}"], False)
    if upstream:
        return upstream.split("/", 1)[0]
    return None


def commits_on_top_of_master():
    """ :returns: list of commit ID strings """
    return run(["rev-list", "origin/master..HEAD"]).splitlines()


def is_rebased_on_master():
    """ Check if the current branch needs to be rebased on master. """
    return run(["rev-list", "--count", "HEAD..origin/master"]) == "0"


def clean_worktree():
    """ Check if there are not modified files in the git dir. """
    return run(["status", "--porcelain"]) == ""
