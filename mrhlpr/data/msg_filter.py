#!/usr/bin/env python3
# Copyright 2019 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
""" Internally used to add the MR-ID to a given commit message. """

import os
import sys

if not os.getenv("MRHLPR_MSG_FILTER_MR_ID"):
    print("This script is meant to be called internally by mrhlpr.py.")
    print("It accepts a commit message on stdin, and writes it back with")
    print("the merge request ID appended to the subject line.")
    print("ERROR: MRHLPR_MSG_FILTER_MR_ID is not set")
    exit(1)


line_number = 0
suffix = " (!" + os.getenv("MRHLPR_MSG_FILTER_MR_ID") + ")"
for line in sys.stdin:
    line = line.rstrip()
    line_number += 1

    # Add the suffix in the first line
    if line_number == 1:
        if line.endswith(suffix):
            print(line)
        else:
            print(line + suffix)
    else:
        # Make sure we have an empty line after the first one
        if line_number == 2 and line != "":
            print()

        # Print all other lines without modification
        print(line)
