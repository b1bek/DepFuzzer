# DepFuzzer

DepFuzzer is a tool used to find dependency confusion or project where owner's email can be takeover.


## Install the tool

/!\ This tool requires python >= 3.10 /!\

```sh
$ python3 -m venv .venv
$ source .venv/bin/activate
$ pip3 install -r requirements.txt
```

Or you can use the docker image :

```sh
$ docker build -t depfuzzer:latest .
$ docker run --rm -it -v "$PWD":/host depfuzzer
```

## Use the tool

The tool can be used to scan folders to search specific file where dependencies are declared, for example :

- `package.json`
- `requirements.txt`
- ...

`python3 main.py --provider pypi --path ~/Documents/Projets/MyProject/`

Moreover, this tool can be used to scan one specific dependency :

`python3 main.py --provider pypi --dependency requests:0.1.0`

The tool uses local package files for fast scanning and falls back to online APIs when needed.

## All possible arguments

```
______          ______                      
|  _  \         |  ___|                     
| | | |___ _ __ | |_ _   _ ___________ _ __ 
| | | / _ \ '_ \|  _| | | |_  /_  / _ \ '__|
| |/ /  __/ |_) | | | |_| |/ / / /  __/ |   
|___/ \___| .__/\_|  \__,_/___/___\___|_|   
          | |                               
          |_|                               

usage: main.py [-h] --provider {npm,pypi,cargo,go,maven,gradle,rubygems,all}
               (--path PATH | --dependency DEPENDENCY) [--print-takeover PRINT_TAKEOVER]
               [--output-file OUTPUT_FILE] [--check-email CHECK_EMAIL]

Dependency checker

options:
  -h, --help            show this help message and exit
  --provider {npm,pypi,cargo,go,maven,gradle,rubygems,all}
  --path PATH           Path to folder(s) to analyze
  --dependency DEPENDENCY
                        Specify the name of one dependency to check. If you specify the version,
                        please use ':' to separate name and version.
  --print-takeover PRINT_TAKEOVER
                        Don't wait the end of the script to display takeoverable modules
  --output-file OUTPUT_FILE
                        File where results will be stored
  --check-email CHECK_EMAIL
                        Check if the email's owner of the dependency exists. Might be longer to
                        analyze.
```

## Found a bug or an idea ?

If you found a bug or have an idea, don't hesitate to open an issue on this project !

# Disclaimer

This tool is not meant to find all dependencies confusion within projects. Furthermore, the tool is known to produce false positives due to the complexity of parsing requirements files.

Always check manually if it's exploitable before taking actions.

Please note that actually exploiting this vulnerability might have out of control side effects, so be careful.

Synacktiv cannot be held responsible if the tool is used for malicious purposes, it's for educational purposes only.

# License

This project is licensed under the MIT License - see the LICENSE file for details.
