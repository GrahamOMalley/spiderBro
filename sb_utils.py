#! /usr/bin/env python
import ConfigParser
import argparse
import logging
import re
import string
import sys
import time
import traceback
import urllib2

from BeautifulSoup import BeautifulSoup
from datetime import date
from datetime import datetime
from deluge.log import setupLogger
from deluge.ui.client import client
from twisted.internet import defer
from twisted.internet import reactor

from db_manager import db_manager

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
        self.can_get_tor_from_main_page = True

    def search(self, series_name, sn, ep, fmask, tags, is_high_qual):
        lg = logging.getLogger('spiderbro')
        series_name = series_name.replace("::", "")
        series_name = series_name.replace(": ", " ")
        series_name = series_name.replace(":", " ")
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
            links = sps.findAll('a', href=re.compile(self.get_links_from_main_page_re()))
            for l in links:
                if self.validate_link(series_search_term, season_or_ep_str, l['href'], tags, is_high_qual, is_season):
                    if self.validate_page(l['href']):
                        if self.can_get_tor_from_main_page:
                            return l['href']
                        else:
                            return self.get_torrent_from_validated_page(l['href'])
        return ""

    def get_links_from_main_page_re(self):
        lg = logging.getLogger('spiderbro')
        lg.debug("\tbase: get links from main page using regexp: ^http")
        return "^http"

    def get_torrent_from_validated_page(self, page):
        lg = logging.getLogger('spiderbro')
        lg.debug("base: get torrent from validated page using regexp: \"\"")
        return ""

    def validate_link(self, series, s_ep_str, link, tags, is_high_q, is_season):
        lg = logging.getLogger('spiderbro')
        # First validate the link title is ok
        is_torrent = re.compile(self.get_is_link_a_torrent_re())
        if(not is_torrent.match(link)):
            return False
        else:
            lg.debug('\t\tValidating %s' % (link))
            
        if (is_high_q and not (("720p" in link.lower()) or ("1080p" in link.lower()))): 
            lg.debug("\t\t\tValidation FAILED: Quality is HighQ but 720p not found in torrent")
            return False

        if ( not is_high_q and (("720p" in link.lower()) or ("1080p" in link.lower()))): 
            lg.debug("\t\t\tValidation FAILED: Quality is lowQ but 720p found in torrent")
            return False

        for t in tags:
            if t.lower() in link.lower(): 
                lg.debug("\t\t\tValidation FAILED: tag filter %s found in torrent" % t)
                return False
        
        if is_season: 
            # we are searching for a torrent of an entire season
            s_ep_str = s_ep_str.replace(" ", self.delimiter).lower()
            if (s_ep_str in link.lower() or (s_ep_str.replace(self.delimiter, self.delimiter+"0") in link.lower())):
                return True
        else:
            # we are searching for an episode
            if (s_ep_str in link.lower() and  self.delimiter.join(series.split(" ")).lower() in link.lower()):
                return True
            else:
                lg.debug("\t\t\tValidation FAILED: s_ep_str %s or %s not found in link title" % (s_ep_str, self.delimiter.join(series.split(" ")).lower()))

        
        return False

    # child classes can define their own site-specific page validation, see piratebaysearch for an example
    def validate_page(self, tor):
        lg = logging.getLogger('spiderbro')
        lg.debug("\tbase: validate page (return true)")
        return True

    # break the series name up and try different variations of it 
    # eg: "Blah & Blah (2010)" -> ["Blah & Blah (2010)", "Blah & Blah", "Blah and Blah (2010)", "Blah and Blah"] etc
    def generate_search_terms(self, name):
        regser = re.compile(" \([0-9a-zA-Z]{2,4}\)").sub('', name)
        li = [name, regser]
        
        hli =[]
        for l in li:
            hyphen = " ".join(l.split("-"))
            hli.append(hyphen)
        if hli: li.extend(hli)

        for l in li:
            hyphen = " ".join(l.split(":"))
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

    def get_is_link_a_torrent_re(self):
        return ".*torrent$"

