#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os, string, time, types
from lxml import etree
import urllib.request
import urllib.parse

username = ''
password = ''


class readerBank:
    def __init__(self):
        self.map = {
                "id"        : ".//id/text()",
                "sum"       : ".//sumCelkem/text()",
                "var"       : ".//varSym/text()"
        }

    def readXML(self, bank, root):
        self.doc = root
        self.readByMap(self.map, bank)

    def readByMap(self, m, bank):
        for key in list(m.keys()):
            self.itemFromXML(key, m[key], bank)

    def itemFromXML(self, key, path, bank):
            x = self.doc.xpath(path)
            if len(x) == 0:
                return
            if type(x[0]) in [etree._ElementStringResult, etree._ElementUnicodeResult]:
                bank[key] = x[0]  # text
            else:
                bank[key] = x     # list or object


class writerFlexiBee:
    def __init__(self):
        self.map = {}

    def appendTextItem(self, parent, name, itemname, bank):
        if itemname in bank:
            etree.SubElement(parent, name).text = bank[itemname]

    def generateSparovani(self, parent, bank):
        sp = etree.SubElement(parent, "sparovani")
        etree.SubElement(sp, "uhrazovanaFak", type="faktura-vydana", castka=bank["sum"]).text = "code:%s" % bank["var"]
        etree.SubElement(sp, "zbytek").text = "ne"

    def generateData(self, doc, bank):
        ba = etree.SubElement(doc, "banka")
        etree.SubElement(ba, "id").text = "code:%s" % bank["id"]
        self.generateSparovani(ba, bank)

    def writeXML(self, bank, root):
        self.generateData(root, bank)


class Sparovani:
    def __init__(self, reader=None, writer=None):
        self.__dict__ = {}
        self.reader = reader
        self.writer = writer

    def verifyCode(self, urlreq):
        code = self["var"]
        data = {}
        data['xpath']  = '//sumCelkem/text()'

        url_path = "/c/radka_sekyrova/faktura-vydana/"
        url_values = urllib.parse.urlencode(data)

        for x in ('R','E'):
            code = "%s%s" % (x, self["var"])
            url_filter = "(kod='" + code + "').xml"
            url_full = url + url_path + url_filter + '?' + url_values
            #print("KZAK>>> %s" % url_full, file=sys.stderr)
            try:
                res = urlreq.urlopen(url_full).read().decode('utf-8')
            except:
                return False

            if res == self["sum"]:
                #print("KZAK>>> match %s" % code)
                self["var"] = code
                return True

        return False

    def __str__(self):
        res = ""
        for key in list(self.items.keys()):
            res += "%s: %s\n" % (key, self.items[key].encode('ascii', 'replace'))
        return res

    def __setitem__(self, key, data):
        self.__dict__[key] = data

    def __getitem__(self, key):
        return self.__dict__[key]
       
    def __len__(self):
        return len(self.__dict__)

    def __delitem__(self, key):
        del self.__dict__[key]

    def clear(self):
        return self.__dict__.clear()

    def copy(self):
        return self.__dict__.copy()

    def has_key(self, k):
        return k in self.__dict__

    def update(self, *args, **kwargs):
        return self.__dict__.update(*args, **kwargs)

    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()

    def items(self):
        return self.__dict__.items()

    def pop(self, *args):
        return self.__dict__.pop(*args)

    def __cmp__(self, dict_):
        return self.__cmp__(self.__dict__, dict_)

    def __contains__(self, item):
        return item in self.__dict__

    def __iter__(self):
        return iter(self.__dict__)

    def __unicode__(self):
        return unicode(repr(self.__dict__))

    def readFromXML(self, root):
        self.reader.readXML(self, root)

    def writeToXML(self, root):
        self.writer.writeXML(self, root)



def unpackBank(filename):
    try:
        doc = etree.parse(filename)
    except:
        self.error('Failed to parse %s' % filename)
    return doc.xpath('//banka')

def makeFlexiBeeTree():
    return etree.Element("winstrom", version="1.0")

def packFlexiBee(tree):
    print( "<?xml version='1.0' encoding='utf-8'?>")
    print( etree.tounicode(tree, method='xml', pretty_print=True))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: %s <filename>" % sys.argv[0])
        sys.exit(1)
    
    bank = unpackBank(sys.argv[1])
    bee  = makeFlexiBeeTree()
    i = 1

    print("%d items" % len(bank), file=sys.stderr)

    url = 'https://zakova.flexibee.eu:5434'
    passman = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    passman.add_password(None, url, username, password)
    authhandler = urllib.request.HTTPBasicAuthHandler(passman)
    opener = urllib.request.build_opener(authhandler)
    urllib.request.install_opener(opener)

    for b in bank:
        spar = Sparovani(readerBank(), writerFlexiBee())
        spar.readFromXML(b)
        if not spar.has_key("var"):
            continue
        if spar.verifyCode(urllib.request):
            print("%04d: %12s [%9s kc] : ok" % (i, spar["var"], spar["sum"]), file=sys.stderr)
            spar.writeToXML(bee)
        else:
            print("%04d: %12s [%9s kc] : ignore" % (i, spar["var"], spar["sum"]), file=sys.stderr)
        i+=1

    packFlexiBee(bee)
