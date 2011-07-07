#! /usr/bin/env python
from BeautifulSoup import BeautifulSoup
from datetime import date
from datetime import datetime
from deluge.log import setupLogger
from deluge.ui.client import client
from twisted.internet import defer
from twisted.internet import reactor
import ConfigParser
import traceback
from db_manager import *
import logging
import re
import sys
import time
import urllib2
import pdb

# nasty global
dl_these = []

#####################################################################################
# Filemasks
#####################################################################################

class season:
    def __init__(self):
        self.descr = "season"
    def mask(self, sn, ep):
        return ("season %s" % sn)

class series:
    def __init__(self):
        self.descr = "series"
    def mask(self, sn, ep):
        return ("series %s" % sn)

class sNeN:
    def __init__(self):
        self.descr = "sNeN"
    def mask(self, sn, ep):
        s = "s0" + sn if(int(sn)<10) else "s" + sn
        e = "e0" + ep if(int(ep)<10) else "e" + ep
        return (s+e)

class NxN:
    def __init__(self):
        self.descr = "NxN"
    def mask(self, sn, ep):
        e = "0" + ep if(int(ep)<10) else ep
        return ("%sx%s" % (sn, e))
       
class NNN:
    def __init__(self):
        self.descr = "NNN"
    def mask(self, sn, ep):
        e = "0" + ep if(int(ep)<10) else ep
        return ("%s%s" % (sn, e))
       
#####################################################################################
# Searches
#####################################################################################

class base_search:
    def __init__(self):
        self.name = "Base Search Class"
        self.delimiter = " "

    def search(self, series_name, sn, ep, fmask, tags, is_high_qual):
        lg = logging.getLogger('spiderbro')
        series_name = "".join(ch for ch in series_name if ch not in ["!", "'", ":"])
        series_name = series_name.replace("&", "and")
        m = fmask()
        season_or_ep_str = m.mask(sn, ep)
        ser_list = self.generate_search_terms(series_name)
        is_season = False
        if ep == "-1": is_season = True
        for series_search_term in ser_list:
            search_url = self.get_search_url(series_search_term, season_or_ep_str)
            lg.info("\tSearching %s:\t%s %s \t\t(%s)" % (self.name, series_search_term, season_or_ep_str, search_url))
            try:
                response = urllib2.urlopen(search_url)
                search_page = response.read()
            except:
                print "Couldn't open %s" % search_url
                return ""
            sps = BeautifulSoup(search_page)
            links = sps.findAll('a', href=re.compile("^http"))
            for l in links:
                if self.validate_link(series_search_term, season_or_ep_str, l['href'], tags, is_high_qual, is_season):
                    if self.validate_page(l['href']):
                        return l['href']
        return ""

    def validate_link(self, series, s_ep_str, link, tags, is_high_q, is_season):
        lg = logging.getLogger('spiderbro')
        if "torrent" in link:
            lg.debug('\t\tValidating %s' % (link))
        # First validate the link title is ok
        is_torrent = re.compile(".*torrent$")
        if(not is_torrent.match(link)):
            #lg.debug("\t\t\tValidation FAILED: Link is not a torrent")
            return False
            
        if (is_high_q and "720p" not in link): 
            lg.debug("\t\t\tValidation FAILED: Quality is HighQ but 720p not found in torrent")
            return False

        if((not is_high_q) and "720p" in link):
            lg.debug("\t\t\tValidation FAILED: Quality is lowQ but 720p found in torrent")
            return False

        for t in tags:
            if t.lower() in link.lower(): 
                lg.debug("\t\t\tValidation FAILED: tag filter %s found in torrent" % t)
                return False
        
        if is_season: 
            # we are searching for a linkrent of an entire season
            s_ep_str = s_ep_str.replace(" ", self.delimiter).lower()
            if (s_ep_str in link.lower() or (s_ep_str.replace(self.delimiter, self.delimiter+"0") in link.lower())):
                return True
        else:
            # we are searching for an episode
            if (s_ep_str in link.lower() and  self.delimiter.join(series.split(" ")).lower() in link.lower()):
                # TODO: this is failing and causing errors in the btjunkie search
                return True
            else:
                lg.debug("\t\t\tValidation FAILED: s_ep_str %s or %s not found in link title" % (s_ep_str, self.delimiter.join(series.split(" ")).lower()))

        
        return False

    # child classes can define their own site-specific page validation, see piratebaysearch for an example
    def validate_page(self, tor):
        return True

    # break the series name up and try different variations of it 
    # eg: "Blah & Blah (2010)" -> ["Blah & Blah (2010)", "Blah & Blah", "Blah and Blah (2010)", "Blah and Blah"] etc
    def generate_search_terms(self, name):
        regser = re.compile(" \([0-9a-zA-Z]{2,4}\)").sub('', name)
        li = [name, regser]
        
        # TODO: fix this ugly code, maybe loop through funciton list and apply each one to data

        hli =[]
        for l in li:
            hyphen = " ".join(l.split("-"))
            hli.append(hyphen)
        if hli: li.extend(hli)

        cli =[]
        for l in li:
            comma = " ".join(l.split(","))
            cli.append(comma)
        if cli: li.extend(cli)


        ali =[]
        for l in li:
            ampersand = "and".join(l.split("&"))
            ali.append(ampersand)
        if cli: li.extend(ali)

        return list(set(li))
    
    def get_search_url(self, name, maskval):
        return "www.thisisabaseclassyouidiot.com"