# Child classes need to define self.delimiter, get_search_url and optionally validate_page 
class piratebaysearch(base_search):
    def __init__(self):
        self.name = "piratebay"
        self.delimiter = "+"
        self.can_get_tor_from_main_page = True

    def get_is_link_a_torrent_re(self):
        return "^magnet"

    def get_links_from_main_page_re(self):
        lg = logging.getLogger('spiderbro')
        lg.debug("\tpiratebay: get links from main page using regexp: ^magnet")
        return "^magnet"

    def get_search_url(self, name, maskval):
        return "http://thepiratebay.se/search/"+"+".join(name.split(" ")).replace("'","")+"+"+"+".join(maskval.split(" ")) + "/0/7/0"
    
    def validate_page(self, tor):
        return True
        seeds = 0
        seeds_reg = re.compile("Seeders:</dt>\n<dd>[0-9]{1,9}")
        lg = logging.getLogger('spiderbro')
        lg.debug("\t\tDoing piratebay page validation")
        turl = tor.replace("http://torrents.thepiratebay.se", "http://thepiratebay.se/torrent")
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

class extratorrentsearch(base_search):
    def __init__(self):
        self.name = "extratorrent"
        self.delimiter = "."
        self.can_get_tor_from_main_page = False

    def get_links_from_main_page_re(self):
        return ".*torrent$"

    def get_search_url(self, name, maskval):
        return "http://extratorrent.com/search/?search=" + "+".join(name.split(" ")).replace("'","")+"+"+"+".join(maskval.split(" ")) + "&new=1&x=0&y=0"

    def validate_page(self, tor):
        lg = logging.getLogger('spiderbro')
        lg.debug("\t\tDoing extratorrent page validation for: "+tor)
        lg.debug("\t\tNot Implemented: extratorrent page validation, returning true")
        return True

    def get_torrent_from_validated_page(self, page):
        lg = logging.getLogger('spiderbro')
        lg.debug("\t\tConverting torrent url to ext format : "+page)
        return "http://extratorrent.com" + page.replace("torrent_", "")

class isohuntsearch(base_search):
    def __init__(self):
        self.name = "isohunt"
        self.delimiter = "+"
        self.can_get_tor_from_main_page = False

    def get_links_from_main_page_re(self):
        return ".*"

    def get_is_link_a_torrent_re(self):
        return ".*tab=summary$"

    def get_search_url(self, name, maskval):
        return "http://isohunt.com/torrents/" + "+".join(name.split(" ")).replace("'","")+"+"+"+".join(maskval.split(" ")) + "?iht=-1&ihp=1&ihs1=1&iho1=d"

    def get_torrent_from_validated_page(self, page):
        turl = "http://www.isohunt.com" + page
        resp = urllib2.urlopen(turl)
        val_page = resp.read()
        val_tags = BeautifulSoup(val_page)
        links = val_tags.findAll('a', href=re.compile("ca.*torrent"))
        for l in links:
            return string.lower(l['href'])
        return ""

    def validate_page(self, tor):
        lg = logging.getLogger('spiderbro')
        lg.debug("\t\tDoing isohunt page validation for: "+tor)
        lg.debug("\t\tNot Implemented: isohunt page validation, returning true")
        return True

# RIP BTJunkie :(
# leaving this dead class here as an example of how to override the base class
class btjunkiesearch(base_search):
    def __init__(self):
        self.name = "btjunkie"
        self.delimiter = "-"
    
    def get_search_url(self, name, maskval):
        return "http://btjunkie.se/search?q="+"+".join(name.split(" ")).replace("'","")+"+"+"+".join(maskval.split(" "))

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
            if(i['src'] == "http://static.btjunkie.se/images/verified_check1.gif"):
                lg.debug("\t\tValidated (validation check image is present)")
                return True

        # otherwise check if good > fake (Check seeds > 0)
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

