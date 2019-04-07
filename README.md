# mrhlpr - merge request helper

Lightweight script to support maintainers of postmarketOS in the merge workflow on GitLab.

The workflow looks like this:
1. Checkout the merge request locally (`mrhlpr checkout 123`).
2. Rebase on latest master (`git rebase master`).
3. Add the MR-ID to all commit messages and sign them (`mrhlpr fixmsg`).
4. Optionally squash all commits (`git rebase -i master`).
5. Check if everything is fine (`mrhlpr status`).
6. If everything looks good force push (`git push --force`).
7. In the GitLab web UI: wait for CI, then merge.

## installation
Same as for pmbootstrap: clone the repo, create a symlink to `mrhlpr.py` in your `PATH`. Optionally set up autocompletion with argcomplete. See pmbootstrap's [manual installation instructions](https://wiki.postmarketos.org/wiki/Installing_pmbootstrap#Installing_Manually) for details.

## example session

Start with `mrhlpr checkout` and the MR-ID. The built-in checklist will tell the next steps. All API requests get cached on disk.

```shell-session
$ cd ~/code/pmbootstrap/aports
$ mrhlpr checkout 81                                               
Download https://gitlab.com/api/v4/projects/postmarketOS%2Fpmaports/merge_requests/81
Download https://gitlab.com/api/v4/projects/8065375
Checkout feature/abuild-sign-noinclude from postmarketOS/feature/abuild-sign-noinclude
https://gitlab.com/postmarketOS/pmaports/merge_requests/81

"main/abuild-sign-noinclude: new aport" (!81)
10 commits from postmarketOS/feature/abuild-sign-noinclude

[OK ] Changes allowed
[OK ] Clean worktree
[NOK] Rebase on master
[NOK] MR-ID in commit msgs
[NOK] Commits are signed

Checklist:
* 10 commits: consider squashing ('git rebase -i origin/master')
* Rebase on master ('git rebase origin/master')
* Check again ('mrhlpr status')
```

```shell-session
$ git rebase -i master
$ mrhlpr status
https://gitlab.com/postmarketOS/pmaports/merge_requests/81

"main/abuild-sign-noinclude: new aport" (!81)
1 commit from postmarketOS/feature/abuild-sign-noinclude

[OK ] Changes allowed
[OK ] Clean worktree
[OK ] Rebase on master
[NOK] MR-ID in commit msgs
[NOK] Commits are signed

Checklist:
* Add the MR-ID to all commits and sign them ('mrhlpr fixmsg')
```

```shell-session
$ mrhlpr fixmsg
Appending ' (!81)' to all commits...
https://gitlab.com/postmarketOS/pmaports/merge_requests/81

"main/abuild-sign-noinclude: new aport" (!81)
1 commit from postmarketOS/feature/abuild-sign-noinclude

[OK ] Changes allowed
[OK ] Clean worktree
[OK ] Rebase on master
[OK ] MR-ID in commit msgs
[OK ] Commits are signed

Checklist:
* Origin up-to-date? ('git fetch origin')
* Pretty 'git log'? (consider copying MR desc)
* Push your changes ('git push --force')
* Web UI: comment about your reviewing and testing
* Web UI: approve MR
* Web UI: adjust MR squash settings (remember the GitLab bug)
* Web UI: do (automatic) merge
```

### portability

This script is not postmarketOS specific, it should work with any GitLab repository. Right now, only gitlab.com is detected - but detecting any GitLab servers could be added in `mrhlpr/gitlab.py:parse_git_origin()` if desired.


### troubleshooting

`mrhlpr -v` displays debug log messages, such as all git commands and their output, as well as the locations of all http cache files.
