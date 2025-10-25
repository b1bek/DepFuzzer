"""
File used to declare the analyzer for dependencies
"""

import requests
from utils.misc import dependency_exists, recover_dependencies, batch_check_dependencies
from utils.email_checker import EmailChecker


class AnalyzeDependencies:
    """
    Class used to analyze and recover all dependencies of environment
    """

    def __init__(self, provider, dependencies, print_takeover, output, check_email):
        self.packages_json = []
        self.dependencies = dependencies
        self.already_done = {}
        self.provider = provider
        self.takeover = {}
        self.print_takeover = print_takeover
        self.output = output
        self.check = check_email
        self.email_takeover = []
        self.session = requests.Session()

    def check_dependency(self, root_package, root_version):
        """
        Method used to check if a dependency exists
        """
        stack = []
        stack.append({root_package: root_version})
        while len(stack) != 0:
            package, version = list(stack.pop().items())[0]
            if package is not None and dependency_exists(package, self.provider, self.session):
                if self.check:
                    self.check_email(package)
                deps = recover_dependencies(package, version, self.provider, self.session)
                self.already_done[package] = version
                if deps is not None and deps.status_code == 200:
                    deps = deps.json()
                    if deps.get("dependencyCount") and deps["dependencyCount"] > 0:
                        for dep in deps["dependencies"][1:]:
                            subpackage = dep["package"]["name"]
                            subpackage_version = dep["version"]
                            if (
                                subpackage not in self.already_done
                                and subpackage not in [list(x.keys())[0] for x in stack]
                            ):
                                stack.append({subpackage: subpackage_version})
            else:
                self.already_done[package] = version
                if package not in self.takeover:
                    self.takeover[package] = version
                if self.print_takeover:
                    if package is not None:
                        if "@" in package:
                            pass
                            # print(
                            #     f"""[DEBUG] {package} is not declared but cannot be taken over because it belongs to an external organization\nYou might have to check manually if the organization exists."""
                            # )
                        else:
                            print(f"[DEBUG] {package}:{version} might be taken over !")

    def analyze_dependencies(self):
        """
        Method used to iterate over all dependencies
        """
        # First, batch check all root dependencies for faster processing
        root_packages = [key for key in self.dependencies.keys() if key not in self.already_done]
        if root_packages:
            print(f"[+] Batch checking {len(root_packages)} dependencies...")
            
            # Clean NPM alias package names before checking
            packages_to_check = []
            for package in root_packages:
                version = self.dependencies[package]
                if self.provider == "npm" and version and "npm:" in version:
                    # Handle NPM aliases like "fdir1" with version "npm:fdir@1.2.0" -> check "fdir"
                    npm_part = version.split("npm:")[1]
                    if "@" in npm_part and not npm_part.startswith("@"):
                        clean_name = npm_part.split("@")[0]
                        packages_to_check.append(clean_name)
                    elif npm_part.startswith("@"):
                        # Scoped package handling
                        parts = npm_part.split("@")
                        if len(parts) >= 3:
                            clean_name = "@" + parts[1] + "@" + parts[2].split("@")[0]
                            packages_to_check.append(clean_name)
                        else:
                            packages_to_check.append(package)
                    else:
                        packages_to_check.append(npm_part)
                else:
                    packages_to_check.append(package)
            
            batch_results = batch_check_dependencies(packages_to_check, self.provider, self.session)
            
            # Map results back to original package names
            final_results = {}
            for i, original_package in enumerate(root_packages):
                checked_package = packages_to_check[i]
                final_results[original_package] = batch_results.get(checked_package, False)
            
            batch_results = final_results
            
            # Process batch results
            for package, exists in batch_results.items():
                if package in self.dependencies:
                    version = self.dependencies[package]
                    if package not in self.already_done:
                        self.already_done[package] = version
                        if not exists:
                            # Package doesn't exist - flag as takeoverable
                            if package not in self.takeover:
                                self.takeover[package] = version
                            if self.print_takeover and package is not None:
                                if "@" not in package:
                                    print(f"[DEBUG] {package}:{version} might be taken over !")
                        else:
                            # Package exists - analyze its dependencies
                            # self.check_dependency(package, version)
                            pass

    def _check_org_exists(self, org_prefix, provider, package_files_mgr):
        """
        Check if any packages exist with the given organization prefix
        """
        try:
            if provider == "npm":
                # For NPM, check if any packages start with the org prefix
                file_path = package_files_mgr._get_file_path(provider)
                if not file_path.exists():
                    return False
                
                import json
                with open(file_path, 'r') as f:
                    packages = json.load(f)
                
                # Check if any package starts with the org prefix
                for pkg in packages:
                    if pkg.startswith(org_prefix):
                        return True
                return False
            else:
                # For other ecosystems, this logic might be different
                return False
        except Exception:
            return False

    def check_email(self, package):
        """
        Method used to check if an email exists
        """
        ec = EmailChecker(self.provider, package)
        res = ec.check_email()
        if len(res) > 0:
            for r in res:
                if r[0] not in self.email_takeover:
                    self.email_takeover.append(r[0])
                    print(
                        f"""The account associated to dependency {package} is : {r[1]} and the domain {r[0]} might be purchased !"""
                    )

    def run(self):
        """
        Main method to run analysis
        """
        print(f"[+] Starting analysis for {self.provider}...")
        self.analyze_dependencies()
        if len(self.takeover) > 0:
            if self.output is not None:
                with open(self.output, "w", encoding="utf-8") as fd:
                    for package, version in self.takeover.items():
                        fd.write(f"{package}:{version}\n")
                print(f"Results saved to {self.output} !")
            else:
                # Group packages by organization for cleaner output
                org_packages = {}  # org_name -> list of packages
                regular_packages = []
                
                for package, version in self.takeover.items():
                    if package is not None:
                        if "@" in package and "/" in package:
                            # Extract organization from scoped package
                            org_prefix = package.split("/")[0] + "/"
                            
                            # Check if organization exists
                            from utils.misc import package_files_mgr
                            org_exists = self._check_org_exists(org_prefix, self.provider, package_files_mgr)
                            
                            if not org_exists:
                                # Group unknown org packages
                                if org_prefix not in org_packages:
                                    org_packages[org_prefix] = []
                                org_packages[org_prefix].append(package)
                            # If org exists, don't print anything (silent)
                        else:
                            regular_packages.append((package, version))
                
                # Print regular takeoverable packages
                for package, version in regular_packages:
                    print(f"[+] {package}:{version} might be taken over !")
                
                # Print grouped organization messages
                for org_prefix, packages in org_packages.items():
                    if len(packages) == 1:
                        print(f"[+] {packages[0]} is not declared but cannot be taken over because it belongs to an external organization")
                        print("You might have to check manually if the organization exists.")
                    else:
                        print(f"[+] {len(packages)} packages from {org_prefix} are not declared but cannot be taken over because they belong to an external organization")
                        print("You might have to check manually if the organization exists.")
                        print(f"Packages: {', '.join(packages)}")
        else:
            print("[+] No package can be taken over !")
