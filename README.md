# About

This repository is used to maintain development of the scripts to support extraction of
"computable" representation of the DICOM standard.

The initial specific goal is to generate JSON representation of the Composite Information 
Object Definitions (CIODs) and Module Attributes from DocBook XML representation of DICOM Part 3.

# Status

Parse output on the 2019d version of the standard:
```bash
$ python dcmdocbook2json.py DocBookDICOM2019d_release_docbook_20190922212826/source/docboo DICOM_2019d_JSON_output
Parsing part 3
Parsing of part 3 done
DICOM standard version: DICOM PS3.3 2019d - Information Object Definitions
All parsing done
308 module tables identified and parsed
129 CIOD tables identified and parsed
4731 attribute rows parsed successfully
694 rows of module tables that did not have 4 columns skipped
0 rows of CIOD tables that did not have 3 or 4 columns skipped
2136 rows that had attribute names starting with ">" skipped
```

# Similar projects

* https://github.com/innolitics/dicom-standard: operates on HTML representation, does not currently 
work on the latest version of the standard, does not generate the concise representation that was needed
for the initial steps of our project. We do not say it cannot be amended to address those issues, it was
just deemed more expedient to start experimenting from scratch, and from DocBook XML.

# Support

This code is developed by the Imaging Data Commons consortium, as part of the work to establish NCI
Imaging Data Commons.  

This work is supported by contract number 19X037Q from Leidos Biomedical Research under Task Order HHSN26100071
from National Cancer Institute.
