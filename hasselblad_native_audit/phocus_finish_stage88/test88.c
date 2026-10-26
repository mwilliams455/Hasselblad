#include "finish88.h"
#include "post55.h"
#include <assert.h>
#include <math.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static void *worker(void *argument) {
    uintptr_t id=(uintptr_t)argument;
    uint16_t input[4096*3],old[4096*3],newer[4096*3],table[65536];
    for(size_t i=0;i<4096*3;i++)input[i]=(uint16_t)(i*101+id*7919);
    assert(hb55_default_curve(table)==0);
    assert(hb55_gradate(table,input,4096,old)==0);
    assert(hb88_gradate(input,4096,newer)==0);
    assert(memcmp(old,newer,sizeof(old))==0);
    for(int iteration=0;iteration<40;iteration++) {
        double e[]={1.,1.8,2.2,3.};
        double matrix[9]={1.12,-.1,-.02,-.04,1.03,.01,.02,-.2,1.18};
        matrix[0]+=(double)id/100.;
        double exponent=e[(id+(uintptr_t)iteration)%4];
        assert(hb55_output_rgb16(input,4096,matrix,exponent,old)==0);
        assert(hb88_output_rgb16(input,4096,matrix,exponent,newer)==0);
        assert(memcmp(old,newer,sizeof(old))==0);
    }
    return NULL;
}

int main(void) {
    pthread_t threads[4];
    for(uintptr_t i=0;i<4;i++)assert(pthread_create(&threads[i],NULL,worker,(void*)i)==0);
    for(int i=0;i<4;i++)assert(pthread_join(threads[i],NULL)==0);
    assert(hb88_curve_builds()==1);
    uint16_t input[3]={123,456,789},out[3]={42,42,42};
    double matrix[9]={1,0,0,0,1,0,0,0,1};
    unsigned long count=hb88_decode_builds();
    for(int i=0;i<47;i++)assert(hb88_output_rgb16(input,1,matrix,2.25,out)==0);
    assert(hb88_decode_builds()==count+1);
    for(int i=0;i<3;i++)out[i]=42;
    assert(hb88_output_rgb16(input,1,matrix,NAN,out)==-1);
    assert(out[0]==42&&out[1]==42&&out[2]==42);
    assert(hb88_output_rgb16(input,1,matrix,0,out)==-1);
    assert(hb88_output_rgb16(NULL,1,matrix,2.2,out)==-1);
    assert(hb88_gradate(NULL,1,out)==-1);
    puts("PASS cold concurrent initialization, 160 concurrent output comparisons, 47-band cache reuse and invalid inputs");
    return 0;
}
