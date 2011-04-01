from dexy.handler import DexyHandler
import os
import subprocess

class ProcessStdoutHandler(DexyHandler):
    """
    Runs python script and returns STDOUT.
    """
    EXECUTABLE = '/usr/bin/env python'
    VERSION = '/usr/bin/env python --version'
    WINDOWS_EXECUTABLE = 'python'
    INPUT_EXTENSIONS = [".txt", ".py"]
    OUTPUT_EXTENSIONS = [".txt"]
    ALIASES = ['py', 'python', 'pyout']

    def process(self):
        self.artifact.generate_workfile()
        command = "%s %s" % (self.executable(), self.artifact.work_filename())
        cla = self.artifact.command_line_args()
        if self.doc.args.has_key('env'):
            env = os.environ
            env.update(self.doc.args['env'])
        else:
            env = None

        if cla:
            command = "%s %s" % (command, cla)
        self.log.debug(command)

        proc = subprocess.Popen(command, shell=True,
                                cwd=self.artifact.artifacts_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                env=env)
        stdout, stderr = proc.communicate()
        self.artifact.data_dict['1'] = stdout
        self.artifact.stdout = stderr

        if proc.returncode is None:
            raise Exception("no return code, proc not finished!")
        elif proc.returncode != 0:
            if self.doc.controller.args.ignore_errors:
                self.log.warn(stderr)
            else:
                print stderr
                raise Exception("""proc returned nonzero status code! if you don't
want dexy to raise errors on failed scripts then pass the --ignore-errors option""")

class BashHandler(ProcessStdoutHandler):
    """
    Runs bash script and returns STDOUT.
    """
    EXECUTABLE = '/usr/bin/env bash'
    VERSION = '/usr/bin/env bash --version'
    INPUT_EXTENSIONS = [".sh", ".bash", ".txt"]
    OUTPUT_EXTENSIONS = [".txt"]
    ALIASES = ['bash']

class PhpHandler(ProcessStdoutHandler):
    """
    Runs php script and returns STDOUT.
    """
    EXECUTABLE = '/usr/bin/env php'
    VERSION = '/usr/bin/env php --version'
    INPUT_EXTENSIONS = [".php"]
    OUTPUT_EXTENSIONS = [".html", ".txt"]
    ALIASES = ['php']

class EscriptHandler(ProcessStdoutHandler):
    """
    Runs escript (erlang) and returns STDOUT.
    """
    EXECUTABLE = '/usr/bin/env escript'
    INPUT_EXTENSIONS = [".erl"]
    OUTPUT_EXTENSIONS = [".txt"]
    ALIASES = ['escript']

class LuaHandler(ProcessStdoutHandler):
    """
    Runs lua script and returns STDOUT.
    """
    EXECUTABLE = '/usr/bin/env lua'
    VERSION = '/usr/bin/env lua -v'
    INPUT_EXTENSIONS = ['.lua']
    OUTPUT_EXTENSIONS = ['.txt']
    ALIASES = ['lua']

class RedclothHandler(ProcessStdoutHandler):
    """
    Runs redcloth, converts textile markup to HTML.
    """
    EXECUTABLE = '/usr/bin/env redcloth'
    VERSION = '/usr/bin/env redcloth --version'
    INPUT_EXTENSIONS = [".txt", ".textile"]
    OUTPUT_EXTENSIONS = [".html"]
    ALIASES = ['redcloth', 'textile']

class RedclothLatexHandler(ProcessStdoutHandler):
    """
    Runs redcloth, converts textile markup to LaTeX.
    """
    EXECUTABLE = '/usr/bin/env redcloth -o latex'
    VERSION = '/usr/bin/env redcloth --version'
    INPUT_EXTENSIONS = [".txt", ".textile"]
    OUTPUT_EXTENSIONS = [".tex"]
    ALIASES = ['redclothl', 'latextile']

class Rst2HtmlHandler(ProcessStdoutHandler):
    EXECUTABLE = '/usr/bin/env rst2html.py'
    INPUT_EXTENSIONS = [".rst", ".txt"]
    OUTPUT_EXTENSIONS = [".html"]
    ALIASES = ['rst2html']

class Rst2LatexHandler(ProcessStdoutHandler):
    EXECUTABLE = '/usr/bin/env rst2latex.py'
    INPUT_EXTENSIONS = [".rst", ".txt"]
    OUTPUT_EXTENSIONS = [".tex"]
    ALIASES = ['rst2latex']

class Rst2BeamerHandler(ProcessStdoutHandler):
    EXECUTABLE = '/usr/bin/env rst2beamer'
    INPUT_EXTENSIONS = [".rst", ".txt"]
    OUTPUT_EXTENSIONS = [".tex"]
    ALIASES = ['rst2beamer']

class SloccountHandler(ProcessStdoutHandler):
    EXECUTABLE = '/usr/bin/env sloccount'
    VERSION = '/usr/bin/env sloccount --version'
    INPUT_EXTENSIONS = [".*"]
    OUTPUT_EXTENSIONS = [".txt"]
    ALIASES = ['sloc', 'sloccount']

class RubyStdoutHandler(ProcessStdoutHandler):
    EXECUTABLE = '/usr/bin/env ruby'
    VERSION = '/usr/bin/env ruby --version'
    INPUT_EXTENSIONS = [".txt", ".rb"]
    OUTPUT_EXTENSIONS = [".txt"]
    ALIASES = ['rb']


