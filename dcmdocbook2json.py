'''
This script will parse DocBook XML of DICOM, and generate a JSON representation
of the Modules, CIODs, and other things, defined by the standard.

Input:
 * top-level directory with the DocBook XML representation of the DICOM standard
 * output directory to keep parsed content saved as JSON
Output:
 * JSON files corresponding to individual parsed items from the standard

Currently, this generates the following files:
* CIOD definitions: for each CIOD, dict of Information Entities, and for each IE - dict of {module names, module usage}
* Module definitions: for each module, dict {attribute name, tag, type}

Limitations:

* Modules
** sequences not supported
** "Include" rows in module definition tables not supported

* CIODs
** need to parse corresponding part of the standard to populate SOPClassUID for each CIOD
'''

from bs4 import BeautifulSoup as bs
import re
import json
import os
import sys
from lxml import etree


class DICOMParser(object):

  def __init__(self, docbook_path):
    self.namespaces = {'docbook': "http://docbook.org/ns/docbook"}
    self.dicom_forest = {}

    self.parsed_modules = {}
    self.parsed_CIODs = {}

    for part_number in [3]:
      print("Parsing part %i" % part_number)
      part_filename = os.path.join(docbook_path, ("part%02i" % part_number), "part%02i.xml" % part_number)
      with open(part_filename, encoding="utf-8") as f:
        parser = etree.XMLParser()
        self.dicom_forest[part_number] = etree.parse(f, parser)
        if len(parser.error_log):
          print("Parser error log not empty: %i errors" % len(parser.error_log))
      print("Parsing of part %i done" % part_number)

    '''
    with open(os.path.join(docbook_path, "part16.xml"), encoding="utf-8") as f:
      parser = etree.XMLParser()
      self.part03tree = etree.parse(f, parser)
    '''

    self.dicom_version = self.dicom_forest[3].xpath("/docbook:book/docbook:subtitle", namespaces=self.namespaces)[0].text
    print("DICOM standard version: "+self.dicom_version)
    print("All parsing done")

  def parse(self):
    self.parseModulesAndCIODs()

  # http://stackz.ru/en/749796/pretty-printing-xml-in-python
  def indent(self, elem, level=0):
    i = '\n' #''\\n' + (' ' * level)
    if len(elem):
      if not elem.text or not elem.text.strip():
        elem.text = i + "  "
      if not elem.tail or not elem.tail.strip():
        elem.tail = i
      for elem in elem:
        self.indent(elem, level + 1)
      if not elem.tail or not elem.tail.strip():
        elem.tail = i
    else:
      if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i

  @staticmethod
  def isModuleTable(caption, headers):
    if caption.endswith("Module Attributes") and len(headers) == 4:
      if headers[0][0].text == "Attribute Name" and \
         headers[1][0].text == "Tag" and \
         headers[2][0].text == "Type" and \
         headers[3][0].text == "Attribute Description":
        return True
    return False

  @staticmethod
  def isCIODTable(caption, headers):
    if caption.endswith("IOD Modules") and len(headers) == 4:
      if headers[0][0].text == "IE" and \
         headers[1][0].text == "Module" and \
         headers[2][0].text == "Reference" and \
         headers[3][0].text == "Usage":
        return True
    return False

  def parseModulesAndCIODs(self):

    # the logic here attempts to do what @dclunie does in
    #  extractcompositeiodsfordicom3tooltemplate.xsl
    # To find module definitions, we need <table>s, which meet the following criteria:
    #  * <caption> ends with "Module Attributes"
    #  * <table> has <thead> child with exactly 4 columns (thead/tr/th*)
    #  * Text for the 4 of the th/para are "Attribute Name", "Tag", "Type" and "Attribute Description"

    tree = self.dicom_forest[3]

    # First select tables from Part 3 that correspond to either module attributes or CIODs
    relevant_tables = {}

    # iterate over all tables, and fine the ones that contain CIODs or Attribute Modules
    tables = tree.xpath('//docbook:table', namespaces=self.namespaces)

    xpathFindCaption = etree.XPath("docbook:caption", namespaces=self.namespaces)
    #findThead = etree.XPath("docbook:thead", namespaces=self.namespaces)
    xpathFindHeader = etree.XPath("docbook:thead/docbook:tr/docbook:th", namespaces=self.namespaces)
    xpathCountColumns = etree.XPath("count(docbook:td)", namespaces=self.namespaces)

    for table in tables:

      caption = xpathFindCaption(table)
      if len(caption) != 1:
        # no caption
        continue

      headers = xpathFindHeader(table)
      caption = caption[0].text
      if self.isModuleTable(caption, headers):
        relevant_tables[caption] = (table, "module")
      elif self.isCIODTable(caption, headers):
        relevant_tables[caption] = (table, "CIOD")
      else:
        # not a relevant table
        pass

    modules = {}
    CIODs = {}
    rowCount = 0
    sequenceRowsSkipped = 0
    modulesNon4ColumnsRowsSkipped = 0
    CIODsNon3or4ColumnsRowsSkipped = 0

    for table_caption in relevant_tables.keys():
      (table, table_type) = relevant_tables[table_caption]
      findRows = etree.XPath("docbook:tbody/docbook:tr", namespaces=self.namespaces)
      rows = findRows(table)
      if len(rows) == 0:
        print("Module table has no rows! Skipping %s" % table_caption)
        continue

      parsed_module = None
      parsed_CIOD = None
      if table_type == "CIOD":
        IE_name = None
        parsed_CIOD = {}
        parsed_CIOD["CIODName"] = table_caption[:table_caption.find(" IOD Modules")]
        parsed_CIOD["informationEntities"] = {}
      elif table_type == "module":
        parsed_module = {}
        parsed_module["moduleName"] = table_caption[:table_caption.find(" Attributes")]
        parsed_module["attributes"] = []
      else:
        continue


      for row in rows:

        num_columns = xpathCountColumns(row)

        # this takes care of the situations with "Include"
        if table_type == "module" and num_columns != 4:
          modulesNon4ColumnsRowsSkipped = modulesNon4ColumnsRowsSkipped+1
          continue

        if table_type == "CIOD" and not num_columns in [3,4]:
          CIODsNon3or4ColumnsRowsSkipped = CIODsNon3or4ColumnsRowsSkipped+1
          continue

        # For CIODs: IE, Module, Reference, Usage
        # For Module Attributes: Attribute Name, Tag, Type
        columns_paras = [row.xpath("docbook:td[%i]/docbook:para[1]" %i, namespaces=self.namespaces) for i in range(1,5)]
        for i, column_para in enumerate(columns_paras):
          if len(column_para) != 0:
            # we only need text
            columns_paras[i] = columns_paras[i][0].text

        if table_type == "module" and columns_paras[0].startswith('>'):
          # this is a sequence
          sequenceRowsSkipped = sequenceRowsSkipped+1
          continue

        if table_type == "module":
          attributeName = columns_paras[0]
          tag = columns_paras[1]
          type = columns_paras[2]

          attribute = {}
          attribute["name"] = attributeName
          attribute["tag"] = tag
          attribute["type"] = type

          parsed_module["attributes"].append(attribute)

        elif table_type == "CIOD":
          if num_columns == 3:
            module_name = columns_paras[0]
            #print("Module: "+module_name)
            if IE_name == None or not (IE_name in parsed_CIOD["informationEntities"].keys()):
              print("ERROR: CIOD table has 3 columns and uninitialized IE name!")
              sys.exit()
              continue
            CIOD_module = {"moduleName": module_name, "moduleUsage": columns_paras[2]}
            parsed_CIOD["informationEntities"][IE_name][columns_paras[0]] = CIOD_module
          elif num_columns == 4:
            module_name = columns_paras[1]
            IE_name = columns_paras[0]
            #print("Module: " + module_name)
            if IE_name in parsed_CIOD["informationEntities"].keys():
              print("ERROR: Parsed new IE %s, but it is already in CIOD - should never happen!" % IE_name)
              sys.exit()
              continue
            CIOD_module = {"moduleName": module_name, "moduleUsage": columns_paras[3]}
            parsed_CIOD["informationEntities"][IE_name] = {}
            parsed_CIOD["informationEntities"][IE_name][columns_paras[1]] = CIOD_module

        rowCount = rowCount+1

        #print(attribute)

      if parsed_module:
        self.parsed_modules[parsed_module["moduleName"]] = parsed_module

      if parsed_CIOD:
        self.parsed_CIODs[parsed_CIOD["CIODName"]] = parsed_CIOD

    print("%i module tables identified and parsed" % len(self.parsed_modules.keys()))
    print("%i CIOD tables identified and parsed" % len(self.parsed_CIODs.keys()))
    print("%i attribute rows parsed successfully" % rowCount)
    print("%i rows of module tables that did not have 4 columns skipped" % modulesNon4ColumnsRowsSkipped)
    print("%i rows of CIOD tables that did not have 3 or 4 columns skipped" % CIODsNon3or4ColumnsRowsSkipped)
    print("%i rows that had attribute names starting with \">\" skipped" % sequenceRowsSkipped)

    self.parsed_modules = {"version": self.dicom_version, "modules": self.parsed_modules}
    self.parsed_CIOD = {"version": self.dicom_version, "CIODs": self.parsed_CIODs}

  def saveParsedContent(self, output_dir):
    version = self.dicom_version.replace(" ", "_")

    with open(os.path.join(output_dir, version+"-modules.json"),"w") as json_file:
      json.dump(self.parsed_modules, json_file, indent=2)

    with open(os.path.join(output_dir, version+"-CIODs.json"),"w") as json_file:
      json.dump(self.parsed_CIODs, json_file, indent=2)

if __name__ == "__main__":
  if len(sys.argv)<2:
    print("Usage: %s <path do DICOM DocBook XML folder> <path to output JSON folder>")
  else:
    parser = DICOMParser(sys.argv[1])
    parser.parse()
    parser.saveParsedContent(sys.argv[2])


