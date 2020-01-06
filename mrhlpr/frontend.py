# Copyright 2020 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
""" Pretty outputs and such. """

import argparse
import logging

try:
    import argcomplete
except ImportError:
    argcomplete = False

from . import git
from . import gitlab
from . import mr


def print_status(mr_id, no_cache=False):
    """ Print the merge request status. Most info is only visible, when the
        branch is checked out locally. Always display a checklist of things to
        do next, in order to get the MR shipped.
        :param mr_id: merge request ID
        :param no_cache: do not cache the API result for the merge request data
    """
    if not mr_id:
        print("ERROR: can't associate the current branch with a merge request"
              " ID. Run 'mrhlpr checkout N' first (N is the MR-ID).")
        exit(1)

    status = mr.get_status(mr_id, no_cache)
    is_checked_out = mr.checked_out() == mr_id
    is_rebased = None
    clean_worktree = None
    commits = []
    commits_have_id = None
    commits_are_signed = None

    # Generate URL
    origin = gitlab.parse_git_origin()
    url = "https://{}/{}/merge_requests/{}".format(origin["host"],
                                                   origin["project_id"], mr_id)

    # Header
    print(url)
    print()
    print("\"" + status["title"] + "\"" + " (!" + str(mr_id) + ")")
    if is_checked_out:
        is_rebased = git.is_rebased_on_master()
        clean_worktree = git.clean_worktree()
        commits = git.commits_on_top_of_master()
        commits_have_id = mr.commits_have_mr_id(commits, mr_id)
        commits_follow_format, subj_err = mr.commits_follow_format(commits)
        commits_are_signed = mr.commits_are_signed(commits)
        print("{} commit{} from {}/{}".format(len(commits),
                                              "s" if len(commits) > 1 else "",
                                              status["source_namespace"],
                                              status["branch"]))
    else:
        print("not checked out, from " + status["source"])
    print()

    if status["state"] == "closed":
        print("ERROR: MR has been closed.")
        exit(1)
    elif status["state"] == "merged":
        print("ERROR: MR has been merged.")
        exit(1)

    # Changes allowed by maintainers
    if status["allow_push"]:
        print("[OK ] Changes allowed")
    else:
        print("[NOK] Changes allowed")

    # Clean worktree
    if clean_worktree is None:
        print("[???] Clean worktree")
    elif clean_worktree:
        print("[OK ] Clean worktree")
    else:
        print("[NOK] Clean worktree")

    # Rebase on master
    if is_rebased is None:
        print("[???] Rebase on master")
    elif is_rebased:
        print("[OK ] Rebase on master")
    else:
        print("[NOK] Rebase on master")

    # MR-ID in all commit messages
    if commits_have_id is None:
        print("[???] MR-ID in commit msgs")
    elif commits_have_id:
        print("[OK ] MR-ID in commit msgs")
    else:
        print("[NOK] MR-ID in commit msgs")

    # All commits follow formatting
    if commits_follow_format is None:
        print("[???] Commit subjects follow format")
        for line in subj_err:
            print("   " + line)
    elif commits_follow_format:
        print("[OK ] Commit subjects follow format")
    else:
        print("[NOK] Commit subjects follow format")
        for line in subj_err:
            print("   " + line)

    # Commits are signed
    if commits_are_signed is None:
        print("[???] Commits are signed")
    elif commits_are_signed:
        print("[OK ] Commits are signed")
    else:
        print("[NOK] Commits are signed")

    # Checklist
    print()
    print("Checklist:")
    if not status["allow_push"]:
        print("* Ask MR author to tick 'Allow commits from members who can"
              " merge to the target branch.'")
        print("* Check again ('mrhlpr -n status')")
        return

    if not is_checked_out:
        print("* Checkout this MR ('mrhlpr checkout " + str(mr_id) + "')")
        return

    if not clean_worktree:
        print("* Commit or stash changes in your worktree")
        print("* Check again ('mrhlpr status')")
        return

    if len(commits) > 1:
        print("* " + str(len(commits)) + " commits: consider squashing"
              " ('git rebase -i origin/master')")

    if not is_rebased:
        print("* Rebase on master ('git rebase origin/master')")
        print("* Check again ('mrhlpr status')")
        return

    if not commits_have_id or not commits_are_signed:
        print("* Add the MR-ID to all commits and sign them ('mrhlpr fixmsg')")
        return

    if commits_follow_format is False:
        print("* Fix commit subjects that don't follow the correct formatting")
        return

    if commits_follow_format is None:
        print("* Manually check if the commit subjects are correct")

    origin = gitlab.parse_git_origin()
    remote_local = status["source"].split("/", 1)[0]
    if remote_local == origin["project"]:
        remote_local = "origin"

    print("* Pretty 'git log -" + str(len(commits)) + " --pretty'?" +
          " (consider copying MR desc)")
    print("* Push your changes ('git push --force " + remote_local + " HEAD:" +
          status["branch"] + "')")
    print("* Web UI: comment about your reviewing and testing")
    print("* Web UI: approve MR")
    print("* Web UI: do (automatic) merge")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--no-cache", action="store_true",
                        help="do not use local cache for MR information")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="display debug log: all git commands and"
                             " locations of http cache files")
    sub = parser.add_subparsers(title="action", dest="action")
    sub.required = True

    # Status
    status = sub.add_parser("status", help="show the MR status")
    status.add_argument("mr_id", type=int, nargs="?", help="merge request ID")

    # Checkout
    checkout = sub.add_parser("checkout",
                              help="add and switch to the MR's branch")
    checkout.add_argument("-n", "--no-fetch", action="store_false",
                          dest="fetch",
                          help="do not fetch the remote and origin"
                               " repositories")
    checkout.add_argument("-o", "--overwrite-remote", action="store_true",
                          help="overwrite the remote URLs if they differ")
    checkout.add_argument("mr_id", type=int, help="merge request ID")

    # Fixmsg
    sub.add_parser("fixmsg", help="add the MR-ID to all commits and sign them")

    if argcomplete:
        argcomplete.autocomplete(parser, always_complete_options="long")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    if args.action == "status":
        mr_id = args.mr_id if args.mr_id else mr.checked_out()
        print_status(mr_id, args.no_cache)
    elif args.action == "checkout":
        mr.checkout(args.mr_id, args.no_cache, args.fetch,
                    args.overwrite_remote)
        print_status(args.mr_id)
    elif args.action == "fixmsg":
        mr_id = mr.checked_out()
        mr.fixmsg(mr_id)
        print_status(mr_id)
