import numpy as np
from scipy.ndimage import uniform_filter,maximum_filter,minimum_filter,median_filter

def candidate(rgb,n,kind='guided',limit=.06,size=31,strength=1.,black_neighbours=False,guide_mode='luma',positive_covariance=True):
 a=rgb.astype(np.float64)/n;s=a[:,:,0]+2*a[:,:,1]+a[:,:,2];Y=s/4
 chroma=np.stack([(a[:,:,0]-a[:,:,1])/(s+1),(a[:,:,2]-a[:,:,1])/(s+1)],2)
 if kind=='median':
  proposal=np.stack([median_filter(chroma[:,:,ch],3) for ch in range(2)],2);coherence=1.
 else:
  guide=Y if guide_mode=='luma' else a[:,:,1]
  mean=uniform_filter(guide,size);vY=np.maximum(uniform_filter(guide*guide,size)-mean*mean,0)
  fitted=[];vTotal=np.zeros_like(Y);explained=np.zeros_like(Y);positive=np.ones_like(Y,dtype=bool)
  for ch in range(3):
   v=a[:,:,ch];mv=uniform_filter(v,size);cov=uniform_filter(v*guide,size)-mv*mean
   positive &= cov>0
   slope=cov/np.maximum(vY,1.);fitted.append(mv+slope*(guide-mean))
   vTotal+=np.maximum(uniform_filter(v*v,size)-mv*mv,0)
   explained+=cov*cov/np.maximum(vY,1.)
  fit=np.stack(fitted,2);fs=fit[:,:,0]+2*fit[:,:,1]+fit[:,:,2]
  proposal=np.stack([(fit[:,:,0]-fit[:,:,1])/(fs+1),(fit[:,:,2]-fit[:,:,1])/(fs+1)],2)
  coherence=np.clip((explained/np.maximum(vTotal,1.)-.9)/.08,0,1)
 if positive_covariance:coherence*=positive
 delta=proposal-chroma;amount=np.max(np.abs(delta),2)
 hi=maximum_filter(Y,3);contrast=(hi-minimum_filter(Y,3))/np.maximum(hi,160)
 weight=np.minimum(strength,limit/np.maximum(amount,1e-15))*np.clip((contrast-.2)/.3,0,1)*coherence
 unsafe=maximum_filter(np.any(rgb==65535,2),size)
 unsafe|=maximum_filter(np.any(rgb==0,2),size) if black_neighbours else np.any(rgb==0,2)
 weight=np.where(unsafe,0,weight)
 d1=delta[:,:,0]*weight*(s+1);d2=delta[:,:,1]*weight*(s+1)
 out=(a+np.stack([(3*d1-d2)/4,-(d1+d2)/4,(3*d2-d1)/4],2))*n
 valid=(weight>0)&(amount>0)&np.all((out>=0)&(out<=65535),2)
 return np.where(valid[:,:,None],np.clip(np.floor(out+.5),0,65535).astype(np.uint16),rgb)
