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
import sys

def make_gem5_cmd(gem5_dir, benchmark, workload, args, config):
    # TODO: tune this
    if args[0] == "<":
        argsWithFlag = f"-i {args[1:]}"
    else:
        argsWithFlag = f"-o \"{args}\""
    return f'{gem5_dir}/build/X86/gem5.opt --debug-flags=HFI \
--outdir={gem5_dir}/run_{benchmark}_{config}  \
{gem5_dir}/configs/example/se.py -c {workload} {argsWithFlag} --mem-size=16GB \
-I 50000000000 --cpu-type=DerivO3CPU --caches'

def build_bmks_and_make_scripts(CONFIG, EXTRA_COMP_FILES):
    SPEC06_DIR = '/spec'
    GEM5_DIR = '/gem5'
    SCRIPT_DIR = '/walkspec/spec_scripts'
    SHEBANG = "#!/bin/bash\n"  # sorry zsh lovers

    start_time = time.ctime()
    # from the config file, get the line which starts with 'ext':
    # this is part of the build and run directories
    os.chdir(SPEC06_DIR)
    with open(f'config/{CONFIG}.cfg', 'r') as f:
        for line in f:
            if line.startswith('ext'):
                EXT = line.split('=')[1].strip()
                #input(f"Config {CONFIG} has extension {EXT}.")
                break

    # benchmarks to try
    C_BENCHMARKS = ['400', '401', '403', '429', '445', '456', '458', '462', '464', \
                    '433', '470', '482', '444', '473']
    #C_BENCHMARKS = ['444', '473'] 
    
    """
    FIXME:
	- 400 doesn't compile in normal clang, but also doesn't here.
	- 403 needed setjmp, so I stubbed that; then it needed getcwd/getpagesize,
	  so I stubbed the former and put the result of `getconf PAGESIZE`; and now
	  stor-layout.c has an assertion failing...
	- 456's toplev.c needs "system"? (haven't investigated much)
        - 458 is failing due to some quirk of wasm2c's generated code: something of
	  type void is being assigned a value
	- 482 needs rlimit and I haven't stubbed that yet
    """

    # log successful builds, to be displayed at the end
    successes = []

    # for gem5-HFI, we need to make an environment variable file
    os.system(f'echo "HFI=\'1\'" > {SCRIPT_DIR}/hfi_env.txt')
    HFI_ENV = f'{SCRIPT_DIR}/hfi_env.txt'

    for benchmark in C_BENCHMARKS:
        ### BENCHMARK COMPILATION ###
        # do a fake run to get the runspec output
        run_log = run(
            f'. ./shrc && go {benchmark} && runspec --config={CONFIG} --loose \
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
        
        #input('\n'.join(BUILD_CMDS))
        for cmd in BUILD_CMDS[:-1]:
            os.system(cmd)
        last_build_cmd = f"{BUILD_CMDS[-1]} {' '.join(EXTRA_COMP_FILES)}"
        # do normal compilation (with whatever's in the config)
        print(last_build_cmd)
        os.system(last_build_cmd)

        # check that the binary was actually built
        binary_name = BUILD_CMDS[-1].strip().split(' ')[-1]
        if os.path.isfile(binary_name):
            successes.append(benchmark)
            # if using wasmSimConfig, invoke wasm2native
            if CONFIG == 'wasmSimConfig':
                os.chdir("/wasm2native")
                os.system("rm -rf src/wasi-app.c src/wasi-app.h")
                print(f'CC=clang ./build.sh {BUILD_DIR}/{BINARY_NAME}')
                os.system(f"CC=clang ./build.sh {BUILD_DIR}/{BINARY_NAME}")
                
                if f"{BINARY_NAME}.elf" in os.listdir():
                    os.system(f"mv {BUILD_DIR}/{BINARY_NAME} {BUILD_DIR}/{BINARY_NAME}.wasm")
                    os.system(f"mv /wasm2native/{BINARY_NAME}.elf {BUILD_DIR}/{BINARY_NAME}")
                    # now try to do it again, but with bounds checks removed
                    print('removing')
                    os.system(f"rm -rf src/wasi-app.c src/wasi-app.h")
                    print('building')
                    os.system(f"CC=clang NOBOUND=1 ./build.sh {BUILD_DIR}/{BINARY_NAME}.wasm")
                    if f"{BINARY_NAME}.elf" in os.listdir():
                        print("built!")
                        os.system(f"mv /wasm2native/{BINARY_NAME}.elf {BUILD_DIR}/{BINARY_NAME}-nobound")
                        successes.append(benchmark+"-nobound")
                    else:
                        print("nobound failed...")
                else:
                    # whoops, it failed!
                    successes.remove(benchmark)

        # --- 

        ### NATIVE SCRIPT GENERATION ###
        # (just use this for a sanity check)

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
            with open(f'{SCRIPT_DIR}/{CONFIG}_{benchmark}_native.sh', 'w') as f:
                f.write(SHEBANG)
                f.write(FIRST_INVOKE)
            os.system(f'chmod +x {SCRIPT_DIR}/{CONFIG}_{benchmark}_native.sh')
            ### GEM5 SCRIPT GENERATION ###
            LAST_CMD_LOC = FIRST_INVOKE[:-1].rfind('\n')
            LAST_CMD = FIRST_INVOKE[LAST_CMD_LOC+1:]
            WORKLOAD = LAST_CMD.split(' ')[0]
            WORKLOAD_ARGS = ' '.join(LAST_CMD.strip().split(' ')[1:])
            with open(f'{SCRIPT_DIR}/{CONFIG}_{benchmark}_gem5_noHFI.sh', 'w') as f:
                f.write(SHEBANG)
                f.write(FIRST_INVOKE[:LAST_CMD_LOC] + '\n')
                f.write(make_gem5_cmd(GEM5_DIR, benchmark, WORKLOAD, 
                    WORKLOAD_ARGS, "noHFI") + "\n")
            os.system(f'chmod +x {SCRIPT_DIR}/{CONFIG}_{benchmark}_gem5_noHFI.sh')
            with open(f'{SCRIPT_DIR}/{CONFIG}_{benchmark}_gem5_HFI.sh', 'w') as f:
                f.write(SHEBANG)
                f.write(FIRST_INVOKE[:LAST_CMD_LOC] + '\n')
                # if using wasmSimConfig, the HFI version should run {BENCHMARK}-nobound
                if CONFIG == "wasmSimConfig":
                    WORKLOAD += "-nobound"
                f.write(make_gem5_cmd(GEM5_DIR, benchmark, WORKLOAD, 
                    WORKLOAD_ARGS, "HFI") + f" --env={HFI_ENV}\n")
            os.system(f'chmod +x {SCRIPT_DIR}/{CONFIG}_{benchmark}_gem5_HFI.sh')
        # finally, return to the SPEC directory to prep for the next bmk
        os.chdir(SPEC06_DIR)

    ### LOGGING ###
    # write the successful benchmarks to a file
    with open(f'{SCRIPT_DIR}/{CONFIG}_log.txt', 'w') as f:
        f.write('Start time: ' + start_time + '\n')
        f.write('End time: ' + time.ctime() + '\n')
        f.write('\n')
        f.write('SPEC directory: ' + SPEC06_DIR + '\n')
        f.write('Config name: ' + CONFIG + '\n')
        f.write('Script directory: ' + SCRIPT_DIR + '\n')
        f.write('Included extra files: ' + ' '.join(EXTRA_COMP_FILES) + '\n')
        f.write('\n')
        f.write('Benchmarks which successfully built:\n')
        f.write('\n'.join(successes))
        f.write("\n\n")
        f.write("Benchmarks which failed to build:\n")
        f.write('\n'.join(set(C_BENCHMARKS) - set(successes)))
        f.write('\n')

    return


def setup_wasm2native():
    os.system("rm -rf /wasm2native/build")
    os.chdir("/wasm2native")
    # build the libraries once
    os.system("./build-libs.sh")
    if not os.path.isdir("/wasm2native/build"):
        print("Failed to build wasm2native libraries?!")
        exit()
    # slightly change build.sh: use the version of w2c added to
    # the docker image, and incorporate hfi_check.c
    os.system("cp -t /wasm2native/src /walkspec/hfi_check.c /walkspec/hfi.h /walkspec/hfi.S")
    os.system("patch -N /wasm2native/build.sh -i /walkspec/hfi-w2n.patch")
    return

def __main__():
    print("""\
    Default values:
        SPEC06:         /spec
        gem5:           /gem5
        scripts dir:    /walkspec/spec_scripts
        extra files:    [/walkspec/hfi_check.c, /walkspec/hfi.S]

    Make sure that you have the correct version of wabt in /wabt and that 
    wasm2native (modified to use /wabt/bin/wasm2c) is in /wasm2native.
    Builds will be done with both simConfig and wasmSimConfig.
    ------------
""")
    if "--now2n" not in sys.argv:
        setup_wasm2native()
    os.chdir("/walkspec")
    os.system("mkdir -p spec_scripts")
    build_bmks_and_make_scripts("simConfig", ["/walkspec/hfi_check.c", "/walkspec/hfi.S", "-I/walkspec"])
    # wasm2native incorporates hfi_check.c into output binaries
    build_bmks_and_make_scripts("wasmSimConfig", [])


__main__()