# Child classes need to define self.delimiter, get_search_url and optionally validate_page 
class piratebaysearch(base_search):
    def __init__(self):
        self.name = "piratebay"
        # TODO has piratebay switched to "." or do some links still use "_"?
        self.delimiter = "."
    
    def get_search_url(self, name, maskval):
        return "http://thepiratebay.org/search/"+"+".join(name.split(" ")).replace("'","")+"+"+"+".join(maskval.split(" ")) + "/0/7/0"
    
    def validate_page(self, tor):
        seeds = 0
        seeds_reg = re.compile("Seeders:</dt>\n<dd>[0-9]{1,9}")
        lg = logging.getLogger('spiderbro')
        lg.debug("\t\tDoing piratebay page validation")
        turl = tor.replace("http://torrents.thepiratebay.org", "http://thepiratebay.org/torrent")
        resp = urllib2.urlopen(turl)
        html = resp.read()
        data = BeautifulSoup(html)
        details = data.findAll("dl", { "class" : "col2" })
        # This is ugly as sin, I think beautifulsoup has some problems with <dt> and <dd> tags?
        for d in details: 
            try:
                seeds = int(seeds_reg.findall(str(d))[0].replace("Seeders:</dt>\n<dd>", ""))
            except:
                lg.error("\t\tError parsing seeders for piratebay")
        if seeds > 0:
            lg.debug("\t\tValidation passed, torrent has %s seeds..." % seeds)
            return True
        else:
            lg.debug("\t\tValidation FAILED, torrent has no seeds...")
        return False

class btjunkiesearch(base_search):
    def __init__(self):
        self.name = "btjunkie"
        self.delimiter = "-"
    
    def get_search_url(self, name, maskval):
        return "http://btjunkie.org/search?q="+"+".join(name.split(" ")).replace("'","")+"+"+"+".join(maskval.split(" "))

    def validate_page(self, tor):
        lg = logging.getLogger('spiderbro')
        lg.debug("\t\tDoing btjunkie page validation")
        g = re.compile(r'Good\((.*?)\)', re.DOTALL)
        f = re.compile(r'Fake\((.*?)\)', re.DOTALL) 
        good = 0
        fake = 0
        turl = tor.replace("/download.torrent", "").replace("dl.", "")
        resp = urllib2.urlopen(turl)
        
        val_page = resp.read()
        val_tags = BeautifulSoup(val_page)

        # first check if btjunkie verified image is present
        im = val_tags.findAll('img')
        for i in im:
            if(i['src'] == "http://static.btjunkie.org/images/verified_check1.gif"):
                lg.debug("\t\tValidated (validation check image is present)")
                return True

        # otherwise check if good > fake (TODO: Check seeds > 0)
        b = val_tags.findAll('b')
        for bs in b:
            if bs.string:
                if g.match(bs.string):
                    good = int(g.findall(bs.string)[0])
                    li = bs.string.split(" ")
                    for v in li:
                        if f.match(v):
                            fake = int(f.findall(v)[0])
        if(good > fake):
            return True
        else:
            lg.debug("\t\tValidation FAILED: good <= fake (good: %s fake: %s)" % (good, fake))
            return False


