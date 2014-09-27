#! /usr/bin/python
#################################################################################################################
#
# Script to scan thetvdb.com for series info, compare list of episodes to the xbmc
# mysql DB, and attempt to download missing torrents from piratebay/btjunkie
# using the deluge rpc interface
#
#################################################################################################################
import socket
from datetime import datetime
from sb_utils import *

startTime = datetime.now()
e_masks = [sNeN, NxN, NNN]
s_masks = [season, series]
ignore_taglist = ["SWESUB", "SPANISH", "GERMAN", "HBOGO"]
#ignore_taglist = ["SWESUB", "SPANISH", "GERMAN", "WEBRIP", "HBOGO"]
#search_list = [piratebaysearch, isohuntsearch, extratorrentsearch]
search_list = [piratebaysearch]
socket.setdefaulttimeout(10)

# Get our config file and params
opts = configure_all()

# Set up the logger to print out errors
log = get_sb_log(opts)

# Set up DB_manager
setup_db_manager(opts)
db = db_manager()

# If using the shows file, open and get shows list
shows_list = []

# Get the list of shows that are complete so we can safely ignore them
ignore_list = db.get_ignore_list()
shows_list = [val for val in shows_list if val not in ignore_list]

#################################################################################################################
# Main
#################################################################################################################
if(opts.all):
    # if ALL, we get the complete list of shows from xbmc, minus the finished shows (if any)
    log.info("Scanning entire XBMC library, this could take some time...")
    full_showlist = []
    db_showlist = db.xbmc_get_showlist()
    for show in db_showlist:
        if(show[0].decode('latin-1', 'replace') not in ignore_list): full_showlist.append(show[0])
    #TODO: add this to config file
    get_trakt_watch_list = True
    if(get_trakt_watch_list):
        log.info("Looking for shows from trakt.com watchlist")
        # get the watchlist from trakt and add
        traktlist = traktWatchlistScraper("thegom145", "b837e9f111dcae8e279711ce929e9ef1")
        full_showlist.extend(t for t in traktlist if t.decode('latin-1', 'replace') not in ignore_list)
        full_showlist.sort()
    for show in full_showlist:
        if(show.decode('latin-1', 'replace') not in ignore_list):
            hunt_eps(show, opts, search_list, s_masks, e_masks, ignore_taglist)

else:
    # if SHOW, get specified show
    if(opts.show):
        hunt_eps(opts.show, opts, search_list, s_masks, e_masks, ignore_taglist)
    
    # else EXIT
    else:
        log.info("No shows to download, exiting")
        sys.exit()


# Connect to a daemon running on the localhost
d = client.connect()
d.addCallback(on_connect_success)
d.addErrback(on_connect_fail)

# Run the twisted main loop to make everything go
reactor.run()
