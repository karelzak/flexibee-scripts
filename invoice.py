#!/usr/bin/env python

import sys, os, string, time, zlib, types
from lxml import etree

vat = { 
        "high" : "21",
        "low"  : "15"
}

class readerPohoda:
    def __init__(self):
        self.ns = {
            'dat' : 'http://www.stormware.cz/schema/version_2/data.xsd',
            'inv' : 'http://www.stormware.cz/schema/version_2/invoice.xsd',
            'typ' : 'http://www.stormware.cz/schema/version_2/type.xsd'
        } 
        self.map = {
                "sym-var"       : "//inv:symVar/text()",            # variabilni symbol

                "date"          : "//inv:date/text()",              # datum
                "date-tax"      : "//inv:dateTax/text()",           # danitelne plneni
                "date-due"      : "//inv:dateDue/text()",           # splatnost

                "addr-name"     : "//typ:address/typ:name/text()",
                "addr-street"   : "//typ:address/typ:street/text()",
                "addr-city"     : "//typ:address/typ:city/text()",
                "addr-zip"      : "//typ:address/typ:zip/text()",

                "ico"           : "//typ:address/typ:ico/text()",
                "dic"           : "//typ:address/typ:dic/text()",

                "sum"           : "//inv:invoiceSummary//typ:priceLowSum/text()",

                "inv-items"     : {
                    "__count__" : "count(//inv:invoiceItem)",
                    "name"      : "//inv:invoiceItem[%d]/inv:text/text()",
                    "quantity"  : "//inv:invoiceItem[%d]/inv:quantity/text()",
                    "unit"      : "//inv:invoiceItem[%d]/inv:unit/text()",
                    "priceUnit":  "//inv:invoiceItem[%d]/inv:homeCurrency/typ:unitPrice/text()",
                    "price"     : "//inv:invoiceItem[%d]/inv:homeCurrency/typ:price/text()",
                    "priceVAT"  : "//inv:invoiceItem[%d]/inv:homeCurrency/typ:priceVAT/text()",
                    "rateVAT"   : "//inv:invoiceItem[%d]/inv:rateVAT/text()",                        # low/hight
                    "payVAT"    : "//inv:invoiceItem[%d]/inv:payVAT/text()"
                }
        }

    def readXML(self, inv, filename):
        try:
            self.doc = etree.parse(filename)
        except:
            self.error('Failed to parse %s' % filename)

        self.readByMap(self.map, inv)

    def readByMap(self, m, inv):
        for key in m.keys():
            if type(m[key]) is types.DictType:
                self.readSubMap(key, m[key], inv)
            else:
                self.itemFromXML(key, m[key], inv)

    def readSubMap(self, key, m, inv):
        path = m['__count__']
        count = int(self.doc.xpath(path, namespaces=self.ns))
        if count is 0.0:
            return
        inv[key] = []
        for i in range(1, count+1):
            subinv = {}
            for k in m.keys():
                if k is '__count__':
                    continue
                self.itemFromXML(k, m[k] % i, subinv)
            inv[key].append(subinv)

        #print "KZAK>>> %s" % inv[key]

    def itemFromXML(self, key, path, inv):
            x = self.doc.xpath(path, namespaces=self.ns)
            if len(x) == 0:
                return
            if type(x[0]) in [etree._ElementStringResult, etree._ElementUnicodeResult]:
                inv[key] = x[0]  # text
            else:
                inv[key] = x     # list or object


