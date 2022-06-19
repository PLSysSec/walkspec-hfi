1. Open the dockerfile `gem5-plus` in this directory with the following volumes:
    - <HW_ISOL_GEM5_DIR>:/gem5
    - <WALKSPEC_DIR>:/walkspec
    - <RLBOX_WASM2C_SANDBOX_DIR>:/rlboxbox
    - <WASM2C_SANDBOX_COMPILER_DIR>:/w2ccomp
    - <SPEC_INSTALL_ISO_DIR>:/install_spec
    - <SPEC_DIR>:/spec
   Also, make sure that /walkspec contains `hfi_check.c`. This bakes in environment-variable-triggered HFI to binaries we compile.
2. Replace `/usr/bin/wasm2c` with the copy of `wasm2c` in this directory. This is the version included in `wabt/impish,now 1.0.20-1 amd64`, and for some reason, copy-pasting it into the docker image just works!)
3. From within the dockerfile, install SPEC06 to /spec. This will probably make it so the runspec command only works if SPEC06 is located at /spec, in the future; just keep this in mind when setting up other compilers if you use another docker image.
4. Run `python /walkspec/walkspec.py`. By default, the gem5 directory, walkspec directory, and spec directory are as listed here, run-scripts are output to `/walkspec/spec_scripts/` (make sure whatever script directory you use exists), and walkspec also attempts to include `/walkspec/hfi_check.c` in all compilation commands. The default SPEC06 config is `wasmSimConfig`, which is just a default gcc config modified to use wasi-clang. Also included is `simConfig`, which uses normal clang. All of these are customizable. The command should take 3-5 minutes on a decent computer.

`401_native.sh` calls the compiled 401.bzip2 with the first command used by specinvoke. To make native execution use HFI (not sure why you'd want this), run `export HFI='1'` before running the script; to disable native HFI use `unset HFI`.

`401_gem5_HFI.sh` and `401_gem5_noHFI` invoke gem5 on the same command that `401_native.sh` does, with and without HFI respectively. This will take a lot longer! To tune what gem5 command is used, see walkspec.py's function make_gem5_cmd().

(All of the above are for 401.bzip2, but every C-only benchmark except perlbench gets shell scripts!)
