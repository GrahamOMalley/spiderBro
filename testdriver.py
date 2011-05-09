#! /usr/bin/env python

from sb_utils import *

ep_matches = [sNeN, NxN]
sn_matches = [season, series]
sites = [piratebaysearch, btjunkiesearch]

# very simple dupe of main logic in spiderBro, leaving out some features for brevity
for series in ("Psychoville", "Game Of Thrones", "American Dad!", "The Whitest Kids U Know"):
    print "Searching for Series: %s" % series
    for m_season, m_episode in [("3", "3"), ("2", "10"), ("5", "-1"), ("1", "-1"), ("7", "-1"), ("4", "-1")]:
        found = False
        print "s%s e%s:" % (m_season, m_episode)
        for site in [btjunkiesearch]:
            if not found:
                p = site()
                #print "\tSearching: " + p.name + "for s" + m_season + "e" + m_episode
                if m_episode == "-1":
                    matches = sn_matches
                else:
                    matches = ep_matches
                for f in matches:
                    s = f()
                    v = p.search(series, m_season, m_episode, f)
                    if v:
                        print "ACCEPTED " + v
                        found = True
                        break
