# -*- coding: utf-8 -*-

import subprocess
import os
import sys
import re
import errno


# This variable contains a reference version of the current code-base. It is
# updated by release and dev-cycle scripts.
BASE_VERSION = '2018.11.09-dev'
# This commit is the reference commit of the BASE_VERSION above.
BASE_COMMIT = '0e2b5fe88d5d43e466a80cd70f0450916098a8c8'
# These files are created as part of our Docker build and are looked for as
# fall-back, should no git environment be available. The VERSION_INFO_PATH file
# contains the commit ID of the code and the COUNT_INFO_PATH file contains the
# commit distance to the the BASE_COMMIT above.
VERSION_INFO_PATH = '/home/git-version'
COUNT_INFO_PATH = '/home/git-base-count'
# The length to which Git commit IDs should be truncated to.
GIT_COMMIT_LENGTH = 10


def get_version():
    """
    Return output of "git describe" executed in the directory of this file. If
    this results in an error, "unknown" is returned.
    """
    try:
        dir = os.path.dirname(os.path.realpath(__file__))
        # Universal newlines is used to get both Python 2 and 3 to use text mode.
        p = subprocess.Popen("/usr/bin/git describe", cwd=os.path.dirname(dir),
                shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True)
        (out, error) = p.communicate()
        if error:
            # Fall-back to docker version file, if it exists
            version_file = open(VERSION_INFO_PATH, 'r')
            version_info = version_file.read().rstrip().encode('utf-8').decode('utf-8')
            version_info = version_info[:GIT_COMMIT_LENGTH]
            count_file = open(COUNT_INFO_PATH, 'r')
            count_info = count_file.read().rstrip().encode('utf-8').decode('utf-8')
        else:
            describe_info = out.rstrip().encode('utf-8').decode('utf-8')
            version_parts = describe_info.split('-')
            version_info = version_parts[2][1:]
            count_info = version_parts[1]
        return '{}-{}-{}'.format(BASE_VERSION, count_info, version_info)
    except:
        return '{}-unknown'.format(BASE_VERSION)


def relative(*path_components):
    """
    Returns a path relative to the directory this file is in
    """
    base = os.path.abspath(os.path.dirname(__file__))
    all_parts = [base] + list(path_components)
    return os.path.realpath(os.path.join(*all_parts))