#####################################################################################
# Deferred callback function for clean exit
#####################################################################################

def dl_finish(result):
    l = logging.getLogger('spiderbro')
    l.info("All deferred calls have fired, exiting program...")
    client.disconnect()
    # Stop the twisted main loop and exit
    reactor.stop()

#################################################################################################################
# force database items from params
#################################################################################################################

def db_do_opts(opts):
    lg = logging.getLogger('spiderbro')
    db = db_manager()

    if('clear_cache' in opts and 'force_show' in opts):
        lg.info("Clearing db cache for show %s" % (opts['force_show']))
        db.clear_cache(opts['force_show'])
    
    if('high_quality' in opts and 'force_show' in opts):
        lg.info("Changing quality to high for show %s" % (opts['force_show']))
        db.set_quality(opts['force_show'], 1)
    
    if('low_quality' in opts and 'force_show' in opts):
        lg.info("Changing quality to low for show %s" % (opts['force_show']))
        db.set_quality(opts['force_show'], 0)
    
    if('force_id' in opts and 'force_show' in opts):
        lg.info("Forcing new id %s for show %s" % (opts['force_id'], opts['force_show']))
        db.update_series_id(opts['force_show'], opts['force_id'])
    

#####################################################################################
# Functions to retrieve configs, episodelists etc
#####################################################################################

def get_config_file(filename):
    opts = {}
    config = ConfigParser.ConfigParser()
    config.read(filename)
    
    # Attempt to get values from config file
    try:
        opts['sb_db_file'] = config.get("options", "sb_db_file")
    except:
        opts['sb_db_file'] = 'spiderbro.db'
    try:
        opts['use_whole_lib'] = config.getboolean("options", "scan_all_shows_xbmc")
    except:
        opts['use_whole_lib'] = False
    try:
        opts['polite'] = config.getboolean("options", "polite")
    except:
        opts['polite'] = False
    try:
        opts['polite_value'] = config.get("options", "polite_value")
    except:
        opts['polite_value'] = 5
    try:
        opts['force_learn'] = config.getboolean("options", "force_learn")
    except:
        opts['force_learn'] = False
    try:
        opts['tv_dir'] = config.get("options", "tv_dir")
    except:
        opts['tv_dir'] = "/media/twoTB1/videos/tv/"
    try:
        opts['shows_file'] = config.get("options", "shows_file")
    except:
        opts['shows_file'] = None
    try:
        opts['log_dir'] = config.get("options", "log_dir")
    except:
        opts['log_dir'] = "/home/gom/log"
    try:
        opts['use_debug_logging'] = config.getboolean("options", "use_debug_logging")
    except:
        opts['use_debug_logging'] = False
    try:
        opts['use_mysql'] = config.getboolean("options", "use_mysql")
    except:
        opts['use_mysql'] = False
    try:
        opts['host'] = config.get("options", "host")
    except:
        opts['host'] = None
    try:
        opts['user'] = config.get("options", "user")
    except:
        opts['user'] = None
    try:
        opts['passw'] = config.get("options", "passw")
    except:
        opts['passw'] = None
    try:
        opts['schema'] = config.get("options", "schema")
    except:
        opts['schema'] = None
    try:
        opts['xbmc_sqlite_db'] = config.get("options", "xbmc_sqlite_db")
    except:
        opts['xbmc_sqlite_db'] = "test.db"
    
    return opts

