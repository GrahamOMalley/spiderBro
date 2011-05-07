#! /usr/bin/env python

import string
import urllib2
from BeautifulSoup import BeautifulSoup
from datetime import date
from datetime import datetime
import MySQLdb
import re
from deluge.ui.client import client
from twisted.internet import defer
from twisted.internet import reactor
from deluge.log import setupLogger
import logging
import sys
import ConfigParser

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
        e = "0" + ep if(int(ep)<10) else "e" + ep
        return ("%sx%s" % (sn, e))
       
class piratebaysearch:
    def __init__(self):
        self.name = "piratebay"
    def search(self, series_name, sn, ep, fmask):
        is_torrent = re.compile(".*torrent$")
        m = fmask()
        val = m.mask(sn, ep)
        search_url = "http://thepiratebay.org/search/" + "+".join(series_name.split(" ")).replace("'","") + "+" + val + "/0/7/0"
        response = urllib2.urlopen(search_url)
        search_page = response.read()
        sps = BeautifulSoup(search_page)
        links = sps.findAll('a', href=re.compile("^http"))
        url = ""
        if(is_torrent.match(links[0]['href'])):
            if(val in links[0]['href'].lower()):
                if("swesub" not in links[0]['href'].lower()):
                    url = links[0]['href']
        return url

class btjunkiesearch:
    def __init__(self):
        self.name = "btjunkie"
    def search(self, series_name, sn, ep, fmask):
        is_torrent = re.compile(".*torrent$")
        g = re.compile(r'Good\((.*?)\)', re.DOTALL)
        f = re.compile(r'Fake\((.*?)\)', re.DOTALL) 
        url = ""
        m = fmask()
        val = m.mask(sn, ep)
        good = 0
        fake = 0
        search_url = "http://btjunkie.org/search?q=" + "+".join(series_name.split(" ")).replace("'","") + "+" + val
        response = urllib2.urlopen(search_url)
        search_page = response.read()
        response.close()
        sps = BeautifulSoup(search_page)
        links = sps.findAll('a', href=re.compile("^http"))
        if links:
            if(is_torrent.match(links[0]['href'])):
                if(val in links[0]['href'].lower()):
                    if("swesub" not in links[0]['href'].lower()):
                        turl = links[0]['href'].replace("/download.torrent", "").replace("dl.", "")
                        resp = urllib2.urlopen(turl)
                        # due to btjunkie having occasional broken/fake torrents, need some additional validation
                        validate_page = resp.read()
                        val_tags = BeautifulSoup(validate_page)
                        b = val_tags.findAll('b')
                        for bs in b:
                            if bs.string:
                                if g.match(bs.string):
                                    good = int(g.findall(bs.string)[0])
                                    l = bs.string.split(" ")
                                    for v in l:
                                        if f.match(v):
                                            fake = int(f.findall(v)[0])
                    if(good > fake):
                        url = links[0]['href']
        return url
