import numpy as np, math
from PIL import Image, ImageDraw, ImageFilter
def glyph(S, bg=(0,0,0), scale=0.62):
    """Apple-ish: dark tile, conic-gradient orb with a chat bubble cut-out."""
    ss=S*2
    y,x=np.mgrid[0:ss,0:ss].astype(np.float32); c=ss/2
    ang=(np.arctan2(y-c,x-c)/(2*math.pi)+0.5)
    stops=np.array([[10,132,255],[94,92,230],[191,90,242],[255,55,95],[255,159,10],[10,132,255]],np.float32)
    t=ang*5; i=np.clip(t.astype(int),0,4); f=(t-i)[...,None]
    col=stops[i]*(1-f)+stops[i+1]*f
    r=np.hypot(x-c,y-c); R=ss*scale/2
    a=np.clip((R-r)/2,0,1)
    # soft inner highlight
    col=col*(0.82+0.18*np.clip(1-(y-c+R)/(2*R),0,1))[...,None]
    img=np.zeros((ss,ss,4),np.uint8); img[...,:3]=bg; img[...,3]=255
    out=img[...,:3]*(1-a[...,None])+col*a[...,None]
    im=Image.fromarray(np.dstack([out.astype(np.uint8),np.full((ss,ss),255,np.uint8)]),'RGBA')
    d=ImageDraw.Draw(im); w=R*1.05; h=R*0.78
    box=(c-w/2,c-h/2-R*0.06,c+w/2,c+h/2-R*0.06)
    d.rounded_rectangle(box,radius=h*0.42,fill=(255,255,255,255))
    d.polygon([(c-w*0.22,box[3]-2),(c-w*0.34,box[3]+R*0.22),(c-w*0.02,box[3]-2)],fill=(255,255,255,255))
    for k in (-1,0,1): rr=R*0.07; cx=c+k*R*0.27; cy=(box[1]+box[3])/2; d.ellipse((cx-rr,cy-rr,cx+rr,cy+rr),fill=tuple(int(v) for v in stops[1])+(255,))
    return im.resize((S,S),Image.LANCZOS)
for s in (180,192,512): glyph(s).convert('RGB').save(f'icons/icon-{s}.png')
for s in (192,512): glyph(s,scale=0.5).convert('RGB').save(f'icons/maskable-{s}.png')  # inside 80% safe zone
glyph(96).convert('RGB').save('icons/shortcut-new.png')
sizes=[(430,932,3),(393,852,3),(390,844,3),(428,926,3),(375,812,3),(414,896,3),(414,896,2),(375,667,2),(402,874,3),(440,956,3),(360,780,3)]
for w,h,r in sizes:
    for m,bg in (('dark',(0,0,0)),('light',(255,255,255))):
        W,H=w*r,h*r; im=Image.new('RGB',(W,H),bg); g=glyph(int(96*r),bg=bg,scale=1.0); im.paste(g,((W-g.width)//2,(H-g.height)//2)); im.save(f'splash/{m}-{W}x{H}.png',optimize=True)
