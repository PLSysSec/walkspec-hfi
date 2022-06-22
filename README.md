## Run SPEC06 without `runspec`.
Everything here is for UCSD's HFI project, so a lot of what `walkspec.py` does also involves gem5 and WASM.

##### Dependencies
- Our fork of gem5: https://github.com/PLSysSec/hw_isol_gem5
- Our fork of wasm2native: https://github.com/PLSysSec/wasm2native
- A copy of WASI-SDK 10 (for wasi-clang): https://github.com/WebAssembly/wasi-sdk/releases/tag/wasi-sdk-10
- A copy of the SPEC 2006 install disc


##### Setup and usage
1. Clone this repo, cd into it, and run `./get-wabt.sh`. This will get a specific release of WABT which seems to play nice with SPEC06. The release gets placed in a subfolder of this repo. 
2. Open the dockerfile `gem5-plus` (stock 20.04+deps gem5 image, but with clang and cmake installed via apt; TODO Joey still needs to package this) with the following volumes (i.e., use `-v` or `--volume`):
    - <HW_ISOL_GEM5_DIR>:/gem5
    - <WALKSPEC_DIR>:/walkspec
    - <SPEC_INSTALL_ISO_DIR>:/install_spec
    - <SPEC_DIR>:/spec
    - <WASM2NATIVE_DIR>:/wasm2native
    - <WASI-SDK_DIR>:/wasi-sdk
    - <WABT_DIR>:/wabt
3. From within the dockerfile, install SPEC06 to /spec. (NOTE: This will probably make it so `runspec` only works if SPEC06 is installed at /spec)
4. Copy `/walkspec/simConfig.cfg` and `/walkspec/wasmSimConfig.cfg` to `/spec/config/`.
5. Run `python /walkspec/walkspec.py`. This will try to build all C-only SPEC benchmarks and make scripts to run them in and out of gem5, with both clang and wasi-clang. Check the `log` files in `/walkspec/spec_scripts` to see which ones built successfully.

`{CONFIG}_401_native.sh` calls the compiled 401.bzip2 with the first command used by specinvoke. To make native execution use HFI (not sure why you'd want this), run `export HFI='1'` before running the script; to disable native HFI use `unset HFI`.

`{CONFIG}_401_gem5_HFI.sh` and `{CONFIG}_401_gem5_noHFI` invoke gem5 on the same command that `401_native.sh` does, with and without HFI respectively. This will take a lot longer! To tune what gem5 command is used, see walkspec.py's function make_gem5_cmd().

(All of the above are for 401.bzip2, but every C-only benchmark except perlbench gets shell scripts!)

### Current issues/todos
- wasm2c throws the error "expected valid block signature type" when run on something where wasi-clang included `hfi_check.c`. This is in the way of doing WASM+HFI tests.
- WASM+HFI should also use a limited version of WASM's isolation -- this still has to be added into the scripts.