def get_series_id(series_name, op):
    l = logging.getLogger("spiderbro")
    d = db_manager()
    
    xbmc_id = d.xbmc_get_series_id(series_name)
    sb_id = d.get_show_info(series_name)

    # Edge case can happen here where show in xbmc but not in sb_db, so we make sure it is inserted
    if(xbmc_id and not sb_id):
        l.debug("No db entry found for show %s, creating default..." % series_name)
        d.add_show(xbmc_id[0][0], series_name, 0)

    # try and get series id from xbmc db first if force_id not True
    if(xbmc_id and not ('force_id' in op)):
        l.debug("\t\tGot series ID from XBMC: %s" % xbmc_id[0][0])
        return xbmc_id[0][0]

    # otherwise go to sb_db
    if sb_id:
        sid = sb_id[0][0]
        l.debug("\t\tGot series ID from Spiderbro Internal DB: %s" % sid)
        return sid
    # finally go to tvdb if all other options exhausted
    else:
        try:
            page = urllib2.urlopen("http://thetvdb.com/api/GetSeries.php?seriesname=%s" % urllib2.quote(series_name))
            soup = BeautifulSoup(page)
            sid = int(soup.data.series.seriesid.string)
            l.debug("\t\tGot series ID from tvdb: %s" % sid)
            d.add_show(sid, series_name, 0)
            return sid
        except Exception, e:
            l.error("Error retrieving series id: %s" % e)

def get_episode_list(series, o):
    aired_list = []
    have_list = []
    highest_season = 1
    ended = False
    series_name = series
    d = db_manager()
    l = logging.getLogger("spiderbro")
    l.info("Looking for eps for: %s" % (series_name))
    try:

        # get the series id from db or web
        series_id = get_series_id(series, o)

        # now get the info for the series
        data = BeautifulSoup(urllib2.urlopen("http://thetvdb.com/data/series/%s/all/" % str(series_id))).data
        if(data.series.status.string == "Ended"):
            ended = True

        # iterate through data, get list of season/episodes for show starting from 1 (0 are specials)
        for i in data.findAll('episode', recursive=False):
            if(i.seasonnumber.string != '0'):
                season = i.seasonnumber.string
                highest_season = max(highest_season, int(i.seasonnumber.string))
                ep = i.episodenumber.string
                try:
                    fa = i.firstaired.string.split('-')
                    airdate = date(int(fa[0]), int(fa[1]), int(fa[2]))
                    # need to compare current date to air date, ignore if not aired yet
                    if date.today() > airdate:
                        aired_list.append((season, ep))
                except:
                    pass
    except:
        l.error("\tCould not get episode list from thetvdb (timeout?)")
        l.error("")
        return [], False, highest_season

    try:
        # use the mysql lib to access xbmc db, cross check episode lists
        l = d.xbmc_get_eps_for_show(series_name)
        for i in l: have_list.append(i)

        # create new db con to torrents db, populate from here aswell
        l = d.get_eps_from_self(series_name)
        for s, e in l: have_list.append((str(s), str(e)))


    except ValueError as v:
        l.error("Database error?")
        l.error(str(v))
        sys.exit()

    have_s = list(set([h[0] for h in have_list]))
    aired_s = list(set([a[0] for a in aired_list]))
    if(ended):
        seas = [c for c in aired_s if c not in have_s]
    else:
        seas = [c for c in aired_s if((c not in have_s) and (int(c) < highest_season))]
    
    have_seas = [val for val in have_list if val[1] == "-1"]
    ep_list = [val for val in aired_list if val not in have_list]
    for s in seas:
        ep_list = [c for c in ep_list if c[0] != s]
        ep_list.append((s, "-1"))
    for h in have_seas:
        ep_list = [c for c in ep_list if c[0] != h[0]]

    return ep_list, ended, highest_season

