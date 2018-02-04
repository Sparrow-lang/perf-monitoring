#!/usr/bin/env python

from __future__ import print_function

import sys, os, argparse, glob
import yaml
import math,numpy

def getPerfDataForBuild(rawBuildData):
    res = {}
    meas = rawBuildData['measurements']
    for key, values in meas.iteritems():
        res[key] = (numpy.median(values), numpy.std(values))
    return res

def main():
    # Parse the arguments
    parser = argparse.ArgumentParser(description='Generate performance trends based on existing performance measurements')
    parser.add_argument('buildName', action='store', nargs='?',
        help='The name of the build')
    parser.add_argument('--dataBuildsDir', action='store', default='_data/builds', metavar='DIR',
        help='The directory containing raw performance data files')
    parser.add_argument('--dataProcessedDir', action='store', default='_data/processed', metavar='DIR',
        help='The directory containing processed performance data files')
    parser.add_argument('--pagesDir', action='store', default='builds', metavar='DIR',
        help='The directory containing the build pages')
    parser.add_argument('--metricsFile', action='store', default='_data/metrics.yaml', metavar='F',
        help='The path to metrics.yaml file')
    parser.add_argument('--maxEntries', action='store', default='20', metavar='N', type=int,
        help='Number of builds to consider for a trend')
    parser.add_argument('--toConsole', action='store_true',
        help='If set, we write the output to console instead of file')
    args = parser.parse_args()

    # Get the list of all the test files in this folder
    # Order them by creation date, reversed
    yamlFiles = glob.glob(args.dataBuildsDir + '/*.yaml')
    yamlFiles.sort(key=lambda x: -os.path.getmtime(x))

    # Make sure we are not dealing with too many files
    if len(yamlFiles) > 100:
        del yamlFiles[100:]

    # Build a map from short sha to yaml content
    # Also identify the sha of the given build
    data = {}
    mainSha = None
    for f in yamlFiles:
        # Load the content of the yaml
        stream = open(f, 'r')
        content = yaml.load(stream)
        # Index it
        sha = content['info']['sha']
        data[sha] = content
        if str(content['info']['name']) == str(args.buildName):
            mainSha = sha

    if not mainSha:
        print('ERROR: Cannot find the given build!')
        sys.exit(1)

    # Build the trend, starting backward from the current build
    trendSha = []
    trendBuilds = []
    curSha = mainSha
    for i in range(args.maxEntries-1):
        if curSha and curSha in data.keys():
            buildInfo = data[curSha]['info']
            trendSha.append(curSha)
            trendBuilds.append(buildInfo['name'])
            curSha = buildInfo['parents'][0]
        else:
            break
    N = len(trendSha)

    # Now build the trends for each measurement key
    perfTrends = {}
    for sha in trendSha:
        curPerf = getPerfDataForBuild(data[sha])
        if len(perfTrends) == 0:
            # Main build; add trends for current measurements
            for key, val in curPerf.iteritems():
                perfTrends[key] = { 'values': [float(val[0])], 'stddevs': [float(val[1])] }
        else:
            # Previous builds; append to the previous measurements lists
            for key in perfTrends.keys():
                val = curPerf[key] if key in curPerf.keys() else None
                if key in curPerf.keys():
                    perfTrends[key]['values'].append(float(curPerf[key][0]))
                    perfTrends[key]['stddevs'].append(float(curPerf[key][1]))
                else:
                    perfTrends[key]['values'].append(None)
                    perfTrends[key]['stddevs'].append(None)

    # Compute relative performance indicators
    if len(trendSha) > 1:
        for key, trend in perfTrends.iteritems():
            # Perf indicator relative to previous build
            val0 = trend['values'][0];
            val1 = None
            sd1 = None
            for i in range(1, N):
                val1 = trend['values'][i];
                sd1 = trend['stddevs'][i];
                if val1 and sd1:
                    break
            if val1 and sd1:
                if abs(sd1) < 0.1:
                    sd1 = 1.0
                perfTrends[key]['relPerf'] = float((val0-val1)/sd1);
            else:
                perfTrends[key]['relPerf'] = 0.0;

            # Perf indicator relative to trend
            val1 = None
            sd1 = None
            for i in range(N-1, 1, -1):
                val1 = trend['values'][i];
                sd1 = trend['stddevs'][i];
                if val1 and sd1:
                    break
            if val1 and sd1:
                if abs(sd1) < 0.1:
                    sd1 = 1.0
                perfTrends[key]['relPerfTrend'] = float((val0-val1)/sd1);
            else:
                perfTrends[key]['relPerfTrend'] = 0.0;
    else:
        for key, trend in perfTrends.iteritems():
            perfTrends[key]['relPerf'] = 0.0;
            perfTrends[key]['relPerfTrend'] = 0.0;

    # If we can open metrics.yaml, also compute the 'health' of the build
    statuses = {}
    stream = open(args.metricsFile, 'r')
    if stream:
        def _perfIndToString(perfInd):
            if perfInd > 4.0:
                return 'bad2'
            elif perfInd > 2.0:
                return 'bad'
            elif perfInd < -4.0:
                return 'good2'
            elif perfInd < -2.0:
                return 'good'
            else:
                return 'same'
        def _aggregateGroup(groupStruct, statuses):
            name = groupStruct['name']
            weight = groupStruct['weight']
            res = 0.0
            # Compute the score for the group
            if 'content' in groupStruct.keys():
                content = groupStruct['content']
                for sub in content:
                    res += _aggregateGroup(sub, statuses)
            else:
                if name in perfTrends:
                    res = perfTrends[name]['relPerf']
                    if abs(res) < 2.0:
                        res = 0.0
                else:
                    res = 0.0
            # Store the score for this group
            statuses[name] = _perfIndToString(res)
            # Return weighted result
            return weight * res
        content = yaml.load(stream)
        res = 0.0
        for gr in content['groups']:
            res += _aggregateGroup(gr, statuses)
        statuses['overall'] = _perfIndToString(res)

    # Build the summary of interesting measurements for current build
    curProblems = []
    curFixes = []
    trendProblems = []
    trendFixes = []
    for key, details in perfTrends.iteritems():
        relPerf = details['relPerf']
        relPerfTrend = details['relPerfTrend']
        if relPerf and relPerf > 2.0:
            curProblems.append(key)
        elif relPerf and relPerf < -2.0:
            curFixes.append(key)
        if relPerfTrend and relPerfTrend > 2.0:
            trendProblems.append(key)
        elif relPerfTrend and relPerfTrend < -2.0:
            trendFixes.append(key)


    # Reverse the lists that we have; current build should be last (instead of first)
    trendSha.reverse()
    trendBuilds.reverse()
    for key, trend in perfTrends.iteritems():
        trend['values'].reverse();
        trend['stddevs'].reverse();

    # Put all the results into a structure and print it as YAML
    outF = sys.stdout
    if not args.toConsole:
        outF = open('%s/%s.yaml' % (args.dataProcessedDir, args.buildName), 'w')
    struct = {'show-history': trendBuilds}
    print(yaml.dump(struct), file=outF)
    struct = {'statuses': statuses}
    print(yaml.dump(struct, default_flow_style=False), file=outF)
    struct = {'trends': perfTrends}
    print(yaml.dump(struct), file=outF)
    struct = {'summary': {
        'curProblems': curProblems,
        'curFixes': curFixes,
        'trendProblems': trendProblems,
        'trendFixes': trendFixes,
    }}
    print(yaml.dump(struct), file=outF)

    # Generate the build page
    if not args.toConsole:
        outF = open('%s/%s.md' % (args.pagesDir, args.buildName), 'w')
    print("""---
layout: build
build-id: "{0}"
title: "Build #{0}"
date: {1}
---
""".format(args.buildName, data[mainSha]['info']['date']), file=outF)

if __name__ == "__main__":
    main()
