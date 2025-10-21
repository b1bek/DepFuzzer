import re
import json
import glob
import requirements
import defusedxml.minidom as xml
from pip._vendor import tomli

class RecoverDependencies:
    """
    Class used to parse projects and recover dependencies of a specific programming language
    """

    def __init__(self, path, provider):
        self.path = path
        self.provider = provider
        self.dependencies = {}
        self.associate_projects_dependencies = {}
        self.to_exclude = []

    def get_npm_dependencies(self):
        """
        Method used to recover all NPM dependencies from projects
        """
        packages_json = []
        for filename in glob.glob(f"{self.path}/**/package.json", recursive=True):
            packages_json.append(filename)

        for package_json in packages_json:
            with open(package_json,"r",encoding="utf-8") as fd:
                content = json.loads(fd.read())

            if content.get("workspaces"):
                workspaces = content.get("workspaces")
                # Handle both array format and object format for workspaces
                if isinstance(workspaces, list):
                    packages = workspaces
                elif isinstance(workspaces, dict) and workspaces.get("packages"):
                    packages = workspaces["packages"]
                else:
                    packages = []
                
                for custom_package in packages:
                    for filename in glob.glob(f"{self.path}/**/{custom_package}", recursive=True):
                        self.to_exclude.append(filename.split(custom_package.split("/")[0])[1].replace("/",""))

            if content.get("dependencies"):
                names = content["dependencies"].keys()
                for name in names:
                    if (self.dependencies.get(name) is None
                        and "https" not in content["dependencies"][name]
                        and "git" not in content["dependencies"][name]
                        and name not in self.to_exclude):
                        self.dependencies[name] = content["dependencies"][name]

            if content.get("devDependencies"):
                names = content["devDependencies"].keys()
                for name in names:
                    if (self.dependencies.get(name) is None
                        and "https" not in content["devDependencies"][name]
                        and "git" not in content["devDependencies"][name]
                        and name not in self.to_exclude):
                        self.dependencies[name] = content["devDependencies"][name]

    def get_cargo_dependencies(self):
        """
        Method used to recover all cargo dependencies from projects
        """
        cargos_toml = []
        local_crates = []
        for filename in glob.glob(f"{self.path}/**/Cargo.toml", recursive=True):
            cargos_toml.append(filename)
        for cargo_toml in cargos_toml:
            with open(cargo_toml,"r",encoding="utf-8") as fd:
                content = tomli.loads(fd.read())

            if content.get("patch") and content.get("patch").get("crates-io"):
                for custom_crate in content.get("patch").get("crates-io"):
                    local_crates.append(custom_crate)

            if content.get("dependencies"):
                names = content["dependencies"].keys()
                for name in names:
                    if self.dependencies.get(name) is None:
                        if isinstance(content["dependencies"][name], str):
                            self.dependencies[name] = content["dependencies"][name]
                        else:
                            if (content["dependencies"][name].get("version") is not None
                                and content["dependencies"][name].get("path") is None
                                and content["dependencies"][name].get("git") is None):
                                self.dependencies[name] = content["dependencies"][name].get("version").split("-")[0]

            if content.get("dev-dependencies"):
                names = content["dev-dependencies"].keys()
                for name in names:
                    if self.dependencies.get(name) is None:
                        if isinstance(content["dev-dependencies"][name], str):
                            self.dependencies[name] = content["dev-dependencies"][name]
                        else:
                            if (content["dev-dependencies"][name].get("version") is not None
                                and content["dev-dependencies"][name].get("path") is None
                                and content["dev-dependencies"][name].get("git") is None):
                                self.dependencies[name] = content["dev-dependencies"][name].get("version").split("-")[0]

        #Remove local crate from dependencies (can't be takeover even if didn't exists)
        for local_crate in local_crates:
            if self.dependencies.get(local_crate):
                self.dependencies.pop(local_crate)

    def get_pypi_dependencies(self):
        """
        Method used to recover all pypi dependencies from projects
        """
        pypi_files = []
        for filename in glob.glob(f"{self.path}/**/pyproject.toml", recursive=True):
            pypi_files.append(filename)
        for filename in glob.glob(f"{self.path}/**/requirements*.txt", recursive=True):
            pypi_files.append(filename)
        for pypi_file in pypi_files:
            with open(pypi_file,"r",encoding="utf-8") as fd:
                if pypi_file.endswith(".toml"):
                    data = tomli.loads(fd.read())
                    toml_dependencies = data.get("project", {}).get("dependencies", [])
                    toml_dependencies += data.get("tool", {}).get("poetry", {}).get("dependencies", {})
                    toml_dependencies += data.get("tool", {}).get("poetry", {}).get("dev-dependencies", {})
                    regex_version = r'([0-9]+\.[0-9]+\.[0-9]+)|([0-9]+\.[0-9]+)'
                    regex_name = r'[a-zA-Z0-9\-]+'
                    for dep in toml_dependencies:
                        potential_ver = re.search(regex_version,dep)
                        if potential_ver is not None:
                            version = potential_ver.group(0)
                        else:
                            version = ""
                        name = re.search(regex_name, dep).group(0)
                        if name not in self.dependencies:
                            self.dependencies[name] = version
                else:
                    try:
                        for req in requirements.parse(fd):
                            if req.name not in self.dependencies:
                                if len(req.specs) > 0:
                                    self.dependencies[req.name] = req.specs[0][1]
                                else:
                                    self.dependencies[req.name] = ""
                    except Exception as _:
                        continue

    def get_go_dependencies(self):
        """
        Method used to recover all golang dependencies from projects
        """
        gomod_files = []
        for filename in glob.glob(f"{self.path}/**/go.mod", recursive=True):
            gomod_files.append(filename)

        inside_require_block = False
        for gomod_file in gomod_files:
            with open(gomod_file, 'r', encoding="utf-8") as file:
                for line in file:
                    if line.startswith("require ("):
                        inside_require_block = True
                        continue
                    elif inside_require_block and line.strip() == ")":
                        inside_require_block = False
                        continue

                    if inside_require_block:
                        parts = line.split()
                        if len(parts) >= 2:
                            module_name = parts[0]
                            version = parts[1]
                            if module_name not in self.dependencies:
                                self.dependencies[module_name.replace('"',"")] = version

    def get_maven_dependencies(self):
        """
        Method used to recover all java maven dependencies from projects
        """
        pomxml_files = []
        for filename in glob.glob(f"{self.path}/**/pom.xml", recursive=True):
            pomxml_files.append(filename)

        for pomxml_file in pomxml_files:
            dom = xml.parse(pomxml_file)
            dependencies = dom.getElementsByTagName('dependency')
            for dependency in dependencies:
                group_id = dependency.getElementsByTagName('groupId')[0].childNodes[0].data
                artifact_id = dependency.getElementsByTagName('artifactId')[0].childNodes[0].data
                version = dependency.getElementsByTagName('version')[0].childNodes[0].data

                package_name = f'{group_id}:{artifact_id}'
                self.dependencies[package_name] = version

    def get_gradle_dependencies(self):
        """
        Method used to recover all java gradle dependencies from projects
        """

        buildgradle_files = []
        for filename in glob.glob(f"{self.path}/**/build.gradle", recursive=True):
            buildgradle_files.append(filename)
        
        for buildgradle_file in buildgradle_files:
            with open(buildgradle_file, 'r') as file:
                gradle_content = file.read()

            dependency_pattern = re.compile(r'(\w+)\s\'([\w.-]+):([\w.-]+):([\w.-]+)\'')
            dependencies = dependency_pattern.findall(gradle_content)
            for dependency in dependencies:
                package_name = f'{dependency[1]}:{dependency[2]}'
                version = dependency[3]
                self.dependencies[package_name] = version

    def get_gem_dependencies(self):
        """
        Method used to recover all ruby gem dependencies from projects
        """

        gemfile_files = []
        for filename in glob.glob(f"{self.path}/**/Gemfile", recursive=True):
            gemfile_files.append(filename)

        for gemfile_file in gemfile_files:
            with open(gemfile_file, 'r') as file:
                for line in file.readlines():
                    if not line.startswith('#') and len(line.strip()) > 0:
                        if line.startswith('gem '):
                            parts = line.split(',')
                            package_name = re.split(r'["\']', parts[0])[1]
                            try:
                                version = re.split(r'["\']', parts[1])[1].split(' ')[1].strip()
                            except:
                                version = ''
                            self.dependencies[package_name] = version


    def run(self):
        """
        Method used to run the right function to recover dependencies
        """
        print(f"[+] Processing repositories for {self.provider}")
        if self.provider == "pypi":
            self.get_pypi_dependencies()
        elif self.provider == "npm":
            self.get_npm_dependencies()
        elif self.provider == "cargo":
            self.get_cargo_dependencies()
        elif self.provider == "go":
            self.get_go_dependencies()
        elif self.provider == "maven":
            self.get_maven_dependencies()
        elif self.provider == "gradle":
            self.get_gradle_dependencies()
        elif self.provider == "rubygems":
            self.get_gem_dependencies()
        print(f"[+] Found {len(self.dependencies)} {self.provider} dependencies")