def get_params(args):
    switches = ['--help', '--learn', '--polite', '--force_show', '--use_xbmc', '--verbose', "--force-id", "--high-quality", "--low-quality", "--clear-cache",
                '-h', '-l', '-p', '-s', '-v', '-x', "-id", "-hq", "-lq", "-cc"]
    opts = {}
    if len(args) > 1:
        for i in range(len(args)):
            if args[i] in switches:
                
                # --CLEAR-CACHE
                if(args[i] == "--clear-cache" or args[i] == "-cc"):
                    opts['clear_cache'] = True
                
                # --HQ
                if(args[i] == "--high-quality" or args[i] == "-hq"):
                    opts['high_quality'] = True
                
                # --LQ
                if(args[i] == "--low-quality" or args[i] == "-lq"):
                    opts['low_quality'] = True
                
                # --LEARN
                if(args[i] == "--learn" or args[i] == "-l"):
                    opts['force_learn'] = True
                
                # --USE_DEBUG_LOGGING
                if(args[i]== "--verbose" or args[i]== "-v"):
                    opts['use_debug_logging'] = True

                # --USE_XBMC
                if(args[i]== "--use_xbmc" or args[i]== "-x"):
                    opts['use_whole_lib'] = True

                # --SHOW
                if(args[i] == "--show" or args[i] == "-s"):
                    try:
                        if(args[i+1] not in switches):
                            opts['force_show'] = args[i+1]
                            opts['use_whole_lib'] = False
                        else:
                            print "please supply value for show to force"
                            sys.exit()
                    except:
                        print "please supply show to force"
                        sys.exit()
                
                # --FORCE-ID 
                if(args[i] == "--force-id" or args[i] == "-id"):
                    try:
                        if(args[i+1] not in switches):
                            opts['force_id'] = args[i+1]
                        else:
                            print "please supply value for id to force"
                            sys.exit()
                    except:
                        print "please supply value for id to force"
                        sys.exit()

                # --POLITE
                if(args[i] == "--polite" or args[i] == "-p" ):
                    try:
                        if(args[i+1] not in switches):
                            opts['polite_value'] = int(args[i+1])
                            opts['polite'] = True
                        else:
                            print "please supply integer value for polite wait period"
                            sys.exit()
                    except:
                        print "please supply polite param in the form of an integer"
                        sys.exit()
                
                # --HELP
                if(args[i]== "--help" or args[i]== "-h"):
                    print "Usage:"
                    print "spiderBro.py"
                    print "Options:"
                    
                    print "\t--learn or -l"
                    print "\t\t forces spiderBro to mark all episodes it cannot find in db (usual behaviour is to ignore ones from current season)"
                    
                    print "\t--polite or -p"
                    print "\t\t forces spiderBro to wait n seconds before opening a url (to prevent site admins from banning you for wasting their bandwidth)"
                    
                    print "\t--show or -s"
                    print "\t\t Forces scan of only show X (will add new shows to library if not in current library)"

                    print "\t--verbose or -v"
                    print "\t\t Turns on debug logging"

                    print "\t--usexbmc or -x"
                    print "\t\t Uses entire xbmc tv shows library"

                    print "\t--help or -h"
                    print "\t\tPrint help and exit"
                    sys.exit()

    return opts

def get_sb_log(o):
    start_time = str(datetime.today()).split(".")[0].replace(" ", "_")
    setupLogger()
    l = logging.getLogger("spiderbro")
    if (o['use_debug_logging'] == True):
        l.setLevel(logging.DEBUG)
    else:
        l.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
    handler_stream = logging.StreamHandler()
    handler_stream.setFormatter(formatter)
    handler_stream.setLevel(logging.CRITICAL)
    l.addHandler(handler_stream)
    handler_file = logging.FileHandler('%s/spiderBro_%s.log' % (o['log_dir'], start_time))
    handler_file.setFormatter(formatter)
    l.addHandler(handler_file)
    #l.info("Initiating Automatic Torrent Download [beep boop boop beep]")
    l.info("SpiderBro, SpiderBro")
    l.info("Finding episodes for your shows")
    log_debug_info(o)
    return l

def get_shows_from_file(fname):
    l = logging.getLogger('spiderbro')
    try:
        slist = []
        f = open(fname)
        try:
            for line in f:
                slist.append(line.replace("\n",""))
        finally:
            f.close()
            return slist
    except:
        l.error("Cannot open shows file, exiting")
        sys.exit()

