#! /usr/bin/python

#################################################################################################################
#
# Script to scan thetvdb.com for series info, compare list of episodes to the xbmc
# mysql DB, and attempt to download missing torrents from piratebay/btjunkie
# using the deluge rpc interface
#
#################################################################################################################

import socket
from sb_utils import *

#################################################################################################################
# globals
#################################################################################################################

e_masks = [NxN, sNeN]
s_masks = [season, series]
search_list = [piratebaysearch, btjunkiesearch]
# these could be made configurable
socket.setdefaulttimeout(10)

#################################################################################################################
# get our config file and params
#################################################################################################################

opts = get_config_file("/home/gom/.spiderBro/config.ini")
opts.update(get_params(sys.argv))
if "force_show" in opts: opts['use_whole_lib'] = False

#################################################################################################################
# Set up the logger to print out errors
#################################################################################################################

log = get_sb_log(opts)

#################################################################################################################
# Set up DB_manager
#################################################################################################################

setup_db_manager(opts)
db = db_manager()

db_do_opts(opts)

#################################################################################################################
# If using the shows file, open and get shows list
#################################################################################################################

shows_list = []
if(('shows_file' in opts and not opts['use_whole_lib']) and 'force_show' not in opts):
    shows_list = get_shows_from_file(opts['shows_file'])

#################################################################################################################
# Get the list of shows that are complete so we can safely ignore them, speeds up whole library scan considerably
#################################################################################################################

ignore_list = db.get_ignore_list()
shows_list = [val for val in shows_list if val not in ignore_list]
#################################################################################################################
# Main
#################################################################################################################

if(opts['use_whole_lib']):
    #
    # if USE_WHOLE_LIB, we get the complete list of shows from xbmc, minus the finished shows (if any)
    #
    log.info("Scanning entire XBMC library, this could take some time...")

    full_showlist = db.xbmc_get_showlist()
    for show in full_showlist:
        if(show[0] not in ignore_list):
            hunt_eps(show[0], opts, search_list, s_masks, e_masks)

else:
    #
    # if FORCE_SHOW, get specified show
    #
    if('force_show' in opts):
        hunt_eps(opts['force_show'], opts, search_list, s_masks, e_masks)
    #
    # if SHOWS_LIST, get for list of shows
    #
    elif(shows_list):
        log.info("Using list of shows from file...")
        for show in shows_list:
            hunt_eps(show, opts, search_list, s_masks, e_masks)
    #
    # else EXIT
    #
    else:
        log.info("No shows to download, exiting")
        sys.exit()


# Connect to a daemon running on the localhost
d = client.connect()
d.addCallback(on_connect_success)
d.addErrback(on_connect_fail)

# Run the twisted main loop to make everything go
reactor.run()