def configure_all():
    # Set up config file
    conf_parser = argparse.ArgumentParser(add_help=False)
    conf_parser.add_argument("--conf_file", help="Specify config file", metavar="FILE", default="/home/gom/code/python/spider_bro/config.ini")
    args, remaining_argv = conf_parser.parse_known_args()
    defaults = {"tv_dir" : "some default",}
    if args.conf_file:
        config = ConfigParser.SafeConfigParser()
        config.read([args.conf_file])
        defaults = dict(config.items("spiderbro"))

    # Don't surpress add_help here so it will handle -h
    parser = argparse.ArgumentParser(parents=[conf_parser], formatter_class=argparse.RawDescriptionHelpFormatter, description='Spiderbro! Spiderbro! Finding episodes for your shows!')
    parser.add_argument('--test',  action="store_true", default=False, help='Don\'t actually download episodes')
    parser.add_argument('--debug_logging',  action="store_true", default=False, help='Turn on Debug Logging')
    parser.add_argument('--xbmc_sqlite_db', type=str, required=False, default="", help='XBMC SQLite DB')
    parser.add_argument('--mysql',  action="store_true", default=True, help='Use Mysql DB')

    parser.add_argument('--host', type=str, required=False, default="", help='Mysql host')
    parser.add_argument('--user', type=str, required=False, default="", help='Mysql user')
    parser.add_argument('--pwd', type=str, required=False, default="", help='Mysql password')
    parser.add_argument('--schema', type=str, required=False, default="", help='MySql schema')

    parser.add_argument('-a', '--all',  action="store_true", default=True, help='Find episodes for all shows')
    parser.add_argument('-cc', '--clear_cache',  action="store_true", default=False, help='Clear the internal SB episode cache for show(s)')
    parser.add_argument('-f', '--use_file_renamer',  action="store_true", default=True, help='Use the file_renamer script after torrent downloads')
    parser.add_argument('-hq', '--high_quality',  action="store_true", default=False, help='Switch show to high quality')
    parser.add_argument('-lq', '--low_quality',  action="store_true", default=False, help='Switch show to low quality')
    parser.add_argument('-l', '--force_learn',  action="store_true", default=False, help='Force SB to mark episode(s) as downloaded')
    parser.add_argument('-p', '--polite',  action="store_true", default=False, help='Wait N seconds before opening each url')
    parser.add_argument('-v', '--verbose',  action="store_true", default=False, help='Verbose output')

    parser.add_argument('-d', '--db_file', type=str, required=False, default='spiderbro.db', help='Spiderbro internal database file')
    parser.add_argument('-ld', '--log_dir', type=str, required=False, default="log", help='Logging Dir')
    parser.add_argument('-pv', '--polite-value', type=int, required=False, default=5, help='Num seconds for polite')
    parser.add_argument('-s', '--show', type=str, required=False, help='Find episodes for a single show')
    parser.add_argument('-t', '--tv_dir', type=str, required=False, default='/home/gom/nas/tv/', help='TV directory')
    parser.add_argument('--force_id', type=str, required=False, help='Force a show to change its id')

    parser.set_defaults(**defaults)
    args = parser.parse_args(remaining_argv)
    print args
    return args

#################################################################################################################
# 
#################################################################################################################
def setup_db_manager(opts):
    d = db_manager()

    if(opts.db_file):
        d.init_sb_db(opts.db_file)
    else:
        d.init_sb_db('spiderbro.db')

    if(opts.mysql):
        d.xbmc_init_mysql(opts.host, opts.user, opts.pwd, opts.schema) 
    else: 
        d.xbmc_init_sqlite(opts.xbmc_sqlite_db) 
    db_do_opts(opts)

#################################################################################################################
# force database items from params
#################################################################################################################
def db_do_opts(opts):
    lg = logging.getLogger('spiderbro')
    db = db_manager()

    if(opts.clear_cache and opts.show):
        lg.info("Clearing db cache for show %s" % (opts.show))
        db.clear_cache(opts.show)
    
    if(opts.high_quality and opts.show):
        lg.info("Changing quality to high for show %s" % (opts.show))
        db.set_quality(opts.show, 1)
    
    if(opts.low_quality and opts.show):
        lg.info("Changing quality to low for show %s" % (opts.show))
        db.set_quality(opts.show, 0)
    
    if(opts.force_id and opts.show):
        lg.info("Forcing new id %s for show %s" % (opts.force_id, opts.show))
        db.update_series_id(opts.show, opts.force_id)
    

