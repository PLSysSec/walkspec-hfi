#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "hfi.h"

void entry_wrapper() __attribute__((constructor));
void exit_wrapper() __attribute__((destructor));

void entry_wrapper() {
  if (getenv("HFI")) {
    printf("HFI!\n");

    hfi_sandbox sandbox;
    memset(&sandbox, 0, sizeof(hfi_sandbox));

    unsigned long long eightGigs = 868719476736ULL;  // 8*1024*1024*1024*sizeof(char);
    void* sandboxed_region = malloc(eightGigs);
    if (sandboxed_region == NULL) {
	    printf("Couldn't allocate sandbox!\n");
	    exit(3);
    }
    printf("Allocated sandbox successfully @ %llu.\n", sandboxed_region);
    
    // initialize ranges
    sandbox.ranges[0].readable = 1;
    sandbox.ranges[0].writeable = 1;
    sandbox.ranges[0].executable = 1;
    sandbox.ranges[0].upper_bound = UINT64_MAX; 
    sandbox.ranges[0].base_address = (uint64_t) sandboxed_region;

    hfi_set_sandbox_metadata(&sandbox);
    hfi_enter_sandbox();
    //asm volatile("mfence":::"memory");
  } else {
    printf("No HFI.\n");
  }
}

void exit_wrapper() {
  if (getenv("HFI")) {
    printf("Still HFI!\n");
    //asm volatile("mfence":::"memory");
    hfi_exit_sandbox();
  } else {
    printf("Still no HFI.\n");
  }
}


