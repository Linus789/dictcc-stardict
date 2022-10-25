# dictcc-stardict
Convert dict.cc file to StarDict format

## Get dict.cc file
Go to [https://www1.dict.cc/translation_file_request.php](https://www1.dict.cc/translation_file_request.php) download the file and unpack it, if necessary.

## Help menu
```
usage: convert.py [-h] -f FILE -s LANG

Convert dict.cc file to StarDict format

options:
  -h, --help                   show this help message and exit
  -f FILE, --file FILE         dict.cc file
  -s LANG, --source-lang LANG  source language
```

## Requirements
* [pyglossary](https://pypi.org/project/pyglossary/)
* [pyparsing](https://pypi.org/project/pyparsing/)
* dictzip (optional: for compression)
