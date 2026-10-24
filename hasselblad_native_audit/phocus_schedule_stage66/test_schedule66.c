#include "schedule66.h"
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>

typedef struct { int width,height; unsigned flags_seen[16];
                 unsigned parity_fail; uint64_t total; HB66Event prior;
                 int prior_x, prior_y; int fail_at; } SinkState;
static int sink(void *user,HB66Event event,int x,int y){
    SinkState *s=user;
    assert(x>=0 && x<s->width && y>=0 && y<s->height);
    if(event>=HB66_GREEN_AT_RED && event<=HB66_RB_GREEN_BLUE_ROW){
        int expected_x=-1,expected_y=-1;
        switch(event){
        case HB66_GREEN_AT_RED: case HB66_BLUE_AT_RED:
            expected_x=0;expected_y=0;break;
        case HB66_GREEN_AT_BLUE: case HB66_RED_AT_BLUE:
            expected_x=1;expected_y=1;break;
        case HB66_GREEN_SITE_TOP: case HB66_MASK_GREEN_RED_ROW:
        case HB66_RB_GREEN_RED_ROW:
            expected_x=1;expected_y=0;break;
        case HB66_GREEN_SITE_LEFT: case HB66_MASK_GREEN_BLUE_ROW:
        case HB66_RB_GREEN_BLUE_ROW:
            expected_x=0;expected_y=1;break;
        default:break;
        }
        if((x&1)!=expected_x || (y&1)!=expected_y) ++s->parity_fail;
    }
    if(event==HB66_GREEN_AT_BLUE) assert(s->prior==HB66_GREEN_SITE_LEFT);
    if(event==HB66_RB_GREEN_RED_ROW)
        assert(s->prior==HB66_MASK_GREEN_RED_ROW && s->prior_x==x && s->prior_y==y);
    if(event==HB66_RB_GREEN_BLUE_ROW)
        assert(s->prior==HB66_MASK_GREEN_BLUE_ROW && s->prior_x==x && s->prior_y==y);
    s->prior=event; s->prior_x=x;s->prior_y=y; ++s->total;
    ++s->flags_seen[event];
    return s->fail_at>=0 && (int)s->total==s->fail_at;
}
static void test_domain(int w,int h,int stride){
    SinkState state;memset(&state,0,sizeof state);
    state.width=w;state.height=h;state.fail_at=-1;
    HB66Counts c;
    int status=hb_schedule66((HB66Domain){w,h,stride,HB66_SCALAR_FLAGS},sink,&state,&c);
    assert(status==0); assert(state.parity_fail==0 && state.total==c.total_events);
    const uint64_t g=(uint64_t)((w-8)/2)*((h-8)/2);
    const uint64_t b=(uint64_t)((w-12)/2)*((h-12)/2);
    const uint64_t q=(uint64_t)((w-16)/2)*((h-16)/2);
    assert(c.green_colour_estimates==2*g);
    assert(c.untouched_green_site_assignments==2*g);
    assert(c.blue_at_red_candidates==b && c.red_at_blue_candidates==b);
    assert(c.green_site_masks==2*q && c.red_blue_green_candidates==2*q);
    assert(c.smooth_rows==(uint64_t)h-2 && c.edge_rows==(uint64_t)h-4);
    assert(c.copy_raw_codes==(uint64_t)stride*h);
    assert(c.scale_calls==1 && c.midgreen_calls==1);
    assert(c.total_events==(uint64_t)(2*h-6+3)+4*g+2*b+4*q);
    HB66Counts k;
    assert(hb_schedule66((HB66Domain){w,h,stride,HB66_SCALAR_FLAGS},NULL,NULL,&k)==0);
    assert(memcmp(&k,&c,sizeof(k))==0);
}
int main(void){
    test_domain(24,24,24); test_domain(32,24,49);
    test_domain(32,32,40);test_domain(64,64,72);
    test_domain(80,88,103);test_domain(96,96,104);test_domain(128,96,136);
    HB66Counts c;
    assert(hb_schedule66((HB66Domain){0,32,32,0xffff},NULL,NULL,&c)==-1);
    assert(hb_schedule66((HB66Domain){32,32,31,0xffff},NULL,NULL,&c)==-1);
    assert(hb_schedule66((HB66Domain){32,32,40,0x20},NULL,NULL,&c)==-2);
    assert(hb_schedule66((HB66Domain){32,33,40,0xffff},NULL,NULL,&c)==-2);
    assert(hb_schedule66((HB66Domain){23,32,40,0xffff},NULL,NULL,&c)==-2);
    SinkState s={0};s.width=32;s.height=32;s.fail_at=10;
    assert(hb_schedule66((HB66Domain){32,32,32,0xffff},sink,&s,&c)==-3);
    assert(s.total==10 && c.total_events==0);
    puts("STAGE66_SCALAR_SCHEDULE_SELF_TEST_PASS");
    return 0;
}
