from dexy.dexy_filter import DexyFilter
from ordereddict import OrderedDict
import pexpect
import re
import time

class ProcessLinewiseInteractiveFilter(DexyFilter):
    """
    Intended for use with interactive processes, such as python interpreter,
    where your goal is to have a session transcript divided into same sections
    as input. Sends input line-by-line.
    """
    PROMPTS = ['>>>', '...'] # Python uses >>> prompt normally and ... when in multi-line structures like loops
    TRIM_PROMPT = '>>>'
    LINE_ENDING = "\r\n"
    SAVE_VARS_TO_JSON_CMD = None
    ALIASES = ['processlinewiseinteractivefilter']
    ALLOW_MATCH_PROMPT_WITHOUT_NEWLINE = False

    def prompt_search_terms(self):
        """
        Search first for the prompt (or prompts) following a line ending.
        Also optionally allow matching the prompt with no preceding line ending.
        """
        if hasattr(self, 'PROMPT'):
            prompts = [self.PROMPT]
        else:
            prompts = self.PROMPTS

        if self.ALLOW_MATCH_PROMPT_WITHOUT_NEWLINE:
            return ["%s%s" % (self.LINE_ENDING, p) for p in prompts] + prompts
        else:
            return ["%s%s" % (self.LINE_ENDING, p) for p in prompts]

    def lines_for_section(self, section_text):
        """
        Take the section text and split it into lines which will be sent to the
        interpreter. This can be overridden if lines need to be defined
        differently, or if you don't want the extra newline at the end.
        """
        return section_text.splitlines() + ["\n"]

    def strip_trailing_prompts(self, section_transcript):
        lines = section_transcript.splitlines()
        while len(lines) > 0 and re.match("^\s*(%s)\s*$|^\s*$" % self.TRIM_PROMPT, lines[-1]):
            lines = lines[0:-1]
        return self.LINE_ENDING.join(lines)

    def process_dict(self, input_dict):
        output_dict = OrderedDict()

        # If we want to automatically record values of local variables in the
        # script we are running, we add a section at the end of script
        do_record_vars = self.artifact.args.has_key('record-vars') and self.artifact.args['record-vars']
        if do_record_vars:
            if not self.SAVE_VARS_TO_JSON_CMD:
                raise Exception("Can't record vars since SAVE_VARS_TO_JSON_CMD not set.")
            artifact = self.artifact.add_additional_artifact(self.artifact.key + "-vars", 'json')
            self.log.debug("Added additional artifact %s (hashstring %s) to store variables" % (artifact.key, artifact.hashstring))
            section_text = self.SAVE_VARS_TO_JSON_CMD % artifact.filename()
            input_dict['dexy--save-vars'] = section_text

        search_terms = self.prompt_search_terms()
        env = self.setup_env()
        timeout = self.setup_timeout()

        # Spawn the process
        proc = pexpect.spawn(
                self.executable(),
                cwd=self.artifact.artifacts_dir,
                env=env)

        # Capture the initial prompt
        proc.expect_exact(search_terms, timeout=timeout)
        start = proc.before + proc.after
        for section_key, section_text in input_dict.items():
            section_transcript = start
            start = ""

            lines = self.lines_for_section(section_text)

            for l in lines:
                section_transcript += start
                proc.send(l + "\n")
                proc.expect_exact(search_terms, timeout=timeout)
                section_transcript += proc.before
                start = proc.after

            # Save this section's output
            output_dict[section_key] = self.strip_trailing_prompts(section_transcript)

        try:
            proc.close()
        except pexpect.ExceptionPexpect:
            raise Exception("process %s may not have closed" % proc.pid)

        if proc.exitstatus:
            self.handle_subprocess_proc_return(proc.exitstatus, str(output_dict))

        return output_dict

class PythonLinewiseInteractiveFilter(ProcessLinewiseInteractiveFilter):
    ALIASES = ['pycon']
    EXECUTABLE = 'python'
    INPUT_EXTENSIONS = [".txt", ".py"]
    OUTPUT_EXTENSIONS = [".pycon"]
    TAGS = ['python', 'interpreter', 'language']
    VERSION = 'python --version'

    SAVE_VARS_TO_JSON_CMD = """
import json
dexy__vars_file = open("%s", "w")
dexy__x = {}
for dexy__k, dexy__v in locals().items():
    dexy__x[dexy__k] = str(dexy__v)

json.dump(dexy__x, dexy__vars_file)
dexy__vars_file.close()
"""

class RLinewiseInteractiveFilter(ProcessLinewiseInteractiveFilter):
    """
    Runs R
    """
    ALIASES = ['r', 'rint']
    EXECUTABLE = "R --quiet --vanilla"
    INPUT_EXTENSIONS = ['.txt', '.r', '.R']
    OUTPUT_EXTENSIONS = ['.Rout']
    PROMPTS = [">", "+"]
    TAGS = ['r', 'interpreter', 'language']
    TRIM_PROMPT = ">"
    VERSION = "R --version"
    ALLOW_MATCH_PROMPT_WITHOUT_NEWLINE = True
    SAVE_VARS_TO_JSON_CMD = """
if ("rjson" %%in%% installed.packages()) {
    library(rjson)
    dexy__json_file <- file("%s", "w")
    writeLines(toJSON(as.list(environment())), dexy__json_file)
    close(dexy__json_file)
} else {
   cat("Can't automatically save environment to JSON since rjson package not installed.")
}
"""

class RhinoInteractiveFilter(ProcessLinewiseInteractiveFilter):
    """
    Runs rhino JavaScript interpeter.
    """
    EXECUTABLE = "rhino"
    INPUT_EXTENSIONS = [".js"]
    OUTPUT_EXTENSIONS = [".txt"]
    ALIASES = ['jsint', 'rhino']
    PROMPT = "js> "

class ClojureInteractiveFilter(ProcessLinewiseInteractiveFilter):
    """
    Runs clojure.
    """
    EXECUTABLE = 'clojure -r'
    INPUT_EXTENSIONS = [".clj", ".txt"]
    OUTPUT_EXTENSIONS = [".txt"]
    ALIASES = ['clj', 'cljint']
    PROMPT = "user=> "

    def lines_for_section(self, input_text):
        input_lines = []
        current_line = []
        in_indented_block = False
        for l in input_text.splitlines():
            if re.match("^\s+", l):
                in_indented_block = True
                current_line.append(l)
            else:
                if len(current_line) > 0:
                    input_lines.append("\n".join(current_line))
                if in_indented_block:
                    # we have reached the end of this indented block
                    in_indented_block = False
                current_line = [l]
        input_lines.append("\n".join(current_line))
        return input_lines

class ProcessTimingFilter(DexyFilter):
    """
    Runs python code N times and reports timings.
    """
    EXECUTABLE = 'python'
    VERSION = 'python --version'
    N = 10
    INPUT_EXTENSIONS = [".txt", ".py"]
    OUTPUT_EXTENSIONS = [".times"]
    ALIASES = ['timing', 'pytime']

    def process(self):
        self.artifact.generate_workfile()
        times = []
        for i in xrange(self.N):
            start = time.time()
            pexpect.run("%s %s" % (self.EXECUTABLE, self.artifact.work_filename()))
            times.append("%s" % (time.time() - start))
        self.artifact.data_dict['1'] = "\n".join(times)