class writerFlexiBee:
    def __init__(self, useAddressBook=False, ignoreZeroPrice=True):
        self.map = {}
        self.last_addr_id = ''
        self.useAddressBook = useAddressBook
        self.ignoreZeroPrice = ignoreZeroPrice

    def appendTextItem(self, parent, name, itemname, inv):
        if inv.has_key(itemname):
            etree.SubElement(parent, name).text = inv[itemname]


    def makeAddrHash(self, inv):
        res = b''
        for x in ["addr-name", "addr-street", "addr-city", "addr-zip"]:
            if inv.has_key(x):
                res += inv[x].encode('ascii', 'replace')
        return (zlib.crc32(res) & 0xffffffff)

    def generateAddressBook(self, doc, inv):
        addr = etree.SubElement(doc, "adresar", update="ignore")

        code = self.makeAddrHash(inv)

        etree.SubElement(addr, "kod").text = unicode(code)
        self.last_addr_id = "ph:%s" % code
        etree.SubElement(addr, "id").text = self.last_addr_id

        self.appendTextItem(addr, "nazev", "addr-name", inv)
        self.appendTextItem(addr, "ulice", "addr-street", inv)
        self.appendTextItem(addr, "mesto", "addr-city", inv)
        self.appendTextItem(addr, "psc", "addr-zip", inv)
        self.appendTextItem(addr, "ic", "ico", inv)
        self.appendTextItem(addr, "dic", "dic", inv)

    def generateAddress(self, parent, inv):
        self.appendTextItem(parent, "nazFirmy", "addr-name", inv)
        self.appendTextItem(parent, "ulice", "addr-street", inv)
        self.appendTextItem(parent, "mesto", "addr-city", inv)
        self.appendTextItem(parent, "psc", "addr-zip", inv)
        self.appendTextItem(parent, "ic", "ico", inv)
        self.appendTextItem(parent, "dic", "dic", inv)

    def vatToNumber(self, inv, name):
        return vat[inv[name]]

    def generateInvDataItems(self, parent, inv):
        polRoot = etree.SubElement(parent, "polozkyFaktury")
    
        for i in inv["inv-items"]:
            if self.ignoreZeroPrice:
                price = 0.0
                if i.has_key("price"):
                    price = float(i["price"])
                if price == 0.0:
                    continue
            pol = etree.SubElement(polRoot, "faktura-vydana-polozka")
            self.appendTextItem(pol, "nazev", "name", i)
            self.appendTextItem(pol, "mnozMj", "quantity", i)
            self.appendTextItem(pol, "cenaMj", "priceUnit", i) 
            self.appendTextItem(pol, "sumZkl", "price", i)
            self.appendTextItem(pol, "sumDph", "priceVAT", i)
            if i.has_key("rateVAT"):
                etree.SubElement(pol, "szbDph").text = self.vatToNumber(i, "rateVAT")

    def generateInvData(self, doc, inv):
        fak = etree.SubElement(doc, "faktura-vydana")

        if len(self.last_addr_id):
            etree.SubElement(fak, "firma").text = self.last_addr_id
        etree.SubElement(fak, "typDokl").text = "code:FAKTURA"

        self.appendTextItem(fak, "varSym", "sym-var", inv)
        self.appendTextItem(fak, "datVyst", "date", inv)
        self.appendTextItem(fak, "datSplat", "date-due", inv)
        self.appendTextItem(fak, "duzpPuv", "date-tax", inv)

        self.generateAddress(fak, inv)
        self.generateInvDataItems(fak, inv)

    def generateTree(self, inv):
        doc = etree.Element("winstrom", version="1.0")
        if self.useAddressBook:
            self.generateAddressBook(doc, inv)
        self.generateInvData(doc, inv)
        return doc

    def writeXML(self, inv, filename=None):
        print etree.tostring(self.generateTree(inv),
                    pretty_print=True,
                    method='xml',
                    xml_declaration=True,
                    encoding="UTF-8")


class Invoice:
    def __init__(self, reader=None, writer=None):
        self.__dict__ = {}
        self.reader = reader
        self.writer = writer

    def __str__(self):
        res = ""
        for key in self.items.keys():
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

    def readFromFile(self, filename):
        self.reader.readXML(self, filename)

    def writeToFile(self, filename=None):
        self.writer.writeXML(self, filename)



if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "usage: %s <filename>" % sys.argv[0]
        sys.exit(1)
         
    inv = Invoice(readerPohoda(),
                  writerFlexiBee(ignoreZeroPrice=True,
                                 useAddressBook=False))

    inv.readFromFile(sys.argv[1])

    inv.writeToFile()    

