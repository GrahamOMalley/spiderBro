#! /usr/bin/env python
from sb_utils import *
import sys

if __name__ == "__main__":
    """
        quick little testing script to see behaviour of search classes and test individual episodes/seasons
    """
    e_masks = [NxN, sNeN, NNN]
    s_masks = [season, series]
    search_list = [piratebaysearch, btjunkiesearch, isohuntsearch]
    tags = ["SWESUB", "SPANISH"]
    opts = {"use_debug_logging":True, "log_dir":"log"}

    log = get_sb_log(opts)

    #base = base_search()
    #base.search("Game of Thrones", "1", "3", sNeN, tags, True)
    
    p = piratebaysearch()
    result = p.search("Girls", "2", "2", sNeN, tags, True)
    if result: log.info("\t\tFound Torrent: %s" % result)

    #i = isohuntsearch()
    #result = i.search("The Office (US)", "8", "17", sNeN, tags, False)
    #print e.search_url
    #if result: log.info("\t\tFound Torrent: %s" % result)
    
    #e = extratorrentsearch()
    #result = e.search("The Office (US)", "8", "17", sNeN, tags, False)
    #print e.search_url
    #if result: log.info("\t\tFound Torrent: %s" % result)
