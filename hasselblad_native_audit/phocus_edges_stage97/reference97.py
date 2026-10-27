import numpy as np
from scipy.ndimage import median_filter,maximum_filter,minimum_filter

def filter_chroma(rgb,n):
 a=rgb.astype(np.float64)/np.asarray(n,np.float64);s=a[:,:,0]+2*a[:,:,1]+a[:,:,2];Y=s*.25
 chroma=np.stack([(a[:,:,0]-a[:,:,1])/(s+1),(a[:,:,2]-a[:,:,1])/(s+1)],2)
 med=np.stack([median_filter(chroma[:,:,ch],size=3,mode='reflect') for ch in range(2)],2)
 mag=np.maximum(np.abs(chroma[:,:,0]),np.abs(chroma[:,:,1]));near=maximum_filter(mag,5)
 contrast=(maximum_filter(Y,3)-minimum_filter(Y,3))/np.maximum(maximum_filter(Y,3),160)
 # Local outlier correction in low-chroma high-contrast regions. Limit the
 # total chroma change and protect neighbourhoods with stronger colour.
 delta=med-chroma
 amount=np.max(np.abs(delta),2)
 weight=np.minimum(1,.005/np.maximum(amount,1e-8))
 weight*=np.clip((.16-near)/.08,0,1)*np.clip((contrast-.2)/.3,0,1)
 unsafe=np.any((rgb==0)|(rgb==65535),axis=2)
 weight=np.where(maximum_filter(unsafe,5),0,weight)
 d1=delta[:,:,0]*weight*(s+1);d2=delta[:,:,1]*weight*(s+1)
 out=(a+np.stack([(3*d1-d2)*.25,-(d1+d2)*.25,(3*d2-d1)*.25],2))*np.asarray(n)
 valid=(weight>0)&(amount>0)&np.all((out>=0)&(out<=65535),2)
 return np.where(valid[:,:,None],np.clip(np.floor(out+.5),0,65535).astype(np.uint16),rgb)
