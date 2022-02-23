#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os, string, time, types
from lxml import etree
import urllib.request
import urllib.parse

username = ''
password = ''

vat = { 
        "high" : "typSzbDph.dphZakl",
        "low"  : "typSzbDph.dphSniz"
}

namespaces = {
        'dat' : 'http://www.stormware.cz/schema/version_2/data.xsd',
        'inv' : 'http://www.stormware.cz/schema/version_2/invoice.xsd',
        'typ' : 'http://www.stormware.cz/schema/version_2/type.xsd'
} 



class readerPohoda:
    def __init__(self):
        self.map = {
                "inv-type"      : ".//inv:invoiceType/text()",
                "code"          : ".//typ:numberRequested/text()",
                "order-num"     : ".//inv:numberOrder/text()",

                "sym-var"       : ".//inv:symVar/text()",            # variabilni symbol

                "date"          : ".//inv:date/text()",              # datum
                "date-tax"      : ".//inv:dateTax/text()",           # danitelne plneni
                "date-due"      : ".//inv:dateDue/text()",           # splatnost

                "addr-name"     : ".//typ:address/typ:name/text()",
                "addr-street"   : ".//typ:address/typ:street/text()",
                "addr-city"     : ".//typ:address/typ:city/text()",
                "addr-zip"      : ".//typ:address/typ:zip/text()",

                "ico"           : ".//typ:address/typ:ico/text()",
                "dic"           : ".//typ:address/typ:dic/text()",

                "sum"           : ".//inv:invoiceSummary//typ:priceLowSum/text()",

                "inv-items"     : {
                    "__count__" : "count(.//inv:invoiceItem)",
                    "name"      : ".//inv:invoiceItem[%d]/inv:text/text()",
                    "quantity"  : ".//inv:invoiceItem[%d]/inv:quantity/text()",
                    "unit"      : ".//inv:invoiceItem[%d]/inv:unit/text()",
                    "priceUnit":  ".//inv:invoiceItem[%d]/inv:homeCurrency/typ:unitPrice/text()",
                    "price"     : ".//inv:invoiceItem[%d]/inv:homeCurrency/typ:price/text()",
                    "priceVAT"  : ".//inv:invoiceItem[%d]/inv:homeCurrency/typ:priceVAT/text()",
                    "rateVAT"   : ".//inv:invoiceItem[%d]/inv:rateVAT/text()",                        # low/hight
                    "payVAT"    : ".//inv:invoiceItem[%d]/inv:payVAT/text()"
                }
        }

    def readXML(self, inv, root):
        self.doc = root
        self.readByMap(self.map, inv)

    def readByMap(self, m, inv):
        for key in list(m.keys()):
            if  isinstance(m[key], dict):
                self.readSubMap(key, m[key], inv)
            else:
                self.itemFromXML(key, m[key], inv)

    def readSubMap(self, key, m, inv):
        path = m['__count__']
        count = int(self.doc.xpath(path, namespaces=namespaces))
        if count == 0.0:
            return
        inv[key] = []
        for i in range(1, count+1):
            subinv = {}
            for k in list(m.keys()):
                if k == '__count__':
                    continue
                self.itemFromXML(k, m[k] % i, subinv)
            inv[key].append(subinv)

    def itemFromXML(self, key, path, inv):
            x = self.doc.xpath(path, namespaces=namespaces)
            if len(x) == 0:
                return
            if type(x[0]) in [etree._ElementStringResult, etree._ElementUnicodeResult]:
                inv[key] = x[0]  # text
            else:
                inv[key] = x     # list or object


