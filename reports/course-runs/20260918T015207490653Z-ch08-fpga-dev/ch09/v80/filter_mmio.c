/* Register-injection harness only: no Ethernet, no packets sent to the live lab.
 * Linux x86-64 sysfs resource2 MMIO; no AMI dependency or automatic driver unbind.
 */
#define _GNU_SOURCE
#include <endian.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#if !defined(__x86_64__)
#error "This small MMIO example is restricted to Linux x86-64 hosts"
#endif
#define APP_ID 0x464c4c39u
#define BAR_OFFSET 0x20000u
#define MAP_BYTES 4096u
static volatile uint32_t *regs;
static void fail(const char *s) { fprintf(stderr,"ERROR: %s\n",s); exit(1); }
static uint32_t rd(unsigned off) { return le32toh(regs[off/4]); }
static void wr(unsigned off, uint32_t val) {
    regs[off/4]=htole32(val);
    (void)rd(0); /* Flush posted writes by reading this same PCI function. */
}
static unsigned read_attr(const char *bdf, const char *attr) {
    char path[256]; int value;
    snprintf(path,sizeof(path),"/sys/bus/pci/devices/%s/%s",bdf,attr);
    FILE *f=fopen(path,"r");
    if (!f || fscanf(f,"%i",&value)!=1) fail("Cannot read PCI identity/state");
    fclose(f); return (unsigned)value;
}
static bool full_pf1_bdf(const char *s) {
    if (strlen(s)!=12 || s[4]!=':' || s[7]!=':' || s[10]!='.' || s[11]!='1') return false;
    for (unsigned i=0;i<12;i++) {
        if (i==4 || i==7 || i==10) continue;
        if (!((s[i]>='0'&&s[i]<='9')||(s[i]>='a'&&s[i]<='f'))) return false;
    }
    unsigned domain,bus,dev,func;
    return sscanf(s,"%4x:%2x:%2x.%1x",&domain,&bus,&dev,&func)==4 && dev<=31;
}
static void show(void) {
    uint32_t status=rd(8);
    if (status&1) { puts("busy=1; result not yet stable"); return; }
    printf("app_id=%08" PRIx32 " busy=%u valid=%u drop=%u remaining=%" PRIu32
           " pass_count=%" PRIu32 " drop_count=%" PRIu32 " seq=%" PRIu64 "\n",
           rd(0),status&1,(status>>1)&1,(status>>2)&1,rd(12),rd(16),rd(20),
           ((uint64_t)rd(28)<<32)|rd(24));
}
int main(int argc, char **argv) {
    const char *bdf=NULL, *command=NULL, *seqtext=NULL; bool allow_write=false;
    for (int i=1;i<argc;i++) {
        if (!strcmp(argv[i],"--device") && i+1<argc) bdf=argv[++i];
        else if (!strcmp(argv[i],"--write")) allow_write=true;
        else if (!command) command=argv[i];
        else if (!seqtext) seqtext=argv[i];
        else fail("Too many arguments");
    }
    if (!bdf || !command || !full_pf1_bdf(bdf))
        fail("Usage: flle-v80-mmio --device dddd:bb:dd.1 [--write] show|arm|disarm|submit [sequence]");
    bool submit=!strcmp(command,"submit"), showing=!strcmp(command,"show");
    if (!showing && strcmp(command,"arm") && strcmp(command,"disarm") && !submit) fail("Unknown command");
    if (submit != (seqtext!=NULL)) fail("Only submit requires one decimal sequence");
    if (!showing && !allow_write) fail("Register writes require --write");
    uint64_t seq=0;
    if (submit) {
        for (const char *p=seqtext; *p; p++) if (*p<'0'||*p>'9') fail("Sequence must be unsigned decimal");
        char *end=NULL; errno=0; seq=strtoull(seqtext,&end,10);
        if (errno || end==seqtext || *end) fail("Invalid sequence");
    }
    if (read_attr(bdf,"vendor")!=0x10ee || read_attr(bdf,"device")!=0x50b5 ||
        read_attr(bdf,"subsystem_device")!=0x000e) fail("Not the pinned V80 AMR PF1 identity");
    if (!read_attr(bdf,"enable")) fail("PF1 is disabled; verify the board deployment before enabling it");
    char path[256]; struct stat st;
    snprintf(path,sizeof(path),"/sys/bus/pci/devices/%s/driver",bdf);
    if (!lstat(path,&st) || errno!=ENOENT) fail("PF1 has a driver, or its ownership cannot be checked");
    snprintf(path,sizeof(path),"/sys/bus/pci/devices/%s/resource2",bdf);
    int fd=open(path,showing?O_RDONLY:O_RDWR);
    if (fd<0 || fstat(fd,&st) || st.st_size < (off_t)(BAR_OFFSET+MAP_BYTES)) fail("Missing/small PF1 BAR2");
    if (flock(fd,LOCK_EX|LOCK_NB)) fail("Cannot exclusively lock the PF1 BAR2 resource");
    void *mapping=mmap(NULL,MAP_BYTES,PROT_READ|(showing?0:PROT_WRITE),MAP_SHARED,fd,BAR_OFFSET);
    if (mapping==MAP_FAILED) fail("BAR2 mmap failed");
    regs=(volatile uint32_t *)mapping;
    if (rd(0)!=APP_ID) fail("APP_ID mismatch: this card does not contain the FLLE register-test circuit");
    if (!showing) {
        if (rd(8)&1) fail("Circuit is busy");
        if (submit) {
            uint8_t msg[36]={0};
            msg[0]='A'; msg[1]=8095>>8; msg[2]=8095&255;
            memcpy(msg+24,"NVDA    ",8);
            for (unsigned i=0;i<9;i++) {
                unsigned j=i*4;
                uint32_t word=((uint32_t)msg[j]<<24)|((uint32_t)msg[j+1]<<16)|
                              ((uint32_t)msg[j+2]<<8)|msg[j+3];
                wr(0x40+i*4,word);
            }
            wr(0x30,(uint32_t)seq); wr(0x34,(uint32_t)(seq>>32)); wr(4,2);
            struct timespec pause={.tv_sec=0,.tv_nsec=1000000};
            unsigned attempts=100;
            while ((rd(8)&3)!=2 && attempts--) nanosleep(&pause,NULL);
            if ((rd(8)&3)!=2) fail("Timed out: do not replay submit automatically; inspect/reset the test circuit");
            if ((((uint64_t)rd(28)<<32)|rd(24))!=seq) fail("Result sequence mismatch; do not replay submit automatically");
        } else wr(4,!strcmp(command,"arm")?1:4);
    }
    show(); munmap(mapping,MAP_BYTES); close(fd); return 0;
}
