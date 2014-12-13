#! /usr/bin/env python
#from sb_utils import *
import sys
import urllib2

if __name__ == "__main__":
    """
        quick little testing script to see behaviour of search classes and test individual episodes/seasons
    """
#    e_masks = [NxN, sNeN, NNN]
#    s_masks = [season, series]
#    search_list = [piratebaysearch, btjunkiesearch, isohuntsearch]
#    tags = ["SWESUB", "SPANISH"]
#    opts = {"use_debug_logging":True, "log_dir":"log"}

    #log = get_sb_log(opts)

    #base = base_search()
    #base.search("Game of Thrones", "1", "3", sNeN, tags, True)
    
    #p = piratebaysearch()
    #result = p.search("Girls", "2", "2", sNeN, tags, True)
    #if result: log.info("\t\tFound Torrent: %s" % result)

    #i = isohuntsearch()
    #result = i.search("The Office (US)", "8", "17", sNeN, tags, False)
    #print e.search_url
    #if result: log.info("\t\tFound Torrent: %s" % result)
    
    #e = extratorrentsearch()
    #result = e.search("The Office (US)", "8", "17", sNeN, tags, False)
    #print e.search_url #if result: log.info("\t\tFound Torrent: %s" % result)

    #proxy_support = urllib2.ProxyHandler({})
    #opener = urllib2.build_opener(proxy_support)
    #urllib2.install_opener(opener)
    #response = urllib2.urlopen("http://extratorrent.cc/search/?search=downton+abbey&new=1&x=0&y=0")
    request = urllib2.Request("https://kickass.unblocked.pw/usearch/marvels%20agents%20of%20S.H.I.E.L.D.%20s02e10/")
    request.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')
    request.add_header('User-Agent', "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:35.0) Gecko/20100101 Firefox/35.0")
    request.add_header('Accept-Language', "en-US,en;q=0.5")
    response = urllib2.urlopen(request)
    search_page = response.read()
    print search_page