class writerFlexiBee:
    def __init__(self, ignoreZeroPrice=True, codePrefix='', typePostfix=''):
        self.map = {}
        self.last_addr_id = ''
        self.ignoreZeroPrice = ignoreZeroPrice
        self.codePrefix = codePrefix
        self.typePostfix = typePostfix

    def appendTextItem(self, parent, name, itemname, inv):
        if itemname in inv:
            etree.SubElement(parent, name).text = inv[itemname]

    def generateAddress(self, parent, inv):
        self.appendTextItem(parent, "nazFirmy", "addr-name", inv)
        self.appendTextItem(parent, "ulice", "addr-street", inv)
        self.appendTextItem(parent, "mesto", "addr-city", inv)
        self.appendTextItem(parent, "psc", "addr-zip", inv)
        self.appendTextItem(parent, "ic", "ico", inv)
        self.appendTextItem(parent, "dic", "dic", inv)

    def vatToSymbol(self, inv, name, code):
        if inv[name] == "none": 
            print("Unspecified rateVAT; code: %s\nwho: %s" % (code, inv), file=sys.stderr)
            sys.exit(1)
        return vat[inv[name]]

    def isDobropis(self, inv):
        if "inv-type" in inv and inv["inv-type"] == "issuedCorrectiveTax":
            return True
        return False

    def generateInvDataItems(self, parent, inv, code):
        polRoot = etree.SubElement(parent, "polozkyFaktury")
    
        for i in inv["inv-items"]:
            if self.ignoreZeroPrice:
                price = 0.0
                if "price" in i:
                    price = float(i["price"])
                if price == 0.0:
                    continue
            pol = etree.SubElement(polRoot, "faktura-vydana-polozka")
            self.appendTextItem(pol, "nazev", "name", i)
            self.appendTextItem(pol, "mnozMj", "quantity", i)
            self.appendTextItem(pol, "cenaMj", "priceUnit", i) 
            self.appendTextItem(pol, "sumZkl", "price", i)
            self.appendTextItem(pol, "sumDph", "priceVAT", i)
            if "rateVAT" in i:
                etree.SubElement(pol, "typSzbDphK").text = self.vatToSymbol(i, "rateVAT", code)

    def orderToInvoiceCode(self, order):
        if len(password) == 0 or len(username) == 0:
            print(" no password", file=sys.stderr)
            return ''
        data = {}
        data['detail'] = 'custom:kod'
        data['xpath']  = '//kod/text()'
        url_values = urllib.parse.urlencode(data)
        url = 'https://zakova.flexibee.eu:5434'
        url_filter = "%28cisObj%3D%27" + order + "%27%20and%20typDokl%3D%27code%3AFAKTURA-DOB%C3%8DRKA%27%29.xml"
        url_path = "/c/radka_sekyrova/faktura-vydana/"
        url_full = url + url_path + url_filter + '?' + url_values

        #print("KZAK>>> %s" % url_full, file=sys.stderr)

        try:
            passman = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            passman.add_password(None, url, username, password)
            authhandler = urllib.request.HTTPBasicAuthHandler(passman)
            opener = urllib.request.build_opener(authhandler)
            urllib.request.install_opener(opener)
            res = urllib.request.urlopen(url_full)
        except:
            return ''

        return res.read().decode('utf-8')

    def generateInvData(self, doc, inv):
        fak = etree.SubElement(doc, "faktura-vydana")

        code = inv["code"]

        if self.isDobropis(inv):
            etree.SubElement(fak, "id").text = "code:%s%s" % (self.codePrefix, code)
            etree.SubElement(fak, "typDokl").text = "code:DOBROPIS-DOBÍRKA"
            fcode = self.orderToInvoiceCode(inv["order-num"])
            if len(fcode) > 0:
                print("Vazba: %s -> %s" % (code, fcode), file=sys.stderr)
                dob = etree.SubElement(fak, "vytvor-vazbu-dobropis")
                etree.SubElement(dob, "dobropisovanyDokl").text = "code:%s" % fcode
            else:
                print("Dobropis %s nema vazbu (objednavka=%s)" % (code, inv["order-num"]), file=sys.stderr)
        else:
            etree.SubElement(fak, "id").text = "code:%s%s" % (self.codePrefix, code)
            etree.SubElement(fak, "typDokl").text = "code:FAKTURA-DOBÍRKA%s" % self.typePostfix

        if len(self.last_addr_id):
            etree.SubElement(fak, "firma").text = self.last_addr_id

        etree.SubElement(fak, "typUcOp").text = "code:DP1-ZBOŽÍ"
        etree.SubElement(fak, "cinnost").text = "code:PRODEJ-ZBOŽÍ"
        etree.SubElement(fak, "formaUhradyCis").text = "code:DOBIRKA"
        etree.SubElement(fak, "clenKonVykDph").text = "code:A.4-5.AUTO"
        #etree.SubElement(fak, "stavUhrK").text = "stavUhr.uhrazenoRucne"

        self.appendTextItem(fak, "varSym", "sym-var", inv)
        self.appendTextItem(fak, "datVyst", "date", inv)
        self.appendTextItem(fak, "datSplat", "date-due", inv)
        self.appendTextItem(fak, "duzpPuv", "date-tax", inv)
        self.appendTextItem(fak, "cisObj", "order-num", inv)
       
        self.generateAddress(fak, inv)
        self.generateInvDataItems(fak, inv, code)

    def writeXML(self, inv, root):
        self.generateInvData(root, inv)


class Invoice:
    def __init__(self, reader=None, writer=None):
        self.__dict__ = {}
        self.reader = reader
        self.writer = writer

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



def unpackPohoda(filename):
    try:
        doc = etree.parse(filename)
    except:
        self.error('Failed to parse %s' % filename)

    return doc.xpath('//inv:invoice', namespaces=namespaces)

def makeFlexiBeeTree():
    return etree.Element("winstrom", version="1.0")

def packFlexiBee(tree):
    print( "<?xml version='1.0' encoding='utf-8'?>")
    print( etree.tounicode(tree, method='xml', pretty_print=True))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: %s <filename> <codePrefix> <typePostfix>" % sys.argv[0])
        sys.exit(1)
    
    pohoda = unpackPohoda(sys.argv[1])
    bee    = makeFlexiBeeTree()

    for p in pohoda:
        inv = Invoice(readerPohoda(),
                      writerFlexiBee(ignoreZeroPrice=True, codePrefix=sys.argv[2], typePostfix=sys.argv[3]))
        inv.readFromXML(p)
        inv.writeToXML(bee)
        del inv

    packFlexiBee(bee)
    

