"""
Script defining several functions used in main program
"""
import urllib.parse
from functools import cache
from time import sleep
import re
import urllib3
from concurrent.futures import ThreadPoolExecutor
from .package_files_manager import PackageFilesManager

# Disable SSL warnings when using proxy
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Initialize package files manager
package_files_mgr = PackageFilesManager()

# Burp proxy configuration
BURP_PROXY = {
    'http': 'http://127.0.0.1:8080',
    'https': 'http://127.0.0.1:8080'
}

@cache
def dependency_exists(name, provider, session, skip_file_check=False):
    """
    Method used to check if a dependency is deprecated or not claimed
    First checks package files, then falls back to API if needed
    """
    if not skip_file_check:
        # First check package files
        file_result = package_files_mgr.package_exists_in_files(name, provider)
        if file_result is not None:
            return file_result
    
    # Fallback to API if package files don't have the info
    try:
        if "gradle" in provider :
            groupId, artifactId = name.split(':')[0], name.split(':')[1]
            output = session.get(f'https://search.maven.org/solrsearch/select?q=g:{groupId}+AND+a:{artifactId}&core=gav&rows=20&wt=json',
                                timeout=5,
                                proxies=BURP_PROXY,
                                verify=False)
            if output.json()['response']['numFound'] != 0:
                return output
            
        else:
            package = urllib.parse.quote(name,safe='')
            output = session.get(f"https://deps.dev/_/s/{provider}/p/{package}",
                                timeout=5,
                                proxies=BURP_PROXY,
                                verify=False)
            return output.status_code != 404
    except Exception as e:
        print("[-] We have been rate limited, going to sleep for 5 minutes.")
        print(f"Exception: {e}")
        # sleep(300) #this means the API drop our requests
        return None

def initialize_package_files(ecosystems=None):
    """
    Initialize package files for specified ecosystems
    """
    print("[+] Initializing package files...")
    results = package_files_mgr.download_all_packages(ecosystems)
    
    success_count = sum(1 for success in results.values() if success)
    total_count = len(results)
    print(f"[+] Package files initialization: {success_count}/{total_count} ecosystems successful")
    
    return results

def get_package_files_status():
    """
    Get status of package files
    """
    return package_files_mgr.get_package_files_info()

def _clean_package_name(package_name, provider):
    """
    Clean package names to extract actual package name from aliases
    Handle format like "fdir1" where the actual package info is in dependencies dict
    """
    # For NPM, if package name looks like an alias, we need to check if it's a real package
    # The actual cleaning will happen when we have access to the version info
    return package_name

def batch_check_dependencies(packages, provider, session, max_workers=50):
    """
    Check multiple dependencies concurrently for faster processing
    Uses package files first, then API for remaining packages
    """
    # First, check all packages against package files
    file_results = {}
    api_packages = []
    
    for package in packages:
        clean_package = _clean_package_name(package, provider)
        file_result = package_files_mgr.package_exists_in_files(clean_package, provider)
        if file_result is True:
            # Package exists in files - definitive result
            file_results[package] = True
        elif file_result is False:
            # Package not found in files - need API confirmation
            api_packages.append(package)
        else:
            # Error reading files - need API fallback
            api_packages.append(package)
    
    print(f"[+] Found {len(file_results)} packages in files, {len(api_packages)} need API check")
    
    # Optimize API calls by grouping scoped packages by organization
    api_results = {}
    if api_packages:
        api_results = _optimize_org_api_calls(api_packages, provider, session, max_workers)
    
    # Combine results
    final_results = {**file_results, **api_results}
    return final_results

def _optimize_org_api_calls(api_packages, provider, session, max_workers):
    """
    Optimize API calls by checking only first few packages per organization
    """
    # Group packages by organization
    org_groups = {}  # org_prefix -> list of packages
    regular_packages = []
    
    for package in api_packages:
        if "@" in package and "/" in package:
            org_prefix = package.split("/")[0] + "/"
            if org_prefix not in org_groups:
                org_groups[org_prefix] = []
            org_groups[org_prefix].append(package)
        else:
            regular_packages.append(package)
    
    # Check regular packages normally
    def check_single_api(package):
        return package, dependency_exists(package, provider, session, skip_file_check=True)
    
    api_results = {}
    if regular_packages:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            api_results.update(dict(executor.map(check_single_api, regular_packages)))
    
    # For each organization, check only first 5 packages and apply result to all
    for org_prefix, org_packages in org_groups.items():
        sample_packages = org_packages[:5]  # Check only first 5
        sample_results = []
        
        # Check sample packages
        with ThreadPoolExecutor(max_workers=min(5, max_workers)) as executor:
            sample_results = list(executor.map(check_single_api, sample_packages))
        
        # Determine organization result (if any sample exists, org exists)
        org_exists = any(result for _, result in sample_results)
        
        # Apply result to all packages in this organization
        for package in org_packages:
            api_results[package] = org_exists
        
        if len(org_packages) > 5:
            print(f"[+] Optimized: Checked {len(sample_packages)} samples from {org_prefix}, applied to {len(org_packages)} packages")
    
    return api_results

@cache
def recover_dependencies(name, version, provider, session):
    """
    Method used to return all dependencies of a dependency
    """
    try:
        if "gradle" in provider :
            groupId, artifactId = name.split(':')[0], name.split(':')[1]
            output = session.get(f'https://search.maven.org/solrsearch/select?q=g:{groupId}+AND+a:{artifactId}+AND+v:{version}&core=gav&rows=20&wt=json',
                                timeout=5,
                                proxies=BURP_PROXY,
                                verify=False)
            if output.json()['response']['numFound'] != 0:
                return output
        else:
            package = urllib.parse.quote(name,safe='')
            version = re.sub('[^0-9A-Za-z\-\.]+', '', version)
            return session.get(f"https://deps.dev/_/s/{provider}/p/{package}/v/{version}/dependencies",
                            timeout=5,
                            proxies=BURP_PROXY,
                            verify=False)
    except Exception as e:
        print("[-] We have been rate limited, going to sleep for 5 minutes.")
        print(f"Exception: {e}")
        # sleep(300) #this means the API drop our requests
        return None
