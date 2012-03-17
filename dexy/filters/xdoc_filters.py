from dexy.dexy_filter import DexyFilter
from dexy.introspect import INSTALL_DIR
from idiopidae.runtime import Composer
from pygments import highlight
from pygments.formatters.html import HtmlFormatter
from pygments.formatters.latex import LatexFormatter
from pygments.lexers.agile import PythonLexer
import idiopidae.parser
import inspect
import json
import nose
import os
import pkgutil
import shutil
import subprocess
import sys

"""
Filters that parse and process various language's documentation systems to make
this information available in Dexy documents. Filters work by processing a
config file that specifies which libraries should be processed. These filters
work for languages where documentation can be generated by referencing
installed libraries, rather than needing source code.
"""

class PythonTestFilter(DexyFilter):
    """
    Runs the tests in the specified module(s) (which must be installed on the
    system) and returns a dict with test results, source code and html or latex
    highlighted source code.
    """
    ALIASES = ['pytest']
    INPUT_EXTENSIONS = [".txt"]
    OUTPUT_EXTENSIONS = [".json"]
    LEXER = PythonLexer()
    LATEX_FORMATTER = LatexFormatter()
    HTML_FORMATTER = HtmlFormatter()

    # TODO some way to ensure tests logs get written elsewhere, they are going to main log for now - very confusing

    def process_text(self, input_text):
        loader = nose.loader.TestLoader()
        test_info = {}
        for module_name in input_text.split():
            self.log.debug("Starting to process module '%s'" % module_name)
            test_info[module_name] = {}
            tests = loader.loadTestsFromName(module_name)
            self.log.debug("Loaded tests.")
            for test in tests:
                self.log.debug("Running test suite %s" % test)
                test_passed = nose.core.run(suite=test, argv=['nosetests'])
                self.log.debug("Passed: %s" % test_passed)
                for x in dir(test.context):
                    xx = test.context.__dict__[x]
                    if inspect.ismethod(xx) or inspect.isfunction(xx):
                        source = inspect.getsource(xx.__code__)
                        html_source = highlight(source, self.LEXER, self.HTML_FORMATTER)
                        latex_source = highlight(source, self.LEXER, self.LATEX_FORMATTER)
                        test_info[module_name][xx.__name__] = {
                                'source' : source,
                                'latex_source' : latex_source,
                                'html_source' : html_source,
                                'test_passed': test_passed
                                }

        return json.dumps(test_info)

