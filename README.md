# dictcc-stardict
Convert dict.cc file to StarDict format

## Installation
### 1. Clone repository
```
git clone https://github.com/Linus789/dictcc-stardict.git
cd dictcc-stardict
```

### 2. Create a Python Virtual Environment (optional step)
For example on Linux:
```
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```
python -m pip install -r requirements.txt
```

### 4. Execution
```
python convert.py --help
```

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
If you have already installed the dependencies during the installation, you can probably skip this section.

* [pyglossary](https://pypi.org/project/pyglossary/)
* [pyparsing](https://pypi.org/project/pyparsing/)
* dictzip (optional: for compression)
