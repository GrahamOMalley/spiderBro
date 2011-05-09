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
# dont change db_mask after using spiderbro for the first time, it'll mess up thesurls_seen table
db_mask = sNeN()
# these could be made configurable
socket.setdefaulttimeout(10)

#################################################################################################################
# get our config file and params
#################################################################################################################

opts = get_configfile("/home/gom/.spiderBro/config.ini")
opts.update(get_params(sys.argv))
if "force_show" in opts: opts['use_whole_lib'] = False

#################################################################################################################
# Set up the logger to print out errors
#################################################################################################################

log = getSBLog(opts)

#################################################################################################################
# If using the shows file, open and get shows list
#################################################################################################################

shows_list = []
if(('shows_file' in opts and not opts['use_whole_lib']) and 'force_show' not in opts):
    shows_list = getshowsfromfile(opts['shows_file'])

#################################################################################################################
# Get the list of shows that are complete so we can safely ignore them, speeds up whole library scan considerably
#################################################################################################################

ignore_list = getignorelist()
shows_list = [val for val in shows_list if val not in ignore_list]

#################################################################################################################
# Main
#################################################################################################################

if(opts['use_whole_lib']):
    #
    # if USE_WHOLE_LIB, we get the complete list of shows from xbmc, minus the finished shows (if any)
    #
    log.info("Scanning entire XBMC library, this could take some time...")
    mysql_con = MySQLdb.connect (host = "localhost",user = "xbmc",passwd = "xbmc",db = "xbmc_video")
    mc = mysql_con.cursor()
    mc.execute("""select distinct strTitle from episodeview order by strTitle""")
    for show in mc:
        if(show[0] not in ignore_list):
            d = hunt_eps(show[0], opts, search_list, s_masks, e_masks, db_mask)
            if d: dl_these.append(d)
    mc.close()
    mysql_con.close()

else:
    #
    # if FORCE_SHOW, get specified show
    #
    if('force_show' in opts):
        d = hunt_eps(opts['force_show'], opts, search_list, s_masks, e_masks, db_mask)
        if d: dl_these.append(d)
    #
    # if SHOWS_LIST, get for list of shows
    #
    elif(shows_list):
        log.info("Using list of shows from file...")
        for show in shows_list:
            d = hunt_eps(show, opts, search_list, s_masks, e_masks, db_mask)
            if d: dl_these.append(d)
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