#####################################################################################
# Functions to retrieve configs, episodelists etc
#####################################################################################


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
                ep = i.episodenumber.string
                try:
                    fa = i.firstaired.string.split('-')
                    airdate = date(int(fa[0]), int(fa[1]), int(fa[2]))
                    # need to compare current date to air date, ignore if not aired yet
                    if date.today() > airdate:
                        aired_list.append((season, ep))
                        highest_season = max(highest_season, int(i.seasonnumber.string))
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

def get_sb_log(o):
    start_time = str(datetime.today()).split(".")[0].replace(" ", "_")
    setupLogger()
    l = logging.getLogger("spiderbro")
    if (o.debug_logging == True):
        l.setLevel(logging.DEBUG)
    else:
        l.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
    handler_stream = logging.StreamHandler()
    handler_stream.setFormatter(formatter)
    handler_stream.setLevel(logging.CRITICAL)
    l.addHandler(handler_stream)
    handler_file = logging.FileHandler('%s/spiderBro_%s.log' % (o.log_dir, start_time))
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

def normalize_series_name(name):
    dir_id = name
    dir_id = str.lower(dir_id)
    dir_id = dir_id.replace("::", "")
    dir_id = dir_id.replace(": ", " ")
    dir_id = dir_id.replace(":", " ")
    dir_id = "".join(ch for ch in dir_id if ch not in ["!", "'", ":", "(", ")", ".", ","])
    dir_id = dir_id.replace("&", "and")
    dir_id = dir_id.replace(" ", "_") 
    return dir_id
    

def hunt_eps(series_name, opts, search_list, s_masks, e_masks, ignore_tags):
    l = logging.getLogger('spiderbro')
    d = db_manager()
    dir_id = normalize_series_name(series_name)
    dir = opts.tv_dir + dir_id

    
    is_high_quality = d.get_show_high_quality(series_name)

    ep_list, ended, highest_season = get_episode_list(series_name, opts)

    if ended and not ep_list:
        l.info("\tGot all episodes for this, skipping in future")
        d.mark_show_finished(series_name)
    elif ep_list:
        # search for sX eX using every search site and every filemask until torrent is found
        for s, e in ep_list:
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
                        if opts.polite: time.sleep(opts.polite_value)
                        site = site_ctor()
                        try:
                            url = site.search(series_name, s, e, mk_ctor, ignore_tags, is_high_quality)
                            if url:
                                l.info("\t\tFound torrent: %s" % url)
                                save_dir = dir
                                if(opts.use_file_renamer):
                                    save_dir = dir + "s" + s + "e" + e
                                dict = {'url':url, "save_dir":save_dir, 'showname':series_name, "season":s, "episode":e}
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
                # something goes weird here; opts.force_learn always evaluates as True using 'or opts.force_learn' - why?
                if ((ep_season < highest_season) or ended or opts.force_learn == True):
                    l.info("Cannot find torrent for: %s season %s episode %s - skipping this in future" % (series_name, s, e))
                    d.add_to_urls_seen(series_name, s, e, "None", "None")
            l.info("")

#####################################################################################
# Print out some debugging info about params
#####################################################################################

def log_debug_info(o):
    l = logging.getLogger("spiderbro")
    l.debug("")
    l.debug("Using params:")
    #sopts = o.keys()
    #sopts.sort()
    #for k in sopts:
        #l.debug("%s: %s" % (k, o[k]))
    #l.debug("")

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

#####################################################################################
# Deferred callback function for clean exit
#####################################################################################

def dl_finish(result):
    l = logging.getLogger('spiderbro')
    l.info("All deferred calls have fired, exiting program...")
    client.disconnect()
    # Stop the twisted main loop and exit
    reactor.stop()