class PythonDocumentationFilter(DexyFilter):
    ALIASES = ["pydoc"]
    INPUT_EXTENSIONS = [".txt"]
    OUTPUT_EXTENSIONS = [".json"]
    COMPOSER = Composer()
    LEXER = PythonLexer()
    LATEX_FORMATTER = LatexFormatter()
    HTML_FORMATTER = HtmlFormatter()

    def fetch_item_content(self, cm):
        is_method = inspect.ismethod(cm)
        is_function = inspect.isfunction(cm)

        if is_method or is_function:
            try:
                source = inspect.getsource(cm)
            except IOError:
                source = ""

            builder = idiopidae.parser.parse('Document', source + "\n\0")
            sections = {}

            for i, s in enumerate(builder.sections):
                lines = builder.statements[i]['lines']
                sections[s] = self.COMPOSER.format(lines, self.LEXER, self.HTML_FORMATTER)

            if len(sections) == 1:
                return sections.values()[0]
            else:
                return sections
        else:
            try:
                # If this can be JSON-serialized, leave it alone...
                json.dumps(cm)
                return cm
            except TypeError:
                # ... if it can't, convert it to a string to avoid problems.
                return str(cm)

    def highlight_html(self, source):
        return highlight(source, self.LEXER, self.HTML_FORMATTER)

    def highlight_latex(self, source):
        return highlight(source, self.LEXER, self.LATEX_FORMATTER)

    def add_source_for_key(self, docs, key, source):
        if docs.has_key(key):
            self.log.debug("Skipping duplicate key %s" % key)
        else:
            self.log.debug("Adding new key %s" % key)
            docs[key] = {}
            docs[key]['value'] = source
            if not type(source) == str or type(source) == unicode:
                source = unicode(source)
            docs[key]['source'] = source
            docs[key]['html-source'] = self.highlight_html(source)
            docs[key]['latex-source'] = self.highlight_latex(source)

    def process_text(self, input_text):
        """
        input_text should be a list of installed python libraries to document.
        """
        package_names = input_text.split()
        packages = [__import__(package_name) for package_name in package_names]
        docs = {}

        for package in packages:
            self.log.debug("processing package %s" % package)
            package_name = package.__name__
            prefix = package.__name__ + "."
            for module_loader, name, ispkg in pkgutil.walk_packages(package.__path__, prefix=prefix):
                self.log.debug("in package %s processing module %s" % (package_name, name))
                try:
                    __import__(name)
                    mod = sys.modules[name]

                    for k, m in inspect.getmembers(mod):
                        self.log.debug("in package %s module %s processing element %s" % (package_name, name, k))
                        if not inspect.isclass(m) and hasattr(m, '__module__') and m.__module__.startswith(package_name):
                            # TODO figure out how to get module constants
                            key = "%s.%s" % (m.__module__, k)
                            item_content = self.fetch_item_content(m)
                            self.add_source_for_key(docs, key, item_content)

                        elif inspect.isclass(m) and m.__module__.startswith(package_name):
                            key = "%s.%s" % (name, k)
                            try:
                                item_content = inspect.getsource(m)
                                self.add_source_for_key(docs, key, item_content)
                            except IOError:
                                self.log.debug("can't get source for" % key)
                                self.add_source_for_key(docs, key, "")

                            for ck, cm in inspect.getmembers(m):
                                key = "%s.%s.%s" % (name, k, ck)
                                item_content = self.fetch_item_content(cm)
                                self.add_source_for_key(docs, key, item_content)

                        else:
                            key = "%s.%s" % (name, k)
                            item_content = self.fetch_item_content(m)
                            self.add_source_for_key(docs, key, item_content)

                except ImportError as e:
                    self.log.debug(e)

        return json.dumps(docs, indent=4)

class RDocumentationFilter(DexyFilter):
    """
    Can be run on a text file listing packages to be processed, or an R script
    which should define a list of package names (strings) named 'packages', the
    latter option so that you can include some R code prior to automated code
    running.
    """
    ALIASES = ["rdoc"]
    INPUT_EXTENSIONS = [".txt", ".R"]
    OUTPUT_EXTENSIONS = [".json"]

    def process(self):
        # Create a temporary directory to run R in.
        self.artifact.create_temp_dir()
        td = self.artifact.temp_dir()

        r_script_file = os.path.join(INSTALL_DIR, 'dexy', 'ext', "introspect.R")
        self.log.debug("script file: %s" % r_script_file)

        with open(r_script_file, "r") as f:
            r_script_contents = f.read()

        if self.artifact.input_ext == ".txt":
            # A text file containing the names of packages to process.
            package_names = self.artifact.input_text().split()
            script_start = "packages <- c(%s)" % ",".join("\"%s\"" % n for n in package_names)
        elif self.artifact.input_ext == ".R":
            script_start = self.artifact.input_text()
        else:
            raise Exception("Unexpected input file extension %s" % self.artifact.input_ext)

        script_filename = os.path.join(td, "script.R")

        with open(script_filename, "w") as f:
            f.write(script_start + "\n")
            f.write(r_script_contents)

        command = "R --slave --vanilla < script.R"
        self.log.debug("About to run %s" % command)

        proc = subprocess.Popen(command, shell=True,
                                cwd=td,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                )
        stdout, stderr = proc.communicate()
        self.artifact.stdout = stdout
        shutil.copyfile(os.path.join(td, "dexy--r-doc-info.json"), self.artifact.filepath())

