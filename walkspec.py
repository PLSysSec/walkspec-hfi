"""
Script to compile SPEC06 benchmarks. Allows compilation with extra files 
(like hfi_check.c).

Also outputs run scripts for each benchmark, but instead of running everything
that normally gets specinvoke'd, we just run the first command. 
We want one run script for native execution (as a sanity check), then another
for gem5 (for portability).

"""

import os
import pathlib
import re
from subprocess import run, DEVNULL, PIPE
import time

def make_gem5_cmd(gem5_dir, benchmark, workload, args, config):
    # TODO: tune this
    return f'{gem5_dir}/build/X86/gem5.fast \
--outdir={gem5_dir}/run_{benchmark}_{config}  \
{gem5_dir}/configs/example/se.py -c {workload} -o "{args}" --mem-size=4GB \
-I 50000000000'

def __main__():
    # ask the user if they want to use default values
    print("""\
    Default values:
        SPEC06:         /spec
        gem5:           /gem5
        config name:    wasmSimConfig
        scripts dir:    /walkspec/spec_scripts
        extra files:    [/walkspec/hfi_check.c]
    
    Make sure you have the wasi-sdk set up at /wasi-sdk.
    
    ------------
""")
    if input("Use default values? (y/n) ") == "y":
        # these are joey's docker img default values
        SPEC06_DIR = '/spec'
        GEM5_DIR = '/gem5'
        #CONFIG_NAME = 'simConfig'
        CONFIG_NAME = 'wasmSimConfig'
        SCRIPT_DIR = '/walkspec/spec_scripts'
        EXTRA_COMP_FILES = ['/walkspec/hfi_check.c']
    else:
        # get the SPEC06 directory from the user
        SPEC06_DIR = input("Enter the SPEC06 directory's absolute path: ")
        # get the gem5 directory from the user
        GEM5_DIR = input("Enter the gem5 directory's absolute path: ")
        # get the config name from the user
        CONFIG_NAME = input("Enter your config name: ")
        # get the script output directory from the user
        SCRIPT_DIR = input("Enter the directory to save scripts: ")
        # get any extra compilation files from the user
        EXTRA_COMP_FILES = []
        while True:
            extra_file = input("Enter an extra file (absolute path) to compile (or \
a blank line to continue):")
            if extra_file == "":
                break
            EXTRA_COMP_FILES.append(extra_file)

    SHEBANG = "#!/bin/bash\n"  # sorry zsh lovers
    start_time = time.ctime()
    # from the config file, get the line which starts with 'ext':
    # this is part of the build and run directories
    os.chdir(SPEC06_DIR)
    with open(f'config/{CONFIG_NAME}.cfg', 'r') as f:
        for line in f:
            if line.startswith('ext'):
                EXT = line.split('=')[1].strip()
                break

    # here's all of the C-only benchmarks
    C_BENCHMARKS = ['400', '401', '403', '429', '445', '456', '458', '462', '464', \
                    '433', '470', '482']

    """
    currently working: 
    everything except 400.perlbench!
    """
    # log successful builds, to be displayed at the end
    successes = []

    # for gem5-HFI, we need to make an environment variable file
    os.system(f'echo "HFI=\'1\'" > {SCRIPT_DIR}/hfi_env.txt')
    HFI_ENV = f'{SCRIPT_DIR}/hfi_env.txt'

    for benchmark in C_BENCHMARKS:
        if benchmark == '400': continue  # perl doesn't work
        ### BENCHMARK COMPILATION ###
        # do a fake run to get the runspec output
        run_log = run(
            f'. ./shrc && go {benchmark} && runspec --config=simConfig --loose \
--fake --iterations=1 {benchmark}', shell=True, capture_output=True 
    ).stdout.decode('utf-8')
        # in that output, we want to run everything labelled a "fake command from make"
        BUILD_CMDS = []
        INVOKE_CMDS = ''  # we're gonna split this differently
        is_build_cmd = False
        is_invoke_cmd = False
        for line in run_log.split('\n'):
            # get the build commands
            if line == r"%% End of fake output from make (specmake -n build)":
                is_build_cmd = False
            if is_build_cmd:
                BUILD_CMDS.append(line)
            if line == r"%% Fake commands from make (specmake -n build):":
                is_build_cmd = True

            # get the invoke commands too
            if line.startswith(r"%% End of fake output from benchmark_run"):
                is_invoke_cmd = False
            if is_invoke_cmd:
                INVOKE_CMDS += line + '\n'
            if line.startswith(r"%% Fake commands from benchmark_run"):
                is_invoke_cmd = True

        if is_build_cmd:
            print("Specmake shouldn't have been the last fake output!")
            exit()
        if is_invoke_cmd:
            print("Invoke commands shouldn't have been the last fake output!")
            exit()
        if not BUILD_CMDS:
            print("No build commands found!")
            exit()
        if not INVOKE_CMDS:
            print("No invoke commands found!")
            exit()

        # the binary name is the very last thing in BUILD_CMDS[-1]
        BINARY_NAME = BUILD_CMDS[-1].split(' ')[-1]
        
        # get the benchmark's build directory
        ALL_BUILDS_DIR = run(f'. ./shrc && go {benchmark} build', shell=True,
    capture_output=True).stdout.decode('utf-8').strip()
        # climb into the fake-built directory -- it's the most recently created
        BUILD_DIR = max(filter(pathlib.PosixPath.is_dir,
 pathlib.Path(ALL_BUILDS_DIR).iterdir()), key=os.path.getctime)
        os.chdir(BUILD_DIR)

        # since we're fake building, the invoke commands have to be changed a bit
        INVOKE_CMDS = re.sub(r'\.\./run_\S+?\s', f'{BUILD_DIR}/{BINARY_NAME} ',
    INVOKE_CMDS)

        # to avoid weird coherency issues, remove the binary if it's present 
        os.system(f'rm -f {BINARY_NAME}')

        # now, from within the build directory, run the build commands
        # this is the same as running make build (but nothing else in the makefile)
        # in particular, the last command makes an executable; we can add in any
        # extra files (like the HFI one) there
        for cmd in BUILD_CMDS[:-1]:
            os.system(cmd)
        last_build_cmd = f"{BUILD_CMDS[-1]} {' '.join(EXTRA_COMP_FILES)}"
        # do normal compilation (with whatever's in the config)
        os.system(last_build_cmd)

        # check that the binary was actually built
        binary_name = BUILD_CMDS[-1].strip().split(' ')[-1]
        if os.path.isfile(binary_name):
            successes.append(benchmark)

        # --- 

        ### NATIVE SCRIPT GENERATION ###
        """
        Benchmark invocation looks like this:

        %% Fake commands from benchmark_run ... (
        <timer info>
        # Starting run for copy #0
        <COMMANDS>
        # Starting run for copy #0
        <COMMANDS>
        ...
        %% End of fake output from benchmark_run

        We're just running the first run of the benchmark, so we just want the
        first <COMMANDS> block
        """
        # only write shell scripts if the benchmark actually built
        if benchmark in successes:
            FIRST_INVOKE = INVOKE_CMDS.split('# Starting run for copy #0')[1]
            # stdout/err are piped to files for later verification;
            # we don't need that
            FIRST_INVOKE = FIRST_INVOKE[:FIRST_INVOKE.rfind(' > ')] + '\n'
            ### NATIVE SCRIPT GENERATION ###
            with open(f'{SCRIPT_DIR}/{benchmark}_native.sh', 'w') as f:
                f.write(SHEBANG)
                f.write(FIRST_INVOKE)
            os.system(f'chmod +x {SCRIPT_DIR}/{benchmark}_native.sh')
            ### GEM5 SCRIPT GENERATION ###
            LAST_CMD_LOC = FIRST_INVOKE[:-1].rfind('\n')
            LAST_CMD = FIRST_INVOKE[LAST_CMD_LOC+1:]
            WORKLOAD = LAST_CMD.split(' ')[0]
            WORKLOAD_ARGS = ' '.join(LAST_CMD.strip().split(' ')[1:])
            with open(f'{SCRIPT_DIR}/{benchmark}_gem5_noHFI.sh', 'w') as f:
                f.write(SHEBANG)
                f.write(FIRST_INVOKE[:LAST_CMD_LOC] + '\n')
                f.write(make_gem5_cmd(GEM5_DIR, benchmark, WORKLOAD, 
                    WORKLOAD_ARGS, "noHFI") + "\n")
            os.system(f'chmod +x {SCRIPT_DIR}/{benchmark}_gem5_noHFI.sh')
            with open(f'{SCRIPT_DIR}/{benchmark}_gem5_HFI.sh', 'w') as f:
                f.write(SHEBANG)
                f.write(FIRST_INVOKE[:LAST_CMD_LOC] + '\n')
                f.write(make_gem5_cmd(GEM5_DIR, benchmark, WORKLOAD, 
                    WORKLOAD_ARGS, "HFI") + f" --env={HFI_ENV}\n")
            os.system(f'chmod +x {SCRIPT_DIR}/{benchmark}_gem5_HFI.sh')
        # finally, return to the SPEC directory to prep for the next bmk
        os.chdir(SPEC06_DIR)

    ### LOGGING ###
    # write the successful benchmarks to a file
    with open(f'{SCRIPT_DIR}/log.txt', 'w') as f:
        f.write('Start time: ' + start_time + '\n')
        f.write('End time: ' + time.ctime() + '\n')
        f.write('\n')
        f.write('SPEC directory: ' + SPEC06_DIR + '\n')
        f.write('Config name: ' + CONFIG_NAME + '\n')
        f.write('Script directory: ' + SCRIPT_DIR + '\n')
        f.write('Included extra files: ' + ' '.join(EXTRA_COMP_FILES) + '\n')
        f.write('\n')
        f.write('Benchmarks which successfully built:\n')
        f.write('\n'.join(successes))
        f.write("\n\n")
        f.write("Benchmarks which failed to build:\n")
        f.write('\n'.join(set(C_BENCHMARKS) - set(successes)))
        f.write('\n')

    print("Done!")
    return

__main__()
