#!/usr/bin/env python

import sys, os, string, time, types
from lxml import etree

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
        for key in m.keys():
            if type(m[key]) is types.DictType:
                self.readSubMap(key, m[key], inv)
            else:
                self.itemFromXML(key, m[key], inv)

    def readSubMap(self, key, m, inv):
        path = m['__count__']
        count = int(self.doc.xpath(path, namespaces=namespaces))
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
            x = self.doc.xpath(path, namespaces=namespaces)
            if len(x) == 0:
                return
            if type(x[0]) in [etree._ElementStringResult, etree._ElementUnicodeResult]:
                inv[key] = x[0]  # text
            else:
                inv[key] = x     # list or object


class writerFlexiBee:
    def __init__(self, ignoreZeroPrice=True):
        self.map = {}
        self.last_addr_id = ''
        self.ignoreZeroPrice = ignoreZeroPrice

    def appendTextItem(self, parent, name, itemname, inv):
        if inv.has_key(itemname):
            etree.SubElement(parent, name).text = inv[itemname]

    def generateAddress(self, parent, inv):
        self.appendTextItem(parent, "nazFirmy", "addr-name", inv)
        self.appendTextItem(parent, "ulice", "addr-street", inv)
        self.appendTextItem(parent, "mesto", "addr-city", inv)
        self.appendTextItem(parent, "psc", "addr-zip", inv)
        self.appendTextItem(parent, "ic", "ico", inv)
        self.appendTextItem(parent, "dic", "dic", inv)

    def vatToSymbol(self, inv, name):
        return vat[inv[name]]

    def isDobropis(self, inv):
        if inv.has_key("inv-type") and inv["inv-type"] == "issuedCorrectiveTax":
            return True
        return False

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
                etree.SubElement(pol, "typSzbDphK").text = self.vatToSymbol(i, "rateVAT")

    def generateInvData(self, doc, inv):
        fak = etree.SubElement(doc, "faktura-vydana")

        code = inv["code"]

        if self.isDobropis(inv):
            etree.SubElement(fak, "id").text = "code:DOB%s" % code
            dob = etree.SubElement(fak, "vytvor-vazbu-dobropis")
            etree.SubElement(dob, "dobropisovanyDokl").text = "code:FAK%s" % code
        else:
            etree.SubElement(fak, "id").text = "code:FAK%s" % code

        if len(self.last_addr_id):
            etree.SubElement(fak, "firma").text = self.last_addr_id
        etree.SubElement(fak, "typDokl").text = "code:FAKTURA"

        self.appendTextItem(fak, "varSym", "sym-var", inv)
        self.appendTextItem(fak, "datVyst", "date", inv)
        self.appendTextItem(fak, "datSplat", "date-due", inv)
        self.appendTextItem(fak, "duzpPuv", "date-tax", inv)
        etree.SubElement(fak, "formaUhrK").text = "formaUhr.dobirka";

        self.generateAddress(fak, inv)
        self.generateInvDataItems(fak, inv)



    def writeXML(self, root):
        self.generateInvData(root, inv)


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

    def readFromXML(self, root):
        self.reader.readXML(self, root)

    def writeToXML(self, root):
        self.writer.writeXML(root)



def unpackPohoda(filename):
    try:
        doc = etree.parse(filename)
    except:
        self.error('Failed to parse %s' % filename)

    return doc.xpath('//inv:invoice', namespaces=namespaces)

def makeFlexiBeeTree():
    return etree.Element("winstrom", version="1.0")

def packFlexiBee(tree):
     print etree.tostring(tree,
                    pretty_print=True,
                    method='xml',
                    xml_declaration=True,
                    encoding="UTF-8")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "usage: %s <filename>" % sys.argv[0]
        sys.exit(1)
    
    pohoda = unpackPohoda(sys.argv[1])
    bee    = makeFlexiBeeTree()

    for p in pohoda:
        inv = Invoice(readerPohoda(),
                      writerFlexiBee(ignoreZeroPrice=True))
        inv.readFromXML(p)
        inv.writeToXML(bee)
        del inv

    packFlexiBee(bee)
    

