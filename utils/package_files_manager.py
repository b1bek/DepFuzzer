"""
Package Files Manager for DepFuzzer
Downloads and manages package lists from different ecosystems for faster dependency checking
"""

import json
import re
import requests
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path


class PackageFilesManager:
    """
    Manages package files from different ecosystems
    """
    
    def __init__(self, base_dir="package_files"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self._package_cache = {}  # Cache for loaded package lists
        
        # Package file URLs for different ecosystems
        self.package_sources = {
            "npm": {
                "url": "https://raw.githubusercontent.com/nice-registry/all-the-package-names/refs/heads/master/names.json",
                "file": "npm_packages.json",
                "format": "json"
            },
            "pypi": {
                "url": "https://pypi.org/simple/",
                "file": "pypi_packages.txt", 
                "format": "html_links"
            },
            "maven": {
                "url": "https://repo1.maven.org/maven2/",
                "file": "maven_packages.txt",
                "format": "html_links"
            },
            "rubygems": {
                "url": "https://rubygems.org/gems",
                "file": "rubygems_packages.txt",
                "format": "gem_search"
            }
        }
        
    def _get_file_path(self, ecosystem):
        """Get the file path for an ecosystem's package list"""
        if ecosystem not in self.package_sources:
            return None  # Ecosystem not supported for file-based checking
        return self.base_dir / self.package_sources[ecosystem]["file"]
    
    def _is_file_fresh(self, file_path, max_age_days=7):
        """Check if a file is fresh (not older than max_age_days)"""
        if not file_path.exists():
            return False
        
        file_age = datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)
        return file_age < timedelta(days=max_age_days)
    
    def download_npm_packages(self):
        """Download NPM package list using GitHub repository (maintained by jsDelivr)"""
        print("[+] Downloading NPM package list...")
        file_path = self._get_file_path("npm")
        
        if self._is_file_fresh(file_path):
            print(f"[+] NPM package file is fresh, skipping download")
            return True
            
        try:
            # Use the GitHub repository approach from the notebook
            url = "https://raw.githubusercontent.com/nice-registry/all-the-package-names/refs/heads/master/names.json"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                packages = response.json()
                
                with open(file_path, 'w') as f:
                    json.dump(packages, f, indent=2)
                print(f"[+] Downloaded {len(packages)} NPM packages")
                return True
            else:
                print(f"[-] Failed to download NPM packages: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"[-] Failed to download NPM packages: {e}")
            return False
    
    def download_pypi_packages(self):
        """Download PyPI package list"""
        print("[+] Downloading PyPI package list...")
        file_path = self._get_file_path("pypi")
        
        if self._is_file_fresh(file_path):
            print(f"[+] PyPI package file is fresh, skipping download")
            return True
            
        try:
            response = requests.get("https://pypi.org/simple/", timeout=30)
            if response.status_code == 200:
                # Parse HTML to extract package names
                import re
                content = response.text
                # Extract package names from href URLs: /simple/package-name/
                packages = re.findall(r'<a href="/simple/([^/"]+)/">', content)
                
                with open(file_path, 'w') as f:
                    for package in packages:
                        f.write(f"{package}\n")
                print(f"[+] Downloaded {len(packages)} PyPI packages")
                return True
        except Exception as e:
            print(f"[-] Failed to download PyPI packages: {e}")
            return False
    

    
    def download_maven_packages(self):
        """Download Maven package list using exact notebook approach"""
        print("[+] Downloading Maven package list...")
        file_path = self._get_file_path("maven")
        
        if self._is_file_fresh(file_path):
            print(f"[+] Maven package file is fresh, skipping download")
            return True
            
        try:
            # Use exact approach from notebook
            response = requests.get("https://repo1.maven.org/maven2/", stream=True, timeout=30)
            
            if response.status_code == 200:
                content = response.text
                # Extract package names using exact regex from notebook
                public_mvn_packages = re.findall(r'<a href="([^"]*)"', content)
                public_mvn_packages = [pkg.rstrip('/') for pkg in public_mvn_packages]
                
                with open(file_path, 'w') as f:
                    for package in public_mvn_packages:
                        f.write(f"{package}\n")
                print(f"[+] Downloaded {len(public_mvn_packages)} Maven organizations")
                return True
            else:
                print(f"[-] Failed to download Maven packages: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"[-] Failed to download Maven packages: {e}")
            return False

    def download_rubygems_packages(self):
        """Download RubyGems package list using gem search command"""
        print("[+] Downloading RubyGems package list...")
        file_path = self._get_file_path("rubygems")
        
        if self._is_file_fresh(file_path):
            print(f"[+] RubyGems package file is fresh, skipping download")
            return True
            
        try:
            # Use the exact command from notebook: gem search '' --all
            print("[+] Running: gem search '' --all")
            result = subprocess.run(['gem', 'search', '', '--all'], 
                                  capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # Parse the output - each line contains gem name and version info
                # Format: "gem_name (version1, version2, ...)"
                packages = []
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        # Extract gem name (everything before the first space or parenthesis)
                        gem_name = line.split(' ')[0].strip()
                        if gem_name and gem_name not in packages:
                            packages.append(gem_name)
                
                with open(file_path, 'w') as f:
                    for package in packages:
                        f.write(f"{package}\n")
                print(f"[+] Downloaded {len(packages)} RubyGems packages")
                return True
            else:
                print(f"[-] gem search command failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("[-] gem search command timed out")
            return False
        except FileNotFoundError:
            print("[-] gem command not found. Please install Ruby and RubyGems")
            return False
        except Exception as e:
            print(f"[-] Failed to download RubyGems packages: {e}")
            return False

    def download_all_packages(self, ecosystems=None):
        """Download package lists for all or specified ecosystems"""
        if ecosystems is None:
            ecosystems = list(self.package_sources.keys())
        
        results = {}
        for ecosystem in ecosystems:
            if ecosystem == "npm":
                results[ecosystem] = self.download_npm_packages()
            elif ecosystem == "pypi":
                results[ecosystem] = self.download_pypi_packages()
            elif ecosystem == "maven":
                results[ecosystem] = self.download_maven_packages()
            elif ecosystem == "rubygems":
                results[ecosystem] = self.download_rubygems_packages()
            else:
                print(f"[-] Unknown ecosystem: {ecosystem}")
                results[ecosystem] = False
        
        return results
    
    def package_exists_in_files(self, package_name, ecosystem):
        """Check if a package exists in the downloaded package files"""
        file_path = self._get_file_path(ecosystem)
        
        if file_path is None or not file_path.exists():
            return None  # Ecosystem not supported or file doesn't exist, need to query API
        
        try:
            if ecosystem == "npm":
                # JSON format for NPM - use caching to avoid reloading large file
                cache_key = f"{ecosystem}_{file_path}"
                if cache_key not in self._package_cache:
                    with open(file_path, 'r') as f:
                        self._package_cache[cache_key] = set(json.load(f))  # Use set for O(1) lookup
                return package_name in self._package_cache[cache_key]
            elif ecosystem == "pypi":
                # Text format, one package per line - case insensitive for PyPI
                cache_key = f"{ecosystem}_{file_path}"
                if cache_key not in self._package_cache:
                    with open(file_path, 'r') as f:
                        # Store as lowercase set for case-insensitive matching
                        self._package_cache[cache_key] = set(line.strip().lower() for line in f)
                package_name_lower = package_name.lower()
                return package_name_lower in self._package_cache[cache_key]
            elif ecosystem in ["maven", "rubygems"]:
                # Text format, one package per line - case sensitive
                cache_key = f"{ecosystem}_{file_path}"
                if cache_key not in self._package_cache:
                    with open(file_path, 'r') as f:
                        # Store as set for case-sensitive matching
                        self._package_cache[cache_key] = set(line.strip() for line in f)
                return package_name in self._package_cache[cache_key]
        except Exception as e:
            print(f"[-] Error reading package file for {ecosystem}: {e}")
            return None  # Error reading file, fallback to API
    
    def get_package_files_info(self):
        """Get information about downloaded package files"""
        info = {}
        for ecosystem in self.package_sources:
            file_path = self._get_file_path(ecosystem)
            if file_path.exists():
                stat = file_path.stat()
                info[ecosystem] = {
                    "exists": True,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "fresh": self._is_file_fresh(file_path)
                }
            else:
                info[ecosystem] = {"exists": False}
        return info