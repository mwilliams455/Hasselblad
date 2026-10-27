#include "chroma99.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
int main(void){
 enum{W=47,H=45,N=W*H*3,O=(W-30)*(H-30)*3};
 uint16_t src[N],out[O],copy[N];uint8_t flags[W*H]={0};
 for(int y=0;y<H;y++)for(int x=0;x<W;x++)for(int ch=0;ch<3;ch++)src[3*(y*W+x)+ch]=((x+y)%2)?30000:7000;
 int centre=22*W+23,k=((22-15)*(W-30)+23-15)*3;
 src[centre*3]=src[centre*3+2]=16000;src[centre*3+1]=14000;memcpy(copy,src,sizeof src);
 assert(!hb99_chroma_roi(src,N,flags,W*H,W,H,1,1,out,O));
 assert(out[k]<16000&&out[k+1]>14000);assert(!memcmp(copy,src,sizeof src));
 flags[centre+1]=1;
 assert(!hb99_chroma_roi(src,N,flags,W*H,W,H,1,1,out,O));assert(out[k]<16000);
 flags[centre+1]=2;
 assert(!hb99_chroma_roi(src,N,flags,W*H,W,H,1,1,out,O));assert(!memcmp(out+k,src+centre*3,6));
 flags[centre+1]=0;flags[centre]=1;
 assert(!hb99_chroma_roi(src,N,flags,W*H,W,H,1,1,out,O));assert(!memcmp(out+k,src+centre*3,6));
 memset(out,0x11,sizeof out);
 assert(hb99_chroma_roi(src,N-1,flags,W*H,W,H,1,1,out,O)==-1);
 assert(hb99_chroma_roi(src,N,flags,W*H-1,W,H,1,1,out,O)==-1);
 assert(hb99_chroma_roi(src,N,flags,W*H,W,H,1,1,out,O-1)==-1);
 assert(hb99_chroma_roi(src,N,flags,W*H,W,H,NAN,1,out,O)==-2);
 assert(hb99_chroma_roi(src,N,flags,W*H,W,H,.01,1,out,O)==-2);
 assert(hb99_chroma_roi(src,N,flags,W*H,W,H,1,1,src,N)==-1);
 for(int i=0;i<O;i++)assert(out[i]==0x1111);
 puts("PASS Stage99 censor distinction, bounded correction, immutability and invalid-call atomicity");
}
