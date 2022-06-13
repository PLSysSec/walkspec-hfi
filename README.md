1. Get the dockerfile jrdek/gem5-plus. (That's the official gem5 20.04 docker image, but with CMake and clang installed.)
2. Open the dockerfile with the following volumes:
    - <HW_ISOL_GEM5_DIR>:/gem5
    - <WALKSPEC_DIR>:/mywench
    - <RLBOX_WASM2C_SANDBOX_DIR>:/rlboxbox
    - <WASM2C_SANDBOX_COMPILER_DIR>:/w2ccomp
    - <SPEC_INSTALL_ISO_DIR>:/install_spec
    - <SPEC_DIR>:/spec
   Also, make sure that /mywench contains `hfi_check.c`. This bakes in environment-variable-triggered HFI to binaries we compile.
3. From within the dockerfile, install SPEC06 to /spec. This will probably make it so the runspec command only works if SPEC06 is located at /spec, in the future; just keep this in mind when setting up other compilers if you use another docker image.
4. Run `python /mywench/walkspec.py`. By default, the gem5 directory, walkspec directory, and spec directory are as listed here, run-scripts are output to `/mywench/spec_scripts/` (make sure whatever script directory you use exists), and walkspec also attempts to include `/mywench/hfi_check.c` in all compilation commands. The default SPEC06 config is `simConfig`, which is just a default gcc config modified to use clang. All of these are customizable. The command should take 3-5 minutes on a decent computer.

`401_native.sh` calls the compiled 401.bzip2 with the first command used by specinvoke. To make native execution use HFI (not sure why you'd want this), run `export HFI='1'` before running the script; to disable native HFI use `unset HFI`.

`401_gem5_HFI.sh` and `401_gem5_noHFI` invoke gem5 on the same command that `401_native.sh` does, with and without HFI respectively. This will take a lot longer! To tune what gem5 command is used, see walkspec.py's function make_gem5_cmd().

(All of the above are for 401.bzip2, but every C-only benchmark except perlbench gets shell scripts!)