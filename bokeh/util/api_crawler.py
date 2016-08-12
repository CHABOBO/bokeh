import ast, os, copy, subprocess


__all__ = ["api_crawler"]


class APICrawler(object):
    exclude = ("tests", "static", "sampledata", "mplexplorer")

    def __init__(self, directory):
        self.directory = directory

    def is_public(self, name):
        return not name.startswith("_", 0, 1) or name == "__init__"

    def is_function(self, ast_node):
        return isinstance(ast_node, ast.FunctionDef) and ast_node.col_offset == 0

    def is_class(self, ast_node):
        return isinstance(ast_node, ast.ClassDef)

    def get_classes(self, source):
        parsed = ast.parse(source)
        classes = [node for node in ast.walk(parsed) if self.is_class(node) and self.is_public(node.name)]
        class_defs = {}
        for x in classes:
            class_defs[x.name] = {}
            methods = []
            for y in x.body:
                if isinstance(y, ast.FunctionDef) and self.is_public(y.name):
                    methods.append(y.name)
            class_defs[x.name]["methods"] = methods
        return class_defs

    def get_functions(self, source):
        parsed = ast.parse(source)
        functions = [node for node in ast.walk(parsed) if self.is_function(node) and self.is_public(node.name)]
        functions = [x.name for x in functions]
        return functions

    def get_filenames(self, directory):
        files = []
        tree = os.walk(directory, topdown=True, followlinks=False)
        for dirpath, dirnames, filenames in tree:
            for folder in self.exclude:
                if folder in dirpath:
                    break
            else:
                for name in filenames:
                    if name.endswith(".py") and not name.startswith("_"):
                        files.append(os.path.join(dirpath, name))
        return files

    def get_files_dict(self, filenames):
        files_dict = {}
        for x in filenames:
            with open(x, "r") as f:
                source = f.read()
                files_dict[x] = {"classes": {}, "functions": []}
                files_dict[x]["classes"] = self.get_classes(source)
                files_dict[x]["functions"] = self.get_functions(source)
        return files_dict

    def get_crawl_dict(self):
        files = self.get_filenames(self.directory)
        files_dict = self.get_files_dict(files)
        return files_dict

    def diff_operation(self, a, b):
        # Returns items removed
        return list(a - b)

    def combinaton_diff_operation(self, a, b):
        # Returns items added
        return list((a ^ b) - a)

    def diff_modules(self, former, latter, added=False):
        if added:
            operation = self.combinaton_diff_operation
        else:
            operation = self.diff_operation

        combined = copy.deepcopy(former)
        combined.update(latter)
        diff = {}
        intersection = {}
        files_intersection = set(former) & set(latter)
        files_diff = operation(set(former), set(latter))

        # Diff files
        for x in combined.keys():
            if x in files_diff:
                diff[x] = combined[x]
                diff[x] = {}
            else:
                intersection[x] = combined[x]

        # Diff functions and classes
        for x in intersection.keys():
            former_items = former.get(x)
            latter_items = latter.get(x)
            if former_items and latter_items:
                function_diff = operation(set(former_items["functions"]), set(latter_items["functions"]))
                class_diff = operation(set(list(former_items["classes"].keys())), set(list(latter_items["classes"].keys())))
                if function_diff or list(class_diff):
                    diff[x]= copy.deepcopy(intersection[x])
                    if list(class_diff):
                        diff_dict = {y: {} for y in class_diff}
                        diff[x]["classes"] = diff_dict
                    else:
                        diff[x]["classes"] = {}

                    if function_diff:
                        diff[x]["functions"] = list(function_diff)
                    else:
                        diff[x]["functions"] = []

        # Diff methods
        for x in intersection.keys():
            former_classes = former[x].get("classes") if former.get(x) else {}
            latter_classes = latter[x].get("classes") if latter.get(x) else {}
            if former_classes and latter_classes:
                for y in intersection[x]["classes"]:
                    # Prevent NoneType errors by returning empty dict.
                    former_methods = former[x]["classes"].get(y, {})
                    latter_methods = latter[x]["classes"].get(y, {})
                    if former_methods.get("methods") and latter_methods.get("methods"):
                        former_values = set(list(former_methods.values())[0])
                        latter_values = set(list(latter_methods.values())[0])
                        methods_diff = operation(former_values, latter_values)
                        if methods_diff:
                            diff[x]["classes"][y] = copy.deepcopy(intersection[x]["classes"][y])
                            diff[x]["classes"][y]["methods"] = methods_diff
        return diff

    def parse_diff(self, diff, added=False):
        parsed_diff = []
        if added:
            method = "ADDED"
        else:
            method = "DELETED"
        for x in diff.keys():
            formatted_string = "%s %s" % (method, os.path.splitext(x.replace("/", "."))[0])
            if diff[x].values():
                for y in diff[x].values():
                    if isinstance(y, dict) and y:
                        for z in y.keys():
                            if not y[z].values():
                                parsed_diff.append("%s.%s" % (formatted_string, z))
                            else:
                                for a in y[z].values():
                                    for b in a:
                                        parsed_diff.append("%s.%s.%s" % (formatted_string, z, b))
                    elif isinstance(y, list) and y:
                        for z in y:
                            class_string = "%s" % z
                            parsed_diff.append("%s.%s" % (formatted_string, class_string))
            else:
                parsed_diff.insert(0, formatted_string)
        return parsed_diff


api_crawler = APICrawler