#! /usr/bin/env python
from sb_utils import *
if __name__ == "__main__":
	
    e_masks = [NxN, sNeN, NNN]
    s_masks = [season, series]
    search_list = [piratebaysearch, btjunkiesearch]
    tags = ["SWESUB", "SPANISH"]
    opts = {"use_debug_logging":True, "log_dir":"log"}

    log = get_sb_log(opts)

    #base = base_search()
    #base.search("Game of Thrones", "1", "3", sNeN, tags, True)

    p = pb()
    result = p.search("Game of Thrones", "1", "3", sNeN, tags, True)
    if result: log.info("\t\tFound Torrent: %s" % result)

    b = bt()
    result = b.search("Game of Thrones", "1", "3", sNeN, tags, False)
    if result: log.info("\t\tFound Torrent: %s" % result)
