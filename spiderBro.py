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
from spiderBroAPI import *

startTime = datetime.now()
e_masks = [SNEN, NxN, NNN]
s_masks = [Season, Series]
ignore_taglist = ["SWESUB", "SPANISH", "GERMAN", "HBOGO"]
search_list = [PirateBaySearch]
search_list = [KATSearch]
#search_list = [ExtraTorrentSearch]
socket.setdefaulttimeout(10)

# Get our config file and script arguments
script_args = get_configuration()

# Get an instance of spiderBro, tell it to search for torrents
spider = SpiderBro(script_args, e_masks, s_masks, ignore_taglist, search_list)
torrent_download_list = spider.get_torrent_download_list()

# Deferred callbacks for twisted
def on_connect_fail(result):
    """
        Deferred callback function to be called when an error is encountered
    """
    l = logging.getLogger('spiderbro')
    l.info("Connection failed!")
    l.info("result: %s" % result)
    sys.exit()


def on_connect_success(result):
    """
        Deferred callback function called when we connect
    """
    d = db_manager()
    l = logging.getLogger('spiderbro')
    init_list = []
    l.info("Connection to deluge was successful, result code: %s" % result)
    # need a callback for when torrent added completes
    def add_tor(key, val):
        l.info("---> Added Torrent: %s" % (val))
    
    for tp in torrent_download_list:
        di = {'download_location':tp['save_dir']}
        # added support for magnet links
        if(str(tp["url"]).startswith("magnet:")):
            df = client.core.add_torrent_magnet(tp["url"], di).addCallback(add_tor, tp["url"])
        else:
            df = client.core.add_torrent_url(tp["url"], di).addCallback(add_tor, tp["url"])
        init_list.append(df)
        #add url to database - ideally would be nice to do this in callback, but dont have info there?
        d.add_to_urls_seen(tp['showname'], tp['season'], tp['episode'], tp['url'], tp['save_dir'])

    dl = defer.DeferredList(init_list)
    dl.addCallback(dl_finish)

def dl_finish(result):
    """
        Deferred callback function for clean exit
    """
    l = logging.getLogger('spiderbro')
    l.info("All deferred calls have fired, exiting program...")
    client.disconnect()
    # Stop the twisted main loop and exit
    reactor.stop()

# Connect to a daemon running on the localhost
d = client.connect()
d.addCallback(on_connect_success)
d.addErrback(on_connect_fail)

# Run the twisted main loop to make everything go
reactor.run()
