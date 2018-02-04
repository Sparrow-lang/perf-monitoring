#!/usr/bin/env python

from __future__ import print_function

import sys, os, argparse
import yaml

def main():
    # Parse the arguments
    parser = argparse.ArgumentParser(description='Add the given build to the list of latest builds')
    parser.add_argument('buildName', action='store', nargs='?',
        help='The name of the build')
    parser.add_argument('--latestBuildsFile', action='store', default='_data/latestBuilds.yaml', metavar='DIR',
        help='Path to the latestBuilds.yaml file')
    parser.add_argument('--maxEntries', action='store', default='7', metavar='N', type=int,
        help='Number of builds to keep in the list')
    parser.add_argument('--toConsole', action='store_true',
        help='If set, we write the output to console instead of file')
    args = parser.parse_args()

    # Read the current content of the file
    content = yaml.load(open(args.latestBuildsFile, 'r'))

    # Add the given build
    content.insert(0, args.buildName)
    if len(content) > 100:
        del content[100:]

    # Write the output
    outF = sys.stdout
    if not args.toConsole:
        outF = open(args.latestBuildsFile, 'w')
    print(yaml.dump(content, default_flow_style=False), file=outF)


if __name__ == "__main__":
    main()
