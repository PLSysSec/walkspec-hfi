#include <stdlib.h>
#include <stdio.h>

void entry_wrapper() __attribute__((constructor));
void exit_wrapper() __attribute__((destructor));
void hfi_enter_sandbox();
void hfi_exit_sandbox();


void entry_wrapper() {
  if (getenv("HFI")) {
    //printf("HFI!\n");
    hfi_enter_sandbox();
  } else {
    //printf("No HFI.\n");
  }
}

void exit_wrapper() {
  if (getenv("HFI")) {
    //printf("Still HFI!\n");
    hfi_exit_sandbox();
  } else {
    //printf("Still no HFI.\n");
  }
}

void hfi_enter_sandbox() {
  __asm__ (".byte 0x0F, 0x04, 0x65, 0x00");
}

void hfi_exit_sandbox() {
  __asm__ (".byte 0x0F, 0x04, 0x66, 0x00");
}