#####################################################################################
# The function that actually grabs our episodes
#####################################################################################

def hunt_eps(series_name, opts, search_list, s_masks, e_masks, ignore_tags):
    l = logging.getLogger('spiderbro')
    d = db_manager()
    dir = opts['tv_dir'] + series_name.replace(" ", "_").replace("'", "").lower()
    is_high_quality = d.get_show_high_quality(series_name)

    ep_list, ended, highest_season = get_episode_list(series_name, opts)

    if ended and not ep_list:
        l.info("\tGot all episodes for this, skipping in future")
        d.mark_show_finished(series_name)
    elif ep_list:
        # search for sX eX using every search site and every filemask until torrent is found
        for s, e in ep_list:
            l.debug("DEBUG EPISODE IS: %s", e)
            found = False
            # if searching for full season season use season mask list
            if(e == "-1"):
                l.info("Searching for entire season %s of %s" % (s, series_name))
                masks_list = s_masks
            else:
                masks_list = e_masks
            for site_ctor in search_list:
                if not found:
                    for mk_ctor in masks_list:
                        if opts['polite']: time.sleep(opts['polite_value'])
                        site = site_ctor()
                        try:
                            url = site.search(series_name, s, e, mk_ctor, ignore_tags, is_high_quality)
                            if url:
                                l.info("\t\tFound torrent: %s" % url)
                                dict = {'url':url, "save_dir":dir, 'showname':series_name, "season":s, "episode":e}
                                dl_these.append(dict)
                                found = True
                                break
                        except AttributeError as ex:
                            l.error("%s timed out?" % ex)
                        except Exception, e:
                            l.error("Error: %s" % e)
                            traceback.print_exc()
                            #sys.exit()
            if not found:
                #check episode is not in current season, do not search again if so
                ep_season = int(s)
                if ((ep_season < highest_season) or (opts['force_learn']) or ended):
                    l.info("Cannot find torrent for: %s season %s episode %s - skipping this in future" % (series_name, s, e))
                    d.add_to_urls_seen(series_name, s, e, "None")
            l.info("")

#####################################################################################
# Print out some debugging info about params
#####################################################################################

def log_debug_info(o):
    l = logging.getLogger("spiderbro")
    l.debug("")
    l.debug("Using params:")
    sopts = o.keys()
    sopts.sort()
    for k in sopts:
        l.debug("%s: %s" % (k, o[k]))
    l.debug("")

#####################################################################################
# Deferred callback function to be called when an error is encountered
#####################################################################################

def on_connect_fail(result):
    l = logging.getLogger('spiderbro')
    l.info("Connection failed!")
    l.info("result: %s" % result)
    sys.exit()

#####################################################################################
# Deferred callback function called when we connect
#####################################################################################

def on_connect_success(result):
    d = db_manager()
    l = logging.getLogger('spiderbro')
    init_list = []
    l.info("Connection to deluge was successful, result code: %s" % result)
    # need a callback for when torrent added completes
    def add_tor(key, val):
        l.info("Added torrent url to deluge: %s" % (val))
    
    # TODO: get rid of this nasty global variable
    for tp in dl_these:
        di = {'download_location':tp['save_dir']}
        df = client.core.add_torrent_url(tp["url"], di).addCallback(add_tor, tp["url"])
        init_list.append(df)
        #add url to database - ideally would be nice to do this in callback, but dont have info there?
        d.add_to_urls_seen(tp['showname'], tp['season'], tp['episode'], tp['url'])

    dl = defer.DeferredList(init_list)
    dl.addCallback(dl_finish)


def setup_db_manager(opts):
    d = db_manager()

    if("sb_db_file" in opts):
        d.init_sb_db(opts['sb_db_file'])
    else:
        d.init_sb_db('spiderbro.db')

    if(opts["use_mysql"]):
        d.xbmc_init_mysql(opts["host"], opts["user"], opts["passw"], opts["schema"])
    else:
        d.xbmc_init_sqlite(opts["xbmc_sqlite_db"])

